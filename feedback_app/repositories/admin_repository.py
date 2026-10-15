"""Admin Repository: Database operations for user, course, assignment management and reporting."""

import sqlite3
from feedback_app.db import get_db


class AdminRepository:
    """Encapsulates administrative database operations."""

    @staticmethod
    def get_dashboard_summary() -> tuple[
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[sqlite3.Row],
    ]:
        """Fetch all dashboard datasets: users, courses, faculty, assignments, and students."""
        db = get_db()
        users = db.execute(
            """SELECT u.user_id, u.full_name, u.email, u.role,
                      COALESCE(s.student_number, f.employee_number, '') AS profile_code,
                      COALESCE(s.department, f.department, '') AS department
               FROM users u
               LEFT JOIN students s ON s.student_id = u.user_id
               LEFT JOIN faculty f ON f.faculty_id = u.user_id
               ORDER BY u.role, u.full_name"""
        ).fetchall()

        courses = db.execute("SELECT * FROM courses ORDER BY course_code").fetchall()

        faculty = db.execute(
            """SELECT f.faculty_id, u.full_name, f.employee_number
               FROM faculty f JOIN users u ON u.user_id = f.faculty_id
               WHERE u.is_active = 1 ORDER BY u.full_name"""
        ).fetchall()

        assignments = db.execute(
            """SELECT ca.assignment_id, ca.semester, c.course_code, c.course_name, u.full_name AS faculty_name
               FROM course_assignments ca
               JOIN courses c ON c.course_id = ca.course_id
               JOIN faculty f ON f.faculty_id = ca.faculty_id
               JOIN users u ON u.user_id = f.faculty_id
               ORDER BY ca.semester DESC, c.course_code"""
        ).fetchall()

        students = db.execute(
            """SELECT s.student_id, u.full_name, s.student_number
               FROM students s JOIN users u ON u.user_id = s.student_id
               WHERE u.is_active = 1 ORDER BY u.full_name"""
        ).fetchall()

        return users, courses, faculty, assignments, students

    @staticmethod
    def get_user_by_id(user_id: int) -> sqlite3.Row | None:
        """Fetch user profile with associated student/faculty details."""
        db = get_db()
        return db.execute(
            """SELECT u.user_id, u.full_name, u.email, u.role,
                      COALESCE(s.student_number, f.employee_number, '') AS profile_code,
                      COALESCE(s.department, f.department, '') AS department
               FROM users u
               LEFT JOIN students s ON s.student_id = u.user_id
               LEFT JOIN faculty f ON f.faculty_id = u.user_id
               WHERE u.user_id = ?""",
            (user_id,),
        ).fetchone()

    @staticmethod
    def create_user(
        full_name: str,
        email: str,
        role: str,
        code: str,
        department: str,
        password_hash: str,
    ) -> None:
        """Insert user account and associated role profile."""
        db = get_db()
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            (email, password_hash, full_name, role),
        )
        table = "students" if role == "student" else "faculty"
        code_col = "student_number" if role == "student" else "employee_number"
        db.execute(
            f"INSERT INTO {table} (student_id, {code_col}, department) VALUES (?, ?, ?)",
            (cursor.lastrowid, code, department),
        )
        db.commit()

    @staticmethod
    def update_user(
        user_id: int,
        role: str,
        full_name: str,
        email: str,
        code: str,
        department: str,
    ) -> None:
        """Update user record and role profile."""
        db = get_db()
        table = "students" if role == "student" else "faculty"
        code_col = "student_number" if role == "student" else "employee_number"
        id_col = "student_id" if role == "student" else "faculty_id"

        db.execute(
            "UPDATE users SET full_name = ?, email = ? WHERE user_id = ?",
            (full_name, email, user_id),
        )
        db.execute(
            f"UPDATE {table} SET {code_col} = ?, department = ? WHERE {id_col} = ?",
            (code, department, user_id),
        )
        db.commit()

    @staticmethod
    def delete_non_admin_user(user_id: int) -> None:
        """Delete user record (preventing deletion of admin roles)."""
        db = get_db()
        db.execute("DELETE FROM users WHERE user_id = ? AND role != 'admin'", (user_id,))
        db.commit()

    @staticmethod
    def get_course_by_id(course_id: int) -> sqlite3.Row | None:
        """Fetch course by ID."""
        db = get_db()
        return db.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()

    @staticmethod
    def create_course(code: str, name: str, department: str) -> None:
        """Create course record."""
        db = get_db()
        db.execute(
            "INSERT INTO courses (course_code, course_name, department) VALUES (?, ?, ?)",
            (code, name, department),
        )
        db.commit()

    @staticmethod
    def update_course(course_id: int, code: str, name: str, department: str) -> None:
        """Update course record."""
        db = get_db()
        db.execute(
            "UPDATE courses SET course_code = ?, course_name = ?, department = ? WHERE course_id = ?",
            (code, name, department, course_id),
        )
        db.commit()

    @staticmethod
    def delete_course(course_id: int) -> None:
        """Delete course record."""
        db = get_db()
        db.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
        db.commit()

    @staticmethod
    def create_assignment(faculty_id: int, course_id: int, semester: str) -> None:
        """Assign faculty to course for a semester."""
        db = get_db()
        db.execute(
            "INSERT INTO course_assignments (faculty_id, course_id, semester) VALUES (?, ?, ?)",
            (faculty_id, course_id, semester),
        )
        db.commit()

    @staticmethod
    def delete_assignment(assignment_id: int) -> None:
        """Delete course assignment."""
        db = get_db()
        db.execute("DELETE FROM course_assignments WHERE assignment_id = ?", (assignment_id,))
        db.commit()

    @staticmethod
    def enroll_student(student_id: int, course_id: int, semester: str) -> None:
        """Enroll student into course for a semester."""
        db = get_db()
        db.execute(
            "INSERT INTO student_courses (student_id, course_id, semester) VALUES (?, ?, ?)",
            (student_id, course_id, semester),
        )
        db.commit()

    @staticmethod
    def get_reports_summary(semester: str | None = None) -> tuple[
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[sqlite3.Row],
    ]:
        """Fetch report data: by course, by faculty, by semester, all feedback, and semester list."""
        db = get_db()
        where_sql = "WHERE f.semester = ?" if semester else ""
        params = (semester,) if semester else ()

        by_course = db.execute(
            f"""SELECT c.course_code, c.course_name, f.semester, COUNT(*) AS responses,
                       ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
                FROM feedback f JOIN courses c ON c.course_id = f.course_id {where_sql}
                GROUP BY c.course_id, f.semester ORDER BY f.semester DESC, c.course_code""",
            params,
        ).fetchall()

        by_faculty = db.execute(
            f"""SELECT u.full_name AS faculty_name, f.semester, COUNT(*) AS responses,
                       ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
                FROM feedback f JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
                JOIN faculty fac ON fac.faculty_id = ca.faculty_id
                JOIN users u ON u.user_id = fac.faculty_id
                {where_sql}
                GROUP BY fac.faculty_id, f.semester
                ORDER BY f.semester DESC, u.full_name""",
            params,
        ).fetchall()

        by_semester = db.execute(
            """SELECT semester, COUNT(*) AS responses,
                      ROUND(AVG((teaching_quality + course_content + punctuality) / 3.0), 2) AS average
               FROM feedback GROUP BY semester ORDER BY semester DESC"""
        ).fetchall()

        all_feedback = db.execute(
            f"""SELECT f.*, c.course_code, c.course_name, student.full_name AS student_name,
                       faculty_user.full_name AS faculty_name
                FROM feedback f JOIN courses c ON c.course_id = f.course_id
                JOIN users student ON student.user_id = f.student_id
                JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
                JOIN faculty fac ON fac.faculty_id = ca.faculty_id
                JOIN users faculty_user ON faculty_user.user_id = fac.faculty_id
                {where_sql} ORDER BY f.created_at DESC""",
            params,
        ).fetchall()

        semesters = db.execute("SELECT DISTINCT semester FROM feedback ORDER BY semester DESC").fetchall()

        return by_course, by_faculty, by_semester, all_feedback, semesters

    @staticmethod
    def get_export_rows(category: str, semester: str | None = None) -> list[sqlite3.Row]:
        """Fetch aggregation rows for CSV export."""
        db = get_db()
        semester_clause = "AND f.semester = ?" if semester else ""
        params = (semester,) if semester else ()

        if category == "course":
            return db.execute(
                f"""SELECT c.course_code, c.course_name, f.semester, COUNT(*) AS responses,
                           ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
                    FROM feedback f JOIN courses c ON c.course_id = f.course_id
                    WHERE 1=1 {semester_clause}
                    GROUP BY c.course_id, f.semester ORDER BY f.semester DESC, c.course_code""",
                params,
            ).fetchall()
        else:
            return db.execute(
                f"""SELECT u.full_name AS faculty_name, f.semester, COUNT(*) AS responses,
                           ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
                    FROM feedback f JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
                    JOIN faculty fac ON fac.faculty_id = ca.faculty_id
                    JOIN users u ON u.user_id = fac.faculty_id
                    WHERE 1=1 {semester_clause}
                    GROUP BY fac.faculty_id, f.semester ORDER BY f.semester DESC, u.full_name""",
                params,
            ).fetchall()
