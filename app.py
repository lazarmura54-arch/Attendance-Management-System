import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# ================= INIT =================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# ================= DATABASE =================
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("DATABASE_URL not set")

# Fix postgres:// issue
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {"sslmode": "require"},
}

db = SQLAlchemy(app)

# ================= MODELS =================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))
    role = db.Column(db.String(50))


class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    trainer_id = db.Column(db.Integer, db.ForeignKey("user.id"))


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"))


class SessionModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    date = db.Column(db.Date)
    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"))


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    session_id = db.Column(db.Integer, db.ForeignKey("session_model.id"))
    status = db.Column(db.String(20))


# ================= CREATE TABLES =================
with app.app_context():
    db.create_all()


# ================= ROUTES =================

@app.route("/")
def home():
    return render_template("index.html")


# ================= AUTH =================

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = generate_password_hash(data.get("password"))
    role = data.get("role")

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "User already exists"})

    user = User(name=name, email=email, password=password, role=role)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Signup successful"})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        session["user_id"] = user.id
        session["role"] = user.role
        session["user_name"] = user.name

        return jsonify({"redirect": "/dashboard"})

    return jsonify({"message": "Invalid credentials"})


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    role = session["role"]
    user_id = session["user_id"]

    users = User.query.all()
    batches = Batch.query.all()

    sessions_data = []

    if role == "trainer":
        sessions_data = (
            SessionModel.query.join(Batch)
            .filter(Batch.trainer_id == user_id)
            .all()
        )

    elif role == "student":
        enrollments = Enrollment.query.filter_by(student_id=user_id).all()
        batch_ids = [e.batch_id for e in enrollments]

        if batch_ids:
            sessions_data = SessionModel.query.filter(
                SessionModel.batch_id.in_(batch_ids)
            ).all()

    else:
        sessions_data = SessionModel.query.all()

    return render_template(
        "dashboard.html",
        role=role,
        users=users,
        batches=batches,
        sessions=sessions_data,
    )


# ================= BATCH =================

@app.route("/batch/create", methods=["POST"])
def create_batch():
    if session.get("role") != "trainer":
        return jsonify({"message": "Unauthorized"})

    data = request.get_json()
    name = data.get("name")

    batch = Batch(name=name, trainer_id=session["user_id"])
    db.session.add(batch)
    db.session.commit()

    return jsonify({"message": "Batch created"})


@app.route("/batch/join", methods=["POST"])
def join_batch():
    if session.get("role") != "student":
        return jsonify({"message": "Unauthorized"})

    data = request.get_json()
    batch_id = data.get("code")  # using code as batch_id for now

    exists = Enrollment.query.filter_by(
        student_id=session["user_id"], batch_id=batch_id
    ).first()

    if exists:
        return jsonify({"message": "Already joined"})

    enrollment = Enrollment(
        student_id=session["user_id"], batch_id=batch_id
    )
    db.session.add(enrollment)
    db.session.commit()

    return jsonify({"message": "Joined batch"})


# ================= SESSION =================

@app.route("/session/create", methods=["POST"])
def create_session():
    if session.get("role") != "trainer":
        return jsonify({"message": "Unauthorized"})

    data = request.get_json()

    title = data.get("title")
    date = datetime.strptime(data.get("date"), "%Y-%m-%d").date()
    batch_id = data.get("batch_id")

    new_session = SessionModel(
        title=title, date=date, batch_id=batch_id
    )

    db.session.add(new_session)
    db.session.commit()

    return jsonify({"message": "Session created"})


# ================= ATTENDANCE =================

@app.route("/attendance/mark", methods=["POST"])
def mark_attendance():
    if session.get("role") != "student":
        return jsonify({"message": "Unauthorized"})

    data = request.get_json()

    session_id = data.get("session_id")
    status = data.get("status")

    existing = Attendance.query.filter_by(
        student_id=session["user_id"], session_id=session_id
    ).first()

    if existing:
        existing.status = status
    else:
        attendance = Attendance(
            student_id=session["user_id"],
            session_id=session_id,
            status=status,
        )
        db.session.add(attendance)

    db.session.commit()

    return jsonify({"message": "Attendance updated"})


# ================= VIEW ATTENDANCE =================

@app.route("/session/<int:id>/attendance")
def view_attendance(id):
    records = Attendance.query.filter_by(session_id=id).all()

    data = []
    for r in records:
        user = User.query.get(r.student_id)
        data.append({
            "name": user.name if user else "Unknown",
            "status": r.status
        })

    return jsonify(data)


# ================= STATS =================

@app.route("/attendance/stats")
def stats():
    present = Attendance.query.filter_by(status="Present").count()
    absent = Attendance.query.filter_by(status="Absent").count()
    late = Attendance.query.filter_by(status="Late").count()

    return jsonify({
        "present": present,
        "absent": absent,
        "late": late
    })


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)