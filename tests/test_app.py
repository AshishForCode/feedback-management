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

    def test_unauthenticated_access_redirects_to_login(self):
        # Visiting root / redirects to /auth/login
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 302)
        self.assertIn("/auth/login", res_root.headers["Location"])

        # Direct access to protected student page redirects to /auth/login
        res_student = self.client.get("/student/dashboard")
        self.assertEqual(res_student.status_code, 302)
        self.assertIn("/auth/login", res_student.headers["Location"])

        # Direct access to faculty page redirects to /auth/login
        res_fac = self.client.get("/faculty/dashboard")
        self.assertEqual(res_fac.status_code, 302)
        self.assertIn("/auth/login", res_fac.headers["Location"])

        # Direct access to admin page redirects to /auth/login
        res_adm = self.client.get("/admin/dashboard")
        self.assertEqual(res_adm.status_code, 302)
        self.assertIn("/auth/login", res_adm.headers["Location"])

        # Public auth pages and static assets remain accessible
        self.assertEqual(self.client.get("/auth/login").status_code, 200)
        self.assertEqual(self.client.get("/auth/register").status_code, 200)
        self.assertEqual(self.client.get("/static/style.css").status_code, 200)

    def test_faculty_can_create_custom_form_and_student_can_fill_it(self):
        # 1. Faculty logs in and creates a custom feedback form
        self.login("faculty@feedback.local")
        create_page = self.client.get("/faculty/forms/create")
        self.assertEqual(create_page.status_code, 200)

        post_res = self.client.post("/faculty/forms/create", data={
            "assignment_id": "1",
            "title": "Unit 2 Practical Feedback",
            "instructions": "Be honest about lab pace and explanations.",
            "question_text[]": ["Clarity of recursion demo", "Suggestions for homework"],
            "question_type[]": ["rating", "text"],
        })
        self.assertEqual(post_res.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            db = get_db()
            form = db.execute("SELECT * FROM feedback_forms WHERE title = 'Unit 2 Practical Feedback'").fetchone()
            self.assertIsNotNone(form)
            form_id = form["form_id"]
            questions = db.execute("SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num", (form_id,)).fetchall()
            self.assertEqual(len(questions), 2)
            q1_id = questions[0]["question_id"]
            q2_id = questions[1]["question_id"]

        self.client.post("/auth/logout")

        # 2. Student logs in and fills the custom feedback form
        self.login("student@feedback.local")
        student_dash = self.client.get("/student/dashboard")
        self.assertEqual(student_dash.status_code, 200)
        self.assertIn(b"Unit 2 Practical Feedback", student_dash.data)

        fill_page = self.client.get(f"/student/forms/{form_id}")
        self.assertEqual(fill_page.status_code, 200)
        self.assertIn(b"Clarity of recursion demo", fill_page.data)

        submit_res = self.client.post(f"/student/forms/{form_id}", data={
            f"question_{q1_id}": "5",
            f"question_{q2_id}": "More practice problems on trees please.",
        })
        self.assertEqual(submit_res.status_code, 302)

        # Duplicate submission is blocked
        dup_res = self.client.post(f"/student/forms/{form_id}", data={
            f"question_{q1_id}": "4",
            f"question_{q2_id}": "Duplicate comment",
        })
        self.assertEqual(dup_res.status_code, 302)

        with self.app.app_context():
            from feedback_app.db import get_db
            resp_count = get_db().execute("SELECT COUNT(DISTINCT student_id) FROM form_responses WHERE form_id = ?", (form_id,)).fetchone()[0]
            self.assertEqual(resp_count, 1)

        self.client.post("/auth/logout")

        # 3. Faculty logs back in to view anonymous response analytics
        self.login("faculty@feedback.local")
        view_res = self.client.get(f"/faculty/forms/{form_id}")
        self.assertEqual(view_res.status_code, 200)
        self.assertIn(b"More practice problems on trees please.", view_res.data)
        # Verify student identity is not exposed
        self.assertNotIn(b"Sam Student", view_res.data)
        self.assertNotIn(b"STU-001", view_res.data)

        # Toggle form closed
        toggle_res = self.client.post(f"/faculty/forms/{form_id}/toggle")
        self.assertEqual(toggle_res.status_code, 302)
        with self.app.app_context():
            from feedback_app.db import get_db
            is_active = get_db().execute("SELECT is_active FROM feedback_forms WHERE form_id = ?", (form_id,)).fetchone()[0]
            self.assertEqual(is_active, 0)


if __name__ == "__main__":
    unittest.main()

