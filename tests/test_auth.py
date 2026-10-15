import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.base import BaseTestCase


class AuthTests(BaseTestCase):
    """Test suite for authentication workflows: registration, login, logout, and status checks."""

    def test_registration_validates_and_hashes_password(self):
        response = self.client.post("/auth/register", data={
            "full_name": "Taylor Student",
            "email": "taylor@example.edu",
            "student_number": "STU-009",
            "department": "Biology",
            "password": "SecurePass9",
        })
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            row = get_db().execute(
                "SELECT password_hash FROM users WHERE email = ?",
                ("taylor@example.edu",),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertTrue(row["password_hash"].startswith("scrypt:"))

    def test_login_invalid_credentials_shows_error(self):
        response = self.client.post("/auth/login", data={
            "email": "student@feedback.local",
            "password": "WrongPassword!",
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
            "email": "student@feedback.local",
            "password": "DemoPass123!",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This account has been deactivated", response.data)

    def test_login_remember_me_and_role_redirect(self):
        response = self.login("admin@feedback.local", "DemoPass123!", remember=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
