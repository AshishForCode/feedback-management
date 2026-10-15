import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.base import BaseTestCase


class FacultyTests(BaseTestCase):
    """Test suite for faculty workflows, anonymous summaries, and custom evaluation form management."""

    def test_faculty_sees_anonymous_feedback_only(self):
        # Student submits feedback
        self.login("student@feedback.local")
        self.client.post("/student/feedback/1", data={
            "teaching_quality": "5",
            "course_content": "4",
            "punctuality": "5",
            "comments": "Useful course, very inspiring.",
        })
        self.logout()

        # Faculty logs in
        self.login("faculty@feedback.local")
        response = self.client.get("/faculty/dashboard")
        self.assertEqual(response.status_code, 200)

        # Comment is displayed, but student name or number is strictly excluded
        self.assertIn(b"Useful course, very inspiring.", response.data)
        self.assertNotIn(b"Sam Student", response.data)
        self.assertNotIn(b"STU-001", response.data)

    def test_faculty_can_create_and_manage_custom_forms(self):
        self.login("faculty@feedback.local")

        # 1. Create form
        create_res = self.client.post("/faculty/forms/create", data={
            "assignment_id": "1",
            "title": "Module 1 Review",
            "instructions": "Please answer honestly.",
            "question_text[]": ["Clarity of concepts", "Did you attend labs?", "General comments"],
            "question_type[]": ["rating", "yes_no", "text"],
        })
        self.assertEqual(create_res.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            form = get_db().execute("SELECT * FROM feedback_forms WHERE title = 'Module 1 Review'").fetchone()
            self.assertIsNotNone(form)
            form_id = form["form_id"]

        # 2. Edit form
        edit_page = self.client.get(f"/faculty/forms/{form_id}/edit")
        self.assertEqual(edit_page.status_code, 200)

        edit_res = self.client.post(f"/faculty/forms/{form_id}/edit", data={
            "title": "Module 1 Review (Updated)",
            "instructions": "Updated instructions.",
            "is_active": "1",
            "question_text[]": ["Rate concepts (1-5)", "Attended labs?", "Feedback comments"],
            "question_type[]": ["rating", "yes_no", "text"],
        })
        self.assertEqual(edit_res.status_code, 302)

        # 3. Toggle form active/closed
        toggle_res = self.client.post(f"/faculty/forms/{form_id}/toggle")
        self.assertEqual(toggle_res.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            is_active = get_db().execute(
                "SELECT is_active FROM feedback_forms WHERE form_id = ?",
                (form_id,),
            ).fetchone()[0]
            self.assertEqual(is_active, 0)


if __name__ == "__main__":
    unittest.main()
