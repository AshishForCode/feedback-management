import csv
import io
import re
import sqlite3

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from .db import get_db
from .decorators import roles_required

bp = Blueprint("admin", __name__, url_prefix="/admin")
SEMESTER_PATTERN = re.compile(r"^\d{4}-(Spring|Summer|Fall)$")


def _valid_semester(value):
    return bool(SEMESTER_PATTERN.fullmatch(value))


@bp.get("/dashboard")
@roles_required("admin")
def dashboard():
    db = get_db()
    users = db.execute(
        """SELECT u.user_id, u.full_name, u.email, u.role,
                  COALESCE(s.student_number, f.employee_number, '') AS profile_code,
                  COALESCE(s.department, f.department, '') AS department
           FROM users u LEFT JOIN students s ON s.student_id = u.user_id
           LEFT JOIN faculty f ON f.faculty_id = u.user_id ORDER BY u.role, u.full_name"""
    ).fetchall()
    courses = db.execute("SELECT * FROM courses ORDER BY course_code").fetchall()
    faculty_members = db.execute(
        """SELECT f.faculty_id, u.full_name, f.employee_number
           FROM faculty f JOIN users u ON u.user_id = f.faculty_id
           WHERE u.is_active = 1 ORDER BY u.full_name"""
    ).fetchall()
    assignments = db.execute(
        """SELECT ca.assignment_id, ca.semester, c.course_code, c.course_name, u.full_name AS faculty_name
           FROM course_assignments ca JOIN courses c ON c.course_id = ca.course_id
           JOIN faculty f ON f.faculty_id = ca.faculty_id JOIN users u ON u.user_id = f.faculty_id
           ORDER BY ca.semester DESC, c.course_code"""
    ).fetchall()
    students = db.execute(
        """SELECT s.student_id, u.full_name, s.student_number
           FROM students s JOIN users u ON u.user_id = s.student_id
           WHERE u.is_active = 1 ORDER BY u.full_name"""
    ).fetchall()
    return render_template("admin/dashboard.html", users=users, courses=courses,
                           faculty_members=faculty_members, assignments=assignments, students=students)


