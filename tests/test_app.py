import os
import tempfile
import unittest

from feedback_app import create_app


class FeedbackApplicationTests(unittest.TestCase):
    def setUp(self):
        handle, self.database_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(handle)
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
            "DATABASE": self.database_path,
            "FEEDBACK_EDIT_HOURS": 24,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.database_path)

    def login(self, email, password="DemoPass123!"):
        return self.client.post("/auth/login", data={"email": email, "password": password})

    def test_student_can_submit_feedback_once(self):
        self.login("student@feedback.local")
        response = self.client.post("/student/feedback/1", data={
            "teaching_quality": "5", "course_content": "4", "punctuality": "5",
            "comments": "Clear explanations",
        })
        self.assertEqual(response.status_code, 302)
        duplicate = self.client.post("/student/feedback/1", data={
            "teaching_quality": "5", "course_content": "4", "punctuality": "5",
        })
        self.assertEqual(duplicate.status_code, 302)
        with self.app.app_context():
            from feedback_app.db import get_db
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM feedback").fetchone()[0], 1)

    def test_invalid_rating_is_not_saved(self):
        self.login("student@feedback.local")
        response = self.client.post("/student/feedback/1", data={
            "teaching_quality": "9", "course_content": "4", "punctuality": "5",
        })
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            from feedback_app.db import get_db
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM feedback").fetchone()[0], 0)

    def test_faculty_sees_anonymous_feedback_only(self):
        self.login("student@feedback.local")
        self.client.post("/student/feedback/1", data={
            "teaching_quality": "5", "course_content": "4", "punctuality": "5",
            "comments": "Useful course",
        })
        self.client.post("/auth/logout", follow_redirects=True)
        self.login("faculty@feedback.local")
        response = self.client.get("/faculty/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Useful course", response.data)
        self.assertNotIn(b"Sam Student", response.data)

    def test_role_access_and_admin_csv(self):
        self.login("student@feedback.local")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)
        self.client.post("/auth/logout", follow_redirects=True)
        self.login("admin@feedback.local")
        self.assertEqual(self.client.get("/admin/reports").status_code, 200)
        csv_response = self.client.get("/admin/reports/export/course.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(b"Course code", csv_response.data)

    def test_reports_include_faculty_and_semester_averages(self):
        self.login("student@feedback.local")
        self.client.post("/student/feedback/1", data={
            "teaching_quality": "5", "course_content": "4", "punctuality": "3",
        })
        self.client.post("/auth/logout")
        self.login("admin@feedback.local")
        response = self.client.get("/admin/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Average rating by faculty", response.data)
        self.assertIn(b"Average rating by semester", response.data)
        faculty_csv = self.client.get("/admin/reports/export/faculty.csv")
        self.assertIn(b"Faculty,Semester,Responses,Average rating", faculty_csv.data)

    def test_admin_dashboard_and_faculty_profile_edit(self):
        self.login("admin@feedback.local")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 200)
        response = self.client.post("/admin/users/2/edit", data={
            "full_name": "Dr. Ada Updated", "email": "faculty@feedback.local",
            "profile_code": "FAC-002", "department": "Computer Science",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            from feedback_app.db import get_db
            row = get_db().execute(
                "SELECT employee_number FROM faculty WHERE faculty_id = 2"
            ).fetchone()
            self.assertEqual(row["employee_number"], "FAC-002")

    def test_registration_validates_and_hashes_password(self):
        response = self.client.post("/auth/register", data={
            "full_name": "Taylor Student", "email": "taylor@example.edu",
            "student_number": "STU-009", "department": "Biology", "password": "SecurePass9",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            from feedback_app.db import get_db
            row = get_db().execute("SELECT password_hash FROM users WHERE email = ?",
                                   ("taylor@example.edu",)).fetchone()
            self.assertTrue(row["password_hash"].startswith("scrypt:"))

    def test_login_invalid_credentials_shows_error(self):
        response = self.client.post("/auth/login", data={
            "email": "student@feedback.local", "password": "WrongPassword!"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email or password is incorrect", response.data)

    def test_login_inactive_user_rejected(self):
        with self.app.app_context():
            from feedback_app.db import get_db
            db = get_db()
            db.execute("UPDATE users SET is_active = 0 WHERE email = 'student@feedback.local'")
            db.commit()

        response = self.client.post("/auth/login", data={
            "email": "student@feedback.local", "password": "DemoPass123!"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This account has been deactivated", response.data)

    def test_login_remember_me_and_role_redirect(self):
        response = self.client.post("/auth/login", data={
            "email": "admin@feedback.local",
            "password": "DemoPass123!",
            "remember": "1"
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()

