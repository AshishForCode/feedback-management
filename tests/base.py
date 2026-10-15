import os
import tempfile
import unittest

from feedback_app import create_app
from feedback_app.db import get_db


class BaseTestCase(unittest.TestCase):
    """Base test case managing temporary SQLite lifecycle and test client setup."""

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
        if os.path.exists(self.database_path):
            try:
                os.unlink(self.database_path)
            except PermissionError:
                pass

    def login(self, email="student@feedback.local", password="DemoPass123!", remember=False):
        data = {"email": email, "password": password}
        if remember:
            data["remember"] = "1"
        return self.client.post("/auth/login", data=data)

    def logout(self):
        return self.client.post("/auth/logout", follow_redirects=True)