@bp.post("/users")
@roles_required("admin")
def create_user():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "")
    code = request.form.get("profile_code", "").strip()
    department = request.form.get("department", "").strip()
    password = request.form.get("password", "")
    if role not in {"student", "faculty"}:
        flash("Choose student or faculty for the new account.", "danger")
    elif len(full_name) < 2 or len(full_name) > 100 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("Enter a valid name and email address.", "danger")
    elif not code or len(code) > 30 or not department or len(department) > 80 or len(password) < 8:
        flash("Profile code, department, and a password of at least 8 characters are required.", "danger")
    else:
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                (email, generate_password_hash(password), full_name, role),
            )
            table = "students" if role == "student" else "faculty"
            code_column = "student_number" if role == "student" else "employee_number"
            db.execute(
                f"INSERT INTO {table} (student_id, {code_column}, department) VALUES (?, ?, ?)",
                (cursor.lastrowid, code, department),
            )
            db.commit()
            flash(f"{role.title()} account created.", "success")
        except sqlite3.IntegrityError:
            db.rollback()
            flash("That email or profile code is already in use.", "danger")
    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<int:user_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit_user(user_id):
    db = get_db()
    user = db.execute(
        """SELECT u.user_id, u.full_name, u.email, u.role,
                  COALESCE(s.student_number, f.employee_number, '') AS profile_code,
                  COALESCE(s.department, f.department, '') AS department
           FROM users u LEFT JOIN students s ON s.student_id = u.user_id
           LEFT JOIN faculty f ON f.faculty_id = u.user_id WHERE u.user_id = ?""",
        (user_id,),
    ).fetchone()
    if user is None:
        abort(404)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        code = request.form.get("profile_code", "").strip()
        department = request.form.get("department", "").strip()
        if user["role"] == "admin":
            flash("Administrator profile editing is not available here.", "warning")
        elif len(full_name) < 2 or len(full_name) > 100 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            flash("Enter a valid name and email address.", "danger")
        elif not code or len(code) > 30 or not department or len(department) > 80:
            flash("Profile code and department are required.", "danger")
        else:
            table = "students" if user["role"] == "student" else "faculty"
            code_column = "student_number" if user["role"] == "student" else "employee_number"
            id_column = "student_id" if user["role"] == "student" else "faculty_id"
            try:
                db.execute("UPDATE users SET full_name = ?, email = ? WHERE user_id = ?",
                           (full_name, email, user_id))
                db.execute(f"UPDATE {table} SET {code_column} = ?, department = ? WHERE {id_column} = ?",
                           (code, department, user_id))
                db.commit()
                flash("Account updated.", "success")
                return redirect(url_for("admin.dashboard"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That email or profile code is already in use.", "danger")
        user = dict(user)
        user.update(full_name=full_name, email=email, profile_code=code, department=department)
    return render_template("admin/edit_user.html", user=user)


@bp.post("/users/<int:user_id>/delete")
@roles_required("admin")
def delete_user(user_id):
    if str(user_id) == str(current_user.id):
        flash("You cannot delete the account you are currently using.", "danger")
    else:
        db = get_db()
        db.execute("DELETE FROM users WHERE user_id = ? AND role != 'admin'", (user_id,))
        db.commit()
        flash("Account deleted. Related enrollments and feedback follow the database cascade rules.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/courses")
@roles_required("admin")
def create_course():
    code = request.form.get("course_code", "").strip().upper()
    name = request.form.get("course_name", "").strip()
    department = request.form.get("department", "").strip()
    if not re.fullmatch(r"[A-Z0-9-]{2,15}", code) or not name or len(name) > 120 or not department or len(department) > 80:
        flash("Enter a valid course code, course name, and department.", "danger")
    else:
        try:
            db = get_db()
            db.execute("INSERT INTO courses (course_code, course_name, department) VALUES (?, ?, ?)",
                       (code, name, department))
            db.commit()
            flash("Course created.", "success")
        except sqlite3.IntegrityError:
            flash("That course code already exists.", "danger")
    return redirect(url_for("admin.dashboard"))


@bp.route("/courses/<int:course_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit_course(course_id):
    db = get_db()
    course = db.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()
    if course is None:
        abort(404)
    if request.method == "POST":
        code = request.form.get("course_code", "").strip().upper()
        name = request.form.get("course_name", "").strip()
        department = request.form.get("department", "").strip()
        if not re.fullmatch(r"[A-Z0-9-]{2,15}", code) or not name or len(name) > 120 or not department:
            flash("Enter a valid course code, name, and department.", "danger")
        else:
            try:
                db.execute("UPDATE courses SET course_code = ?, course_name = ?, department = ? WHERE course_id = ?",
                           (code, name, department, course_id))
                db.commit()
                flash("Course updated.", "success")
                return redirect(url_for("admin.dashboard"))
            except sqlite3.IntegrityError:
                flash("That course code already exists.", "danger")
            course = dict(course)
            course.update(course_code=code, course_name=name, department=department)
    return render_template("admin/edit_course.html", course=course)


@bp.post("/courses/<int:course_id>/delete")
@roles_required("admin")
def delete_course(course_id):
    db = get_db()
    db.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
    db.commit()
    flash("Course deleted, including linked assignments, enrollments, and feedback.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/assignments")
@roles_required("admin")
def create_assignment():
    faculty_id = request.form.get("faculty_id", type=int)
    course_id = request.form.get("course_id", type=int)
    semester = request.form.get("semester", "").strip()
    if not faculty_id or not course_id or not _valid_semester(semester):
        flash("Select a faculty member and course, and use semester format YYYY-Term.", "danger")
    else:
        try:
            db = get_db()
            db.execute("INSERT INTO course_assignments (faculty_id, course_id, semester) VALUES (?, ?, ?)",
                       (faculty_id, course_id, semester))
            db.commit()
            flash("Faculty assigned to course.", "success")
        except sqlite3.IntegrityError:
            flash("Assignment is invalid or already exists.", "danger")
    return redirect(url_for("admin.dashboard"))


@bp.post("/assignments/<int:assignment_id>/delete")
@roles_required("admin")
def delete_assignment(assignment_id):
    db = get_db()
    db.execute("DELETE FROM course_assignments WHERE assignment_id = ?", (assignment_id,))
    db.commit()
    flash("Assignment deleted. Feedback attached to that assignment is also removed.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/enrollments")
@roles_required("admin")
def enroll_student():
    student_id = request.form.get("student_id", type=int)
    course_id = request.form.get("course_id", type=int)
    semester = request.form.get("semester", "").strip()
    if not student_id or not course_id or not _valid_semester(semester):
        flash("Select a student and course, and use semester format YYYY-Term.", "danger")
    else:
        try:
            db = get_db()
            db.execute("INSERT INTO student_courses (student_id, course_id, semester) VALUES (?, ?, ?)",
                       (student_id, course_id, semester))
            db.commit()
            flash("Student enrolled in course.", "success")
        except sqlite3.IntegrityError:
            flash("Enrollment is invalid or already exists.", "danger")
    return redirect(url_for("admin.dashboard"))


@bp.get("/reports")
@roles_required("admin")
def reports():
    semester = request.args.get("semester", "").strip()
    if semester and not _valid_semester(semester):
        abort(400)
    where_sql = "WHERE f.semester = ?" if semester else ""
    parameters = (semester,) if semester else ()
    db = get_db()
    by_course = db.execute(
        f"""SELECT c.course_code, c.course_name, f.semester, COUNT(*) AS responses,
                   ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
            FROM feedback f JOIN courses c ON c.course_id = f.course_id {where_sql}
            GROUP BY c.course_id, f.semester ORDER BY f.semester DESC, c.course_code""",
        parameters,
    ).fetchall()
    by_faculty = db.execute(
        f"""SELECT u.full_name AS faculty_name, f.semester, COUNT(*) AS responses,
                   ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
            FROM feedback f JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
            JOIN faculty fac ON fac.faculty_id = ca.faculty_id JOIN users u ON u.user_id = fac.faculty_id
            {where_sql}
            GROUP BY fac.faculty_id, f.semester
            ORDER BY f.semester DESC, u.full_name""",
        parameters,
    ).fetchall()
    by_semester = db.execute(
        """SELECT semester, COUNT(*) AS responses,
                  ROUND(AVG((teaching_quality + course_content + punctuality) / 3.0), 2) AS average
           FROM feedback GROUP BY semester ORDER BY semester DESC"""
    ).fetchall()
    all_feedback = db.execute(
        f"""SELECT f.*, c.course_code, c.course_name, student.full_name AS student_name,
                   faculty_user.full_name AS faculty_name
            FROM feedback f JOIN courses c ON c.course_id = f.course_id
            JOIN users student ON student.user_id = f.student_id
            JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
            JOIN faculty fac ON fac.faculty_id = ca.faculty_id
            JOIN users faculty_user ON faculty_user.user_id = fac.faculty_id
            {where_sql} ORDER BY f.created_at DESC""",
        parameters,
    ).fetchall()
    semesters = db.execute("SELECT DISTINCT semester FROM feedback ORDER BY semester DESC").fetchall()
    return render_template("admin/reports.html", by_course=by_course, by_faculty=by_faculty,
                           by_semester=by_semester, all_feedback=all_feedback,
                           semesters=semesters, selected_semester=semester)


@bp.get("/reports/export/<category>.csv")
@roles_required("admin")
def export_report(category):
    semester = request.args.get("semester", "").strip()
    if category not in {"course", "faculty"} or (semester and not _valid_semester(semester)):
        abort(400)
    db = get_db()
    semester_clause = "AND f.semester = ?" if semester else ""
    params = (semester,) if semester else ()
    if category == "course":
        rows = db.execute(
            f"""SELECT c.course_code, c.course_name, f.semester, COUNT(*) AS responses,
                       ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
                FROM feedback f JOIN courses c ON c.course_id = f.course_id WHERE 1=1 {semester_clause}
                GROUP BY c.course_id, f.semester ORDER BY f.semester DESC, c.course_code""", params,
        ).fetchall()
        headers = ["Course code", "Course name", "Semester", "Responses", "Average rating"]
        fields = ("course_code", "course_name", "semester", "responses", "average")
    else:
        rows = db.execute(
            f"""SELECT u.full_name AS faculty_name, f.semester, COUNT(*) AS responses,
                       ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2) AS average
                FROM feedback f JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
                JOIN faculty fac ON fac.faculty_id = ca.faculty_id JOIN users u ON u.user_id = fac.faculty_id
                WHERE 1=1 {semester_clause}
                GROUP BY fac.faculty_id, f.semester ORDER BY f.semester DESC, u.full_name""", params,
        ).fetchall()
        headers = ["Faculty", "Semester", "Responses", "Average rating"]
        fields = ("faculty_name", "semester", "responses", "average")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        values = []
        for field in fields:
            value = str(row[field])
            values.append("'" + value if value.startswith(("=", "+", "-", "@")) else value)
        writer.writerow(values)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=feedback-{category}-report.csv"
    return response
