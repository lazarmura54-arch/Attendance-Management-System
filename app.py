from flask import Flask, render_template, request, jsonify, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random, string

# ================= INIT =================
app = Flask(__name__)
app.config['SECRET_KEY'] = "secret123"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///attendance.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ================= MODELS =================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))


class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    trainer_id = db.Column(db.Integer)
    invite_code = db.Column(db.String(10), unique=True)


class BatchStudent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer)
    student_id = db.Column(db.Integer)


class SessionModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    date = db.Column(db.Date)
    trainer_id = db.Column(db.Integer)
    batch_id = db.Column(db.Integer)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer)
    student_id = db.Column(db.Integer)
    status = db.Column(db.String(20))
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)


# ================= HELPERS =================

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def require_login():
    return 'user_id' in session


# ================= ROUTES =================

@app.route('/')
def home():
    return render_template('index.html')


# ================= AUTH =================

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    if not all([data.get('name'), data.get('email'), data.get('password'), data.get('role')]):
        return jsonify({'message': 'All fields required'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 400

    user = User(
        name=data['name'],
        email=data['email'],
        password=generate_password_hash(data['password']),
        role=data['role']
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'Signup successful'})


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    user = User.query.filter_by(email=data['email']).first()

    if user and check_password_hash(user.password, data['password']):
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['role'] = user.role
        return jsonify({'redirect': '/dashboard'})

    return jsonify({'message': 'Invalid credentials'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ================= DASHBOARD =================

@app.route('/dashboard')
def dashboard():
    if not require_login():
        return redirect('/')

    role = session['role']

    if role == 'student':
        batch_ids = [b.batch_id for b in BatchStudent.query.filter_by(student_id=session['user_id']).all()]
        sessions = SessionModel.query.filter(SessionModel.batch_id.in_(batch_ids)).all()
        return render_template('dashboard.html', role=role, sessions=sessions)

    elif role == 'trainer':
        sessions = SessionModel.query.filter_by(trainer_id=session['user_id']).all()
        batches = Batch.query.filter_by(trainer_id=session['user_id']).all()
        return render_template('dashboard.html', role=role, sessions=sessions, batches=batches)

    else:
        users = User.query.all()
        return render_template('dashboard.html', role=role, users=users)


# ================= BATCH =================

@app.route('/batch/create', methods=['POST'])
def create_batch():
    if session.get('role') != 'trainer':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()

    if not data.get('name'):
        return jsonify({'message': 'Batch name required'}), 400

    batch = Batch(
        name=data['name'],
        trainer_id=session['user_id'],
        invite_code=generate_code()
    )

    db.session.add(batch)
    db.session.commit()

    return jsonify({'message': 'Batch created', 'invite_code': batch.invite_code})


@app.route('/batch/join', methods=['POST'])
def join_batch():
    if session.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()

    batch = Batch.query.filter_by(invite_code=data.get('code')).first()

    if not batch:
        return jsonify({'message': 'Invalid code'}), 400

    if BatchStudent.query.filter_by(batch_id=batch.id, student_id=session['user_id']).first():
        return jsonify({'message': 'Already joined'}), 400

    db.session.add(BatchStudent(batch_id=batch.id, student_id=session['user_id']))
    db.session.commit()

    return jsonify({'message': 'Joined batch'})


# ================= SESSION =================

@app.route('/session/create', methods=['POST'])
def create_session():
    if session.get('role') != 'trainer':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()

    if not data.get('title') or not data.get('date'):
        return jsonify({'message': 'Title and date required'}), 400

    new_session = SessionModel(
        title=data['title'],
        date=datetime.strptime(data['date'], "%Y-%m-%d"),
        trainer_id=session['user_id'],
        batch_id=data.get('batch_id')
    )

    db.session.add(new_session)
    db.session.commit()

    return jsonify({'message': 'Session created'})


# ================= ATTENDANCE =================

@app.route('/attendance/mark', methods=['POST'])
def mark_attendance():
    if session.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()

    if Attendance.query.filter_by(session_id=data['session_id'], student_id=session['user_id']).first():
        return jsonify({'message': 'Already marked'}), 400

    db.session.add(Attendance(
        session_id=data['session_id'],
        student_id=session['user_id'],
        status=data['status']
    ))

    db.session.commit()

    return jsonify({'message': 'Attendance marked'})


@app.route('/session/<int:id>/attendance')
def view_attendance(id):
    records = Attendance.query.filter_by(session_id=id).all()

    result = []
    for r in records:
        user = User.query.get(r.student_id)
        result.append({
            "name": user.name if user else "Unknown",
            "status": r.status
        })

    return jsonify(result)


# ================= STATS =================

@app.route('/attendance/stats')
def attendance_stats():
    if not require_login():
        return jsonify({})

    records = Attendance.query.filter_by(student_id=session['user_id']).all()

    present = len([r for r in records if r.status == 'Present'])
    absent = len([r for r in records if r.status == 'Absent'])
    late = len([r for r in records if r.status == 'Late'])

    return jsonify({
        "present": present,
        "absent": absent,
        "late": late
    })


# ================= ADMIN =================

@app.route('/admin')
def admin():
    users = User.query.all()
    records = Attendance.query.all()

    data = []
    for r in records:
        user = User.query.get(r.student_id)
        data.append({
            "name": user.name if user else "Unknown",
            "status": r.status,
            "marked_at": r.marked_at
        })

    return render_template("admin.html", users=users, records=data)


# ================= RUN =================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)