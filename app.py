import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# =========================
# INIT
# =========================
load_dotenv()

app = Flask(__name__)

# SECRET KEY
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# =========================
# DATABASE CONFIG (FIXED)
# =========================
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("❌ DATABASE_URL is not set in environment variables")

# Fix postgres URL for SQLAlchemy
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Render PostgreSQL fix (SSL)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {
        "sslmode": "require"
    }
}

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))
    role = db.Column(db.String(50))


class Batch(db.Model):
    __tablename__ = "batches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    trainer_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))


class SessionModel(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    date = db.Column(db.Date)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    status = db.Column(db.String(20))


# =========================
# CREATE TABLES
# =========================
with app.app_context():
    db.create_all()


# =========================
# ROUTES
# =========================

@app.route('/')
def home():
    return render_template("index.html")


# =========================
# AUTH
# =========================

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form['name']
    email = request.form['email']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']

    if User.query.filter_by(email=email).first():
        flash("User already exists")
        return redirect('/')

    user = User(name=name, email=email, password=password, role=role)
    db.session.add(user)
    db.session.commit()

    flash("Signup successful")
    return redirect('/')


@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.name   # ✅ FIXED

        return redirect('/dashboard')

    flash("Invalid credentials")
    return redirect('/')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# =========================
# DASHBOARD
# =========================

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    role = session['role']
    user_id = session['user_id']

    users = User.query.all()
    batches = Batch.query.all()

    sessions_data = []

    if role == 'trainer':
        sessions_data = SessionModel.query.join(Batch).filter(Batch.trainer_id == user_id).all()

    elif role == 'student':
        enrollments = Enrollment.query.filter_by(student_id=user_id).all()
        batch_ids = [e.batch_id for e in enrollments]

        if batch_ids:
            sessions_data = SessionModel.query.filter(SessionModel.batch_id.in_(batch_ids)).all()

    else:
        sessions_data = SessionModel.query.all()

    return render_template(
        "dashboard.html",
        role=role,
        users=users,
        batches=batches,
        sessions=sessions_data
    )


# =========================
# CREATE BATCH
# =========================

@app.route('/create_batch', methods=['POST'])
def create_batch():
    if session.get('role') != 'trainer':
        return redirect('/dashboard')

    name = request.form['batch_name']

    batch = Batch(name=name, trainer_id=session['user_id'])
    db.session.add(batch)
    db.session.commit()

    return redirect('/dashboard')


# =========================
# JOIN BATCH
# =========================

@app.route('/join_batch', methods=['POST'])
def join_batch():
    if session.get('role') != 'student':
        return redirect('/dashboard')

    batch_id = request.form['batch_id']

    exists = Enrollment.query.filter_by(
        student_id=session['user_id'],
        batch_id=batch_id
    ).first()

    if not exists:
        enrollment = Enrollment(
            student_id=session['user_id'],
            batch_id=batch_id
        )
        db.session.add(enrollment)
        db.session.commit()

    return redirect('/dashboard')


# =========================
# CREATE SESSION
# =========================

@app.route('/create_session', methods=['POST'])
def create_session():
    if session.get('role') != 'trainer':
        return redirect('/dashboard')

    title = request.form['title']
    date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
    batch_id = request.form['batch_id']

    new_session = SessionModel(
        title=title,
        date=date,
        batch_id=batch_id
    )

    db.session.add(new_session)
    db.session.commit()

    return redirect('/dashboard')


# =========================
# MARK ATTENDANCE
# =========================

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if session.get('role') != 'student':
        return redirect('/dashboard')

    session_id = request.form['session_id']
    status = request.form['status']

    existing = Attendance.query.filter_by(
        student_id=session['user_id'],
        session_id=session_id
    ).first()

    if existing:
        existing.status = status
    else:
        attendance = Attendance(
            student_id=session['user_id'],
            session_id=session_id,
            status=status
        )
        db.session.add(attendance)

    db.session.commit()

    return redirect('/dashboard')


# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True)