import re
import sqlite3
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


class User(UserMixin):
    """Small authenticated-user object backed by the users table."""
    def __init__(self, row):
        self.id = str(row["user_id"])
        self.email = row["email"]
        self.full_name = row["full_name"]
        self.role = row["role"]
        self._active = bool(row["is_active"])

    @property
    def is_active(self):
        return self._active


def load_user(user_id):
    row = get_db().execute(
        "SELECT user_id, email, full_name, role, is_active FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return User(row) if row else None


def _safe_next_url(target):
    if not target:
        return None
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    if redirect_url.scheme in {"http", "https"} and host_url.netloc == redirect_url.netloc:
        return target
    return None


def _dashboard_endpoint(role):
    return {"student": "student.dashboard", "faculty": "faculty.dashboard", "admin": "admin.dashboard"}[role]


@bp.route("/login", methods=("GET", "POST"))
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_dashboard_endpoint(current_user.role)))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        row = get_db().execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            flash("Email or password is incorrect.", "danger")
        else:
            login_user(User(row))
            return redirect(_safe_next_url(request.args.get("next")) or url_for(_dashboard_endpoint(row["role"])))
    return render_template("auth/login.html")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if current_user.is_authenticated:
        return redirect(url_for(_dashboard_endpoint(current_user.role)))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        student_number = request.form.get("student_number", "").strip()
        department = request.form.get("department", "").strip()
        password = request.form.get("password", "")
        errors = []
        if len(full_name) < 2 or len(full_name) > 100:
            errors.append("Name must be between 2 and 100 characters.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            errors.append("Enter a valid email address.")
        if not re.fullmatch(r"[A-Za-z0-9-]{3,30}", student_number):
            errors.append("Student number must be 3-30 letters, numbers, or hyphens.")
        if not department or len(department) > 80:
            errors.append("Enter a department (up to 80 characters).")
        if len(password) < 8 or len(password) > 128:
            errors.append("Password must be between 8 and 128 characters.")

        if not errors:
            db = get_db()
            try:
                cursor = db.execute(
                    "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, 'student')",
                    (email, generate_password_hash(password), full_name),
                )
                db.execute(
                    "INSERT INTO students (student_id, student_number, department) VALUES (?, ?, ?)",
                    (cursor.lastrowid, student_number, department),
                )
                db.commit()
                flash("Registration complete. You can now log in.", "success")
                return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError:
                db.rollback()
                errors.append("That email or student number is already registered.")
        for error in errors:
            flash(error, "danger")
    return render_template("auth/register.html")


@bp.post("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
