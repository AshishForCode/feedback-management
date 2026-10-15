"""Faculty Repository: Database access layer for faculty course analytics, custom forms, and responses."""

import sqlite3
from typing import Any
from feedback_app.db import get_db


class FacultyRepository:
    """Encapsulates database operations for faculty dashboards, anonymous feedback, and custom forms."""

    @staticmethod
    def get_assigned_courses_summary(faculty_id: int) -> list[sqlite3.Row]:
        """Fetch all course assignments for a faculty member with aggregated ratings and response counts."""
        db = get_db()
        return db.execute(
            """SELECT ca.assignment_id, ca.semester, c.course_code, c.course_name,
                      COUNT(f.feedback_id) AS response_count,
                      ROUND(AVG(f.teaching_quality), 2) AS teaching_average,
                      ROUND(AVG(f.course_content), 2) AS content_average,
                      ROUND(AVG(f.punctuality), 2) AS punctuality_average,
                      ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2)
                        AS overall_average
               FROM course_assignments ca
               JOIN courses c ON c.course_id = ca.course_id
               LEFT JOIN feedback f ON f.assignment_id = ca.assignment_id
               WHERE ca.faculty_id = ?
               GROUP BY ca.assignment_id, ca.semester, c.course_code, c.course_name
               ORDER BY ca.semester DESC, c.course_code""",
            (faculty_id,),
        ).fetchall()

    @staticmethod
    def get_forms_summary(faculty_id: int) -> list[sqlite3.Row]:
        """Fetch all custom feedback forms created by the faculty member."""
        db = get_db()
        return db.execute(
            """SELECT ff.form_id, ff.title, ff.instructions, ff.is_active, ff.created_at,
                      ca.assignment_id, ca.semester, c.course_code, c.course_name,
                      COUNT(DISTINCT fr.student_id) AS response_count,
                      (SELECT COUNT(*) FROM form_questions fq WHERE fq.form_id = ff.form_id) AS question_count
               FROM feedback_forms ff
               JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
               JOIN courses c ON c.course_id = ca.course_id
               LEFT JOIN form_responses fr ON fr.form_id = ff.form_id
               WHERE ff.faculty_id = ?
               GROUP BY ff.form_id, ff.title, ff.instructions, ff.is_active, ff.created_at,
                        ca.assignment_id, ca.semester, c.course_code, c.course_name
               ORDER BY ff.created_at DESC""",
            (faculty_id,),
        ).fetchall()

    @staticmethod
    def get_anonymous_comments(faculty_id: int) -> list[sqlite3.Row]:
        """Fetch feedback comments without any student identities."""
        db = get_db()
        return db.execute(
            """SELECT c.course_code, c.course_name, ca.semester, f.comments, f.created_at
               FROM feedback f
               JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
               JOIN courses c ON c.course_id = f.course_id
               WHERE ca.faculty_id = ? AND trim(f.comments) != ''
               ORDER BY f.created_at DESC""",
            (faculty_id,),
        ).fetchall()

    @staticmethod
    def get_teaching_assignments(faculty_id: int) -> list[sqlite3.Row]:
        """Fetch all course assignments for faculty member to select when creating forms."""
        db = get_db()
        return db.execute(
            """SELECT ca.assignment_id, ca.semester, c.course_code, c.course_name
               FROM course_assignments ca
               JOIN courses c ON c.course_id = ca.course_id
               WHERE ca.faculty_id = ?
               ORDER BY ca.semester DESC, c.course_code""",
            (faculty_id,),
        ).fetchall()

    @staticmethod
    def get_form_by_id(form_id: int, faculty_id: int) -> sqlite3.Row | None:
        """Fetch a specific custom form owned by the faculty member."""
        db = get_db()
        return db.execute(
            """SELECT ff.*, ca.semester, c.course_code, c.course_name
               FROM feedback_forms ff
               JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
               JOIN courses c ON c.course_id = ca.course_id
               WHERE ff.form_id = ? AND ff.faculty_id = ?""",
            (form_id, faculty_id),
        ).fetchone()

    @staticmethod
    def create_custom_form(
        assignment_id: int,
        faculty_id: int,
        title: str,
        instructions: str,
        questions: list[tuple[str, str]],
    ) -> int:
        """Create a new custom feedback form along with its ordered questions."""
        db = get_db()
        cursor = db.execute(
            """INSERT INTO feedback_forms (assignment_id, faculty_id, title, instructions, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (assignment_id, faculty_id, title, instructions),
        )
        form_id = cursor.lastrowid
        for idx, (q_text, q_type) in enumerate(questions, start=1):
            db.execute(
                """INSERT INTO form_questions (form_id, question_text, question_type, order_num)
                   VALUES (?, ?, ?, ?)""",
                (form_id, q_text, q_type, idx),
            )
        db.commit()
        return form_id

    @staticmethod
    def update_custom_form(
        form_id: int,
        title: str,
        instructions: str,
        questions: list[tuple[str, str]],
    ) -> None:
        """Update form details and replace questions atomically."""
        db = get_db()
        db.execute(
            "UPDATE feedback_forms SET title = ?, instructions = ? WHERE form_id = ?",
            (title, instructions, form_id),
        )
        db.execute("DELETE FROM form_questions WHERE form_id = ?", (form_id,))
        for idx, (q_text, q_type) in enumerate(questions, start=1):
            db.execute(
                """INSERT INTO form_questions (form_id, question_text, question_type, order_num)
                   VALUES (?, ?, ?, ?)""",
                (form_id, q_text, q_type, idx),
            )
        db.commit()

    @staticmethod
    def toggle_form_active(form_id: int, faculty_id: int) -> int | None:
        """Toggle active/closed state of a custom form. Returns new state (0 or 1), or None if not found."""
        db = get_db()
        form = db.execute(
            "SELECT is_active FROM feedback_forms WHERE form_id = ? AND faculty_id = ?",
            (form_id, faculty_id),
        ).fetchone()
        if form is None:
            return None
        new_status = 0 if form["is_active"] else 1
        db.execute("UPDATE feedback_forms SET is_active = ? WHERE form_id = ?", (new_status, form_id))
        db.commit()
        return new_status

    @staticmethod
    def delete_custom_form(form_id: int, faculty_id: int) -> bool:
        """Delete a custom form owned by the faculty member."""
        db = get_db()
        cursor = db.execute(
            "DELETE FROM feedback_forms WHERE form_id = ? AND faculty_id = ?",
            (form_id, faculty_id),
        )
        db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def get_form_questions(form_id: int) -> list[sqlite3.Row]:
        """Fetch ordered questions for a form."""
        db = get_db()
        return db.execute(
            "SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num ASC",
            (form_id,),
        ).fetchall()

    @staticmethod
    def get_form_response_count(form_id: int) -> int:
        """Fetch distinct student count who completed this form."""
        db = get_db()
        row = db.execute(
            "SELECT COUNT(DISTINCT student_id) FROM form_responses WHERE form_id = ?",
            (form_id,),
        ).fetchone()
        return row[0] if row else 0

    @staticmethod
    def get_rating_question_stats(question_id: int) -> tuple[Any, int, dict[int, int]]:
        """Compute average, total, and frequency distribution for a rating question."""
        db = get_db()
        stats = db.execute(
            """SELECT ROUND(AVG(rating_value), 2) AS average, COUNT(rating_value) AS total
               FROM form_responses WHERE question_id = ? AND rating_value IS NOT NULL""",
            (question_id,),
        ).fetchone()
        distribution = {}
        for score in range(1, 6):
            cnt = db.execute(
                "SELECT COUNT(*) FROM form_responses WHERE question_id = ? AND rating_value = ?",
                (question_id, score),
            ).fetchone()[0]
            distribution[score] = cnt
        average = stats["average"] if stats and stats["average"] is not None else "—"
        total = stats["total"] if stats else 0
        return average, total, distribution

    @staticmethod
    def get_yes_no_question_stats(question_id: int) -> tuple[int, int, int, int, int]:
        """Compute yes/no counts, total, and percentages."""
        db = get_db()
        yes_cnt = db.execute(
            "SELECT COUNT(*) FROM form_responses WHERE question_id = ? AND (text_value = 'Yes' OR text_value = 'yes')",
            (question_id,),
        ).fetchone()[0]
        no_cnt = db.execute(
            "SELECT COUNT(*) FROM form_responses WHERE question_id = ? AND (text_value = 'No' OR text_value = 'no')",
            (question_id,),
        ).fetchone()[0]
        total = yes_cnt + no_cnt
        yes_pct = round((yes_cnt / total) * 100) if total > 0 else 0
        no_pct = round((no_cnt / total) * 100) if total > 0 else 0
        return yes_cnt, no_cnt, total, yes_pct, no_pct

    @staticmethod
    def get_text_question_comments(question_id: int) -> list[sqlite3.Row]:
        """Fetch anonymous text comments for a question."""
        db = get_db()
        return db.execute(
            """SELECT text_value, created_at FROM form_responses
               WHERE question_id = ? AND trim(text_value) != ''
               ORDER BY created_at DESC""",
            (question_id,),
        ).fetchall()
