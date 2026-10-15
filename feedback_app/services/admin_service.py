"""Admin Service: Business logic for administrative management, validation, and CSV export."""

import csv
import io
import re
import sqlite3
from typing import Any
from werkzeug.security import generate_password_hash
from feedback_app.repositories.admin_repository import AdminRepository

SEMESTER_PATTERN = re.compile(r"^\d{4}-(Spring|Summer|Fall)$")


class AdminService:
    """Encapsulates business rules for account management, course setup, and reporting."""

    def __init__(self, repo: type[AdminRepository] = AdminRepository):
        self.repo = repo

    @staticmethod
    def is_valid_semester(value: str) -> bool:
        """Validate semester format: YYYY-Spring, YYYY-Summer, or YYYY-Fall."""
        return bool(SEMESTER_PATTERN.fullmatch(value))

    def create_user(self, form_data: dict[str, Any]) -> tuple[bool, str, str]:
        """Validate input and create student or faculty account."""
        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip().lower()
        role = str(form_data.get("role", ""))
        code = str(form_data.get("profile_code", "")).strip()
        department = str(form_data.get("department", "")).strip()
        password = str(form_data.get("password", ""))

        if role not in {"student", "faculty"}:
            return False, "Choose student or faculty for the new account.", "danger"
        if len(full_name) < 2 or len(full_name) > 100 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            return False, "Enter a valid name and email address.", "danger"
        if not code or len(code) > 30 or not department or len(department) > 80 or len(password) < 8:
            return False, "Profile code, department, and a password of at least 8 characters are required.", "danger"

        try:
            self.repo.create_user(
                full_name=full_name,
                email=email,
                role=role,
                code=code,
                department=department,
                password_hash=generate_password_hash(password),
            )
            return True, f"{role.title()} account created.", "success"
        except sqlite3.IntegrityError:
            return False, "That email or profile code is already in use.", "danger"

    def update_user(
        self,
        user: sqlite3.Row,
        user_id: int,
        form_data: dict[str, Any],
    ) -> tuple[bool, str, str, dict[str, Any]]:
        """Validate and update student or faculty account."""
        full_name = str(form_data.get("full_name", "")).strip()
        email = str(form_data.get("email", "")).strip().lower()
        code = str(form_data.get("profile_code", "")).strip()
        department = str(form_data.get("department", "")).strip()

        updated_dict = dict(user)
        updated_dict.update(full_name=full_name, email=email, profile_code=code, department=department)

        if user["role"] == "admin":
            return False, "Administrator profile editing is not available here.", "warning", updated_dict
        if len(full_name) < 2 or len(full_name) > 100 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            return False, "Enter a valid name and email address.", "danger", updated_dict
        if not code or len(code) > 30 or not department or len(department) > 80:
            return False, "Profile code and department are required.", "danger", updated_dict

        try:
            self.repo.update_user(
                user_id=user_id,
                role=user["role"],
                full_name=full_name,
                email=email,
                code=code,
                department=department,
            )
            return True, "Account updated.", "success", updated_dict
        except sqlite3.IntegrityError:
            return False, "That email or profile code is already in use.", "danger", updated_dict

    def create_course(self, form_data: dict[str, Any]) -> tuple[bool, str, str]:
        """Validate and create a course."""
        code = str(form_data.get("course_code", "")).strip().upper()
        name = str(form_data.get("course_name", "")).strip()
        department = str(form_data.get("department", "")).strip()

        if not re.fullmatch(r"[A-Z0-9-]{2,15}", code) or not name or len(name) > 120 or not department or len(department) > 80:
            return False, "Enter a valid course code, course name, and department.", "danger"

        try:
            self.repo.create_course(code, name, department)
            return True, "Course created.", "success"
        except sqlite3.IntegrityError:
            return False, "That course code already exists.", "danger"

    def update_course(
        self,
        course_id: int,
        form_data: dict[str, Any],
        existing_course: sqlite3.Row,
    ) -> tuple[bool, str, str, dict[str, Any]]:
        """Validate and update a course."""
        code = str(form_data.get("course_code", "")).strip().upper()
        name = str(form_data.get("course_name", "")).strip()
        department = str(form_data.get("department", "")).strip()

        updated_dict = dict(existing_course)
        updated_dict.update(course_code=code, course_name=name, department=department)

        if not re.fullmatch(r"[A-Z0-9-]{2,15}", code) or not name or len(name) > 120 or not department:
            return False, "Enter a valid course code, name, and department.", "danger", updated_dict

        try:
            self.repo.update_course(course_id, code, name, department)
            return True, "Course updated.", "success", updated_dict
        except sqlite3.IntegrityError:
            return False, "That course code already exists.", "danger", updated_dict

    def create_assignment(self, faculty_id: int | None, course_id: int | None, semester: str) -> tuple[bool, str, str]:
        """Validate and assign faculty to a course."""
        clean_semester = semester.strip()
        if not faculty_id or not course_id or not self.is_valid_semester(clean_semester):
            return False, "Select a faculty member and course, and use semester format YYYY-Term.", "danger"

        try:
            self.repo.create_assignment(faculty_id, course_id, clean_semester)
            return True, "Faculty assigned to course.", "success"
        except sqlite3.IntegrityError:
            return False, "Assignment is invalid or already exists.", "danger"

    def enroll_student(self, student_id: int | None, course_id: int | None, semester: str) -> tuple[bool, str, str]:
        """Validate and enroll student into a course."""
        clean_semester = semester.strip()
        if not student_id or not course_id or not self.is_valid_semester(clean_semester):
            return False, "Select a student and course, and use semester format YYYY-Term.", "danger"

        try:
            self.repo.enroll_student(student_id, course_id, clean_semester)
            return True, "Student enrolled in course.", "success"
        except sqlite3.IntegrityError:
            return False, "Enrollment is invalid or already exists.", "danger"

    def generate_csv_report(self, category: str, semester: str | None = None) -> tuple[str, str]:
        """Generate CSV string with formula injection escaping."""
        rows = self.repo.get_export_rows(category, semester)
        if category == "course":
            headers = ["Course code", "Course name", "Semester", "Responses", "Average rating"]
            fields = ("course_code", "course_name", "semester", "responses", "average")
        else:
            headers = ["Faculty", "Semester", "Responses", "Average rating"]
            fields = ("faculty_name", "semester", "responses", "average")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        for row in rows:
            values = []
            for field in fields:
                val = str(row[field])
                # Sanitize against spreadsheet formula injection
                if val.startswith(("=", "+", "-", "@")):
                    val = "'" + val
                values.append(val)
            writer.writerow(values)

        return output.getvalue(), f"feedback-{category}-report.csv"
