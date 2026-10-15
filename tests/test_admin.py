import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.base import BaseTestCase


class AdminTests(BaseTestCase):
    """Test suite for administrator functions: user management, reporting, and CSV exports."""

    def test_admin_dashboard_and_faculty_profile_edit(self):
        self.login("admin@feedback.local")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 200)

        response = self.client.post("/admin/users/2/edit", data={
            "full_name": "Dr. Ada Updated",
            "email": "faculty@feedback.local",
            "profile_code": "FAC-002",
            "department": "Computer Science",
        })
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            row = get_db().execute(
                "SELECT employee_number FROM faculty WHERE faculty_id = 2"
            ).fetchone()
            self.assertEqual(row["employee_number"], "FAC-002")

    def test_reports_and_csv_exports(self):
        # 1. Student submits feedback to populate metrics
        self.login("student@feedback.local")
        self.client.post("/student/feedback/1", data={
            "teaching_quality": "5",
            "course_content": "4",
            "punctuality": "3",
        })
        self.logout()

        # 2. Admin inspects reports
        self.login("admin@feedback.local")
        response = self.client.get("/admin/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Average rating by faculty", response.data)
        self.assertIn(b"Average rating by semester", response.data)

        # 3. Test course CSV export
        course_csv = self.client.get("/admin/reports/export/course.csv")
        self.assertEqual(course_csv.status_code, 200)
        self.assertIn(b"Course code", course_csv.data)

        # 4. Test faculty CSV export
        faculty_csv = self.client.get("/admin/reports/export/faculty.csv")
        self.assertEqual(faculty_csv.status_code, 200)
        self.assertIn(b"Faculty,Semester,Responses,Average rating", faculty_csv.data)


if __name__ == "__main__":
    unittest.main()
