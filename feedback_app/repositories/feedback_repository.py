"""Feedback Repository: Data access layer for student feedback and dynamic forms."""

import sqlite3
from typing import Any
from feedback_app.db import get_db


class FeedbackRepository:
    """Encapsulates all database operations for feedback submissions and student courses."""

    @staticmethod
    def get_student_courses(student_id: int) -> list[sqlite3.Row]:
        """Fetch all courses a student is enrolled in with current feedback status."""
        db = get_db()
        return db.execute(
            """SELECT sc.course_id, sc.semester, c.course_code, c.course_name,
                      ca.assignment_id, u.full_name AS faculty_name,
                      f.feedback_id, f.created_at
               FROM student_courses sc
               JOIN courses c ON c.course_id = sc.course_id
               LEFT JOIN course_assignments ca
                 ON ca.course_id = sc.course_id AND ca.semester = sc.semester
               LEFT JOIN faculty fac ON fac.faculty_id = ca.faculty_id
               LEFT JOIN users u ON u.user_id = fac.faculty_id
               LEFT JOIN feedback f
                 ON f.student_id = sc.student_id AND f.course_id = sc.course_id
                AND f.semester = sc.semester
               WHERE sc.student_id = ?
               ORDER BY sc.semester DESC, c.course_code, u.full_name""",
            (student_id,),
        ).fetchall()

    @staticmethod
    def get_feedback_history(student_id: int) -> list[sqlite3.Row]:
        """Fetch feedback history submitted by the student."""
        db = get_db()
        return db.execute(
            """SELECT f.*, c.course_code, c.course_name
               FROM feedback f JOIN courses c ON c.course_id = f.course_id
               WHERE f.student_id = ? ORDER BY f.created_at DESC""",
            (student_id,),
        ).fetchall()

    @staticmethod
    def get_active_forms_for_student(student_id: int) -> list[sqlite3.Row]:
        """Fetch active custom feedback forms available for courses the student is enrolled in."""
        db = get_db()
        return db.execute(
            """SELECT ff.form_id, ff.title, ff.instructions, ff.is_active, ff.created_at,
                      c.course_code, c.course_name, ca.semester, u.full_name AS faculty_name,
                      (SELECT COUNT(*) FROM form_questions fq WHERE fq.form_id = ff.form_id) AS question_count,
                      (SELECT COUNT(*) FROM form_responses fr WHERE fr.form_id = ff.form_id AND fr.student_id = ?) AS has_submitted
               FROM feedback_forms ff
               JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
               JOIN courses c ON c.course_id = ca.course_id
               JOIN faculty fac ON fac.faculty_id = ca.faculty_id
               JOIN users u ON u.user_id = fac.faculty_id
               JOIN student_courses sc ON sc.course_id = ca.course_id AND sc.semester = ca.semester
               WHERE sc.student_id = ? AND ff.is_active = 1
               ORDER BY ff.created_at DESC""",
            (student_id, student_id),
        ).fetchall()

    @staticmethod
    def get_assignment_for_student(assignment_id: int, student_id: int) -> sqlite3.Row | None:
        """Fetch an assignment detail ensuring the student is enrolled."""
        db = get_db()
        return db.execute(
            """SELECT ca.assignment_id, ca.course_id, ca.semester, c.course_code, c.course_name,
                      u.full_name AS faculty_name
               FROM course_assignments ca
               JOIN courses c ON c.course_id = ca.course_id
               JOIN faculty f ON f.faculty_id = ca.faculty_id
               JOIN users u ON u.user_id = f.faculty_id
               JOIN student_courses sc ON sc.course_id = ca.course_id AND sc.semester = ca.semester
               WHERE ca.assignment_id = ? AND sc.student_id = ?""",
            (assignment_id, student_id),
        ).fetchone()

    @staticmethod
    def get_feedback_for_course(student_id: int, course_id: int, semester: str) -> sqlite3.Row | None:
        """Fetch existing feedback for a student in a specific course semester."""
        db = get_db()
        return db.execute(
            """SELECT * FROM feedback
               WHERE student_id = ? AND course_id = ? AND semester = ?""",
            (student_id, course_id, semester),
        ).fetchone()

    @staticmethod
    def get_feedback_by_id(feedback_id: int, student_id: int) -> sqlite3.Row | None:
        """Fetch a specific feedback submission owned by the student."""
        db = get_db()
        return db.execute(
            "SELECT * FROM feedback WHERE feedback_id = ? AND student_id = ?",
            (feedback_id, student_id),
        ).fetchone()

    @staticmethod
    def is_editable(created_at: str, edit_hours: int) -> bool:
        """Verify whether the feedback submission is still within the allowable edit window."""
        db = get_db()
        row = db.execute(
            "SELECT julianday(?) >= julianday('now', ?) AS allowed",
            (created_at, f"-{edit_hours} hours"),
        ).fetchone()
        return bool(row["allowed"]) if row else False

    @staticmethod
    def save_feedback(
        student_id: int,
        assignment_id: int,
        course_id: int,
        semester: str,
        scores: list[int],
        comments: str,
        feedback_id: int | None = None,
    ) -> None:
        """Insert or update feedback record."""
        db = get_db()
        if feedback_id:
            db.execute(
                """UPDATE feedback SET assignment_id = ?, teaching_quality = ?,
                   course_content = ?, punctuality = ?, comments = ?, updated_at = datetime('now')
                   WHERE feedback_id = ? AND student_id = ?""",
                (assignment_id, *scores, comments, feedback_id, student_id),
            )
        else:
            db.execute(
                """INSERT INTO feedback
                   (student_id, course_id, assignment_id, semester, teaching_quality,
                    course_content, punctuality, comments)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, course_id, assignment_id, semester, *scores, comments),
            )
        db.commit()

    @staticmethod
    def delete_feedback(feedback_id: int, student_id: int) -> None:
        """Delete feedback record owned by student."""
        db = get_db()
        db.execute(
            "DELETE FROM feedback WHERE feedback_id = ? AND student_id = ?",
            (feedback_id, student_id),
        )
        db.commit()

    @staticmethod
    def get_custom_form_for_student(form_id: int, student_id: int) -> sqlite3.Row | None:
        """Fetch custom form ensuring student is enrolled in the course."""
        db = get_db()
        return db.execute(
            """SELECT ff.*, c.course_code, c.course_name, ca.semester, u.full_name AS faculty_name
               FROM feedback_forms ff
               JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
               JOIN courses c ON c.course_id = ca.course_id
               JOIN faculty fac ON fac.faculty_id = ca.faculty_id
               JOIN users u ON u.user_id = fac.faculty_id
               JOIN student_courses sc ON sc.course_id = ca.course_id AND sc.semester = ca.semester
               WHERE ff.form_id = ? AND sc.student_id = ?""",
            (form_id, student_id),
        ).fetchone()

    @staticmethod
    def has_submitted_form(form_id: int, student_id: int) -> bool:
        """Check if student has already responded to this form."""
        db = get_db()
        row = db.execute(
            "SELECT 1 FROM form_responses WHERE form_id = ? AND student_id = ? LIMIT 1",
            (form_id, student_id),
        ).fetchone()
        return row is not None

    @staticmethod
    def get_form_questions(form_id: int) -> list[sqlite3.Row]:
        """Fetch ordered questions for a custom form."""
        db = get_db()
        return db.execute(
            "SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num ASC",
            (form_id,),
        ).fetchall()

    @staticmethod
    def save_form_responses(responses: list[tuple[int, int, int, int | None, str]]) -> None:
        """Save a batch of form responses."""
        db = get_db()
        for item in responses:
            db.execute(
                """INSERT INTO form_responses (form_id, student_id, question_id, rating_value, text_value)
                   VALUES (?, ?, ?, ?, ?)""",
                item,
            )
        db.commit()
