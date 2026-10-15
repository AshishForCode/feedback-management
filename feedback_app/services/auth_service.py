"""Auth Service: Business rules for user authentication, password verification, and registration."""

import re
import sqlite3
from typing import Any
from urllib.parse import urljoin, urlparse
from werkzeug.security import check_password_hash, generate_password_hash
from feedback_app.repositories.user_repository import UserRepository


class AuthService:
    """Encapsulates authentication, credential checking, and registration workflows."""

    def __init__(self, repo: type[UserRepository] = UserRepository):
        self.repo = repo

    @staticmethod
    def get_dashboard_endpoint(role: str) -> str:
        """Map user role to dashboard route endpoint."""
        mapping = {
            "student": "student.dashboard",
            "faculty": "faculty.dashboard",
            "admin": "admin.dashboard",
        }
        return mapping.get(role, "auth.login")

    @staticmethod
    def is_safe_redirect_url(target: str | None, host_url: str) -> str | None:
        """Validate that the redirect target is an internal URL on the same host."""
        if not target:
            return None
        base = urlparse(host_url)
        redirect = urlparse(urljoin(host_url, target))
        if redirect.scheme in {"http", "https"} and base.netloc == redirect.netloc:
            return target
        return None

    def authenticate(self, email: str, password: str) -> tuple[sqlite3.Row | None, str | None]:
        """Verify user credentials. Returns (user_row, error_message)."""
        clean_email = email.strip().lower()
        row = self.repo.get_by_email(clean_email)
        if row is None or not check_password_hash(row["password_hash"], password):
            return None, "Email or password is incorrect."
        if not row["is_active"]:
            return None, "This account has been deactivated. Please contact an administrator."
        return row, None

    def validate_registration(self, form_data: dict[str, Any]) -> list[str]:
        """Validate student registration fields."""
        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip().lower()
        student_number = str(form_data.get("student_number", "")).strip()
        department = str(form_data.get("department", "")).strip()
        password = str(form_data.get("password", ""))

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
        return errors

    def register_student(self, form_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate input and register a new student."""
        errors = self.validate_registration(form_data)
        if errors:
            return False, errors

        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip().lower()
        student_number = str(form_data.get("student_number", "")).strip()
        department = str(form_data.get("department", "")).strip()
        password = str(form_data.get("password", ""))

        try:
            self.repo.register_student(
                full_name=full_name,
                email=email,
                student_number=student_number,
                department=department,
                password_hash=generate_password_hash(password),
            )
            return True, []
        except sqlite3.IntegrityError:
            return False, ["That email or student number is already registered."]
