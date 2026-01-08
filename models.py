from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)

    # Passwort wird gehasht gespeichert (niemals Klartext!)
    password_hash = db.Column(db.String(255), nullable=False)

    # Gesamtpunkte über alle Aufgaben / Bereiche
    total_points = db.Column(db.Integer, nullable=False, default=0)

    # Rolle: "student" oder "teacher"
    role = db.Column(db.String(20), nullable=False, default="student")

    # Beziehung zu Result (User -> viele Result-Einträge)
    results = db.relationship("Result", backref="user", lazy=True, cascade="all, delete-orphan")

    # -----------------------------
    # Passwort-Funktionen
    # -----------------------------
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # -----------------------------
    # Rollen-Helfer
    # -----------------------------
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    def __repr__(self) -> str:
        return f"<User {self.username} role={self.role} points={self.total_points}>"


class Result(db.Model):
    __tablename__ = "results"

    id = db.Column(db.Integer, primary_key=True)

    # z.B. "DIA_A1", "DIA_A2" usw.
    quiz_name = db.Column(db.String(50), nullable=False)

    points = db.Column(db.Integer, nullable=False, default=0)

    # Zeitstempel für Ranglisten/Verlauf/Teacher-Ansicht
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Foreign Key auf User
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def __repr__(self) -> str:
        return f"<Result {self.quiz_name} points={self.points} user_id={self.user_id} at={self.created_at}>"
