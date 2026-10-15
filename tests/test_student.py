import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.base import BaseTestCase


class StudentTests(BaseTestCase):
    """Test suite for student feedback submissions, validation rules, and custom form participation."""

    def test_student_can_submit_feedback_once(self):
        self.login("student@feedback.local")
        response = self.client.post("/student/feedback/1", data={
            "teaching_quality": "5",
            "course_content": "4",
            "punctuality": "5",
            "comments": "Clear explanations and great pace.",
        })
        self.assertEqual(response.status_code, 302)

        # Attempting duplicate submission on the same course assignment is rejected
        duplicate = self.client.post("/student/feedback/1", data={
            "teaching_quality": "5",
            "course_content": "4",
            "punctuality": "5",
        })
        self.assertEqual(duplicate.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            count = get_db().execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            self.assertEqual(count, 1)

    def test_invalid_rating_is_not_saved(self):
        self.login("student@feedback.local")
        # Rating 9 is outside allowed range (1-5)
        response = self.client.post("/student/feedback/1", data={
            "teaching_quality": "9",
            "course_content": "4",
            "punctuality": "5",
        })
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            from feedback_app.db import get_db
            count = get_db().execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            self.assertEqual(count, 0)

    def test_student_can_fill_custom_form(self):
        # 1. Setup a custom form as faculty
        self.login("faculty@feedback.local")
        self.client.post("/faculty/forms/create", data={
            "assignment_id": "1",
            "title": "Midterm Checkpoint",
            "instructions": "Help us improve the second half.",
            "question_text[]": ["Pacing feedback", "Extra office hours needed?"],
            "question_type[]": ["rating", "yes_no"],
        })
        self.logout()

        with self.app.app_context():
            from feedback_app.db import get_db
            form = get_db().execute("SELECT * FROM feedback_forms WHERE title = 'Midterm Checkpoint'").fetchone()
            form_id = form["form_id"]
            questions = get_db().execute("SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num", (form_id,)).fetchall()
            q1_id, q2_id = questions[0]["question_id"], questions[1]["question_id"]

        # 2. Student logs in and completes form
        self.login("student@feedback.local")
        dash = self.client.get("/student/dashboard")
        self.assertEqual(dash.status_code, 200)
        self.assertIn(b"Midterm Checkpoint", dash.data)

        fill_page = self.client.get(f"/student/forms/{form_id}")
        self.assertEqual(fill_page.status_code, 200)

        submit = self.client.post(f"/student/forms/{form_id}", data={
            f"question_{q1_id}": "5",
            f"question_{q2_id}": "No",
        })
        self.assertEqual(submit.status_code, 302)

        # Duplicate submission is blocked
        dup = self.client.post(f"/student/forms/{form_id}", data={
            f"question_{q1_id}": "4",
            f"question_{q2_id}": "Yes",
        })
        self.assertEqual(dup.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            resp_count = get_db().execute(
                "SELECT COUNT(DISTINCT student_id) FROM form_responses WHERE form_id = ?",
                (form_id,),
            ).fetchone()[0]
            self.assertEqual(resp_count, 1)


if __name__ == "__main__":
    unittest.main()
