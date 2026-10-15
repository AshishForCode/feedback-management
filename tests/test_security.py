import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.base import BaseTestCase


class SecurityTests(BaseTestCase):
    """Test suite for role-based access control, authentication redirects, and route security."""

    def test_unauthenticated_access_redirects_to_login(self):
        # Root redirects to login
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 302)
        self.assertIn("/auth/login", res_root.headers["Location"])

        # Protected student endpoint redirects to login
        res_student = self.client.get("/student/dashboard")
        self.assertEqual(res_student.status_code, 302)
        self.assertIn("/auth/login", res_student.headers["Location"])

        # Protected faculty endpoint redirects to login
        res_fac = self.client.get("/faculty/dashboard")
        self.assertEqual(res_fac.status_code, 302)
        self.assertIn("/auth/login", res_fac.headers["Location"])

        # Protected admin endpoint redirects to login
        res_adm = self.client.get("/admin/dashboard")
        self.assertEqual(res_adm.status_code, 302)
        self.assertIn("/auth/login", res_adm.headers["Location"])

    def test_public_endpoints_accessible_without_auth(self):
        self.assertEqual(self.client.get("/auth/login").status_code, 200)
        self.assertEqual(self.client.get("/auth/register").status_code, 200)
        res_static = self.client.get("/static/style.css")
        self.assertEqual(res_static.status_code, 200)
        res_static.close()

    def test_health_check_endpoint(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertEqual(json_data["status"], "healthy")
        self.assertEqual(json_data["database"], "connected")

    def test_role_boundaries_are_enforced(self):
        # Logged in student cannot access admin area
        self.login("student@feedback.local")
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 403)

        # Logged in student cannot access faculty form creation
        res_form = self.client.get("/faculty/forms/create")
        self.assertEqual(res_form.status_code, 403)


if __name__ == "__main__":
    unittest.main()
