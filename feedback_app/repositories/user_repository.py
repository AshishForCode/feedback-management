"""User Repository: Database access layer for authentication, user lookups, and student registration."""

import sqlite3
from feedback_app.db import get_db


class UserRepository:
    """Encapsulates database operations for users and authentication."""

    @staticmethod
    def get_by_id(user_id: int | str) -> sqlite3.Row | None:
        """Fetch user by primary key ID."""
        db = get_db()
        return db.execute(
            "SELECT user_id, email, full_name, role, is_active FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    @staticmethod
    def get_by_email(email: str) -> sqlite3.Row | None:
        """Fetch user by case-insensitive unique email."""
        db = get_db()
        return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    @staticmethod
    def register_student(
        full_name: str,
        email: str,
        student_number: str,
        department: str,
        password_hash: str,
    ) -> None:
        """Atomically insert a new user and corresponding student record."""
        db = get_db()
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, 'student')",
            (email, password_hash, full_name),
        )
        db.execute(
            "INSERT INTO students (student_id, student_number, department) VALUES (?, ?, ?)",
            (cursor.lastrowid, student_number, department),
        )
        db.commit()
