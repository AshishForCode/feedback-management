"""Admin Blueprint: Presentation layer for user management, course setup, and reports."""

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user

from .decorators import roles_required
from .repositories.admin_repository import AdminRepository
from .services.admin_service import AdminService

bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_service = AdminService(AdminRepository)


@bp.get("/dashboard")
@roles_required("admin")
def dashboard():
    """Render admin dashboard with accounts, courses, faculty, assignments, and students."""
    users, courses, faculty_members, assignments, students = AdminRepository.get_dashboard_summary()
    return render_template(
        "admin/dashboard.html",
        users=users,
        courses=courses,
        faculty_members=faculty_members,
        assignments=assignments,
        students=students,
    )


@bp.post("/users")
@roles_required("admin")
def create_user():
    """Create a new student or faculty account."""
    _, message, category = admin_service.create_user(request.form)
    flash(message, category)
    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<int:user_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit_user(user_id: int):
    """Edit student or faculty profile details."""
    user = AdminRepository.get_user_by_id(user_id)
    if user is None:
        abort(404)

    if request.method == "POST":
        success, message, category, updated_user = admin_service.update_user(
            user=user,
            user_id=user_id,
            form_data=request.form,
        )
        flash(message, category)
        if success:
            return redirect(url_for("admin.dashboard"))
        return render_template("admin/edit_user.html", user=updated_user)

    return render_template("admin/edit_user.html", user=user)


@bp.post("/users/<int:user_id>/delete")
@roles_required("admin")
def delete_user(user_id: int):
    """Delete a user account (excluding the active administrator)."""
    if str(user_id) == str(current_user.id):
        flash("You cannot delete the account you are currently using.", "danger")
    else:
        AdminRepository.delete_non_admin_user(user_id)
        flash("Account deleted. Related enrollments and feedback follow the database cascade rules.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/courses")
@roles_required("admin")
def create_course():
    """Create a new academic course."""
    _, message, category = admin_service.create_course(request.form)
    flash(message, category)
    return redirect(url_for("admin.dashboard"))


@bp.route("/courses/<int:course_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit_course(course_id: int):
    """Edit course code, title, or department."""
    course = AdminRepository.get_course_by_id(course_id)
    if course is None:
        abort(404)

    if request.method == "POST":
        success, message, category, updated_course = admin_service.update_course(
            course_id=course_id,
            form_data=request.form,
            existing_course=course,
        )
        flash(message, category)
        if success:
            return redirect(url_for("admin.dashboard"))
        return render_template("admin/edit_course.html", course=updated_course)

    return render_template("admin/edit_course.html", course=course)


@bp.post("/courses/<int:course_id>/delete")
@roles_required("admin")
def delete_course(course_id: int):
    """Delete a course and all related assignments, enrollments, and feedback."""
    AdminRepository.delete_course(course_id)
    flash("Course deleted, including linked assignments, enrollments, and feedback.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/assignments")
@roles_required("admin")
def create_assignment():
    """Assign a faculty member to teach a course in a given semester."""
    _, message, category = admin_service.create_assignment(
        faculty_id=request.form.get("faculty_id", type=int),
        course_id=request.form.get("course_id", type=int),
        semester=request.form.get("semester", ""),
    )
    flash(message, category)
    return redirect(url_for("admin.dashboard"))


@bp.post("/assignments/<int:assignment_id>/delete")
@roles_required("admin")
def delete_assignment(assignment_id: int):
    """Delete a course assignment."""
    AdminRepository.delete_assignment(assignment_id)
    flash("Assignment deleted. Feedback attached to that assignment is also removed.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/enrollments")
@roles_required("admin")
def enroll_student():
    """Enroll a student into a course for a given semester."""
    _, message, category = admin_service.enroll_student(
        student_id=request.form.get("student_id", type=int),
        course_id=request.form.get("course_id", type=int),
        semester=request.form.get("semester", ""),
    )
    flash(message, category)
    return redirect(url_for("admin.dashboard"))


@bp.get("/reports")
@roles_required("admin")
def reports():
    """Display system-wide feedback reports grouped by course, faculty, and semester."""
    semester = request.args.get("semester", "").strip()
    if semester and not admin_service.is_valid_semester(semester):
        abort(400)

    by_course, by_faculty, by_semester, all_feedback, semesters = AdminRepository.get_reports_summary(
        semester=semester if semester else None
    )

    return render_template(
        "admin/reports.html",
        by_course=by_course,
        by_faculty=by_faculty,
        by_semester=by_semester,
        all_feedback=all_feedback,
        semesters=semesters,
        selected_semester=semester,
    )


@bp.get("/reports/export/<category>.csv")
@roles_required("admin")
def export_report(category: str):
    """Export course or faculty feedback reports as a CSV download."""
    semester = request.args.get("semester", "").strip()
    if category not in {"course", "faculty"} or (semester and not admin_service.is_valid_semester(semester)):
        abort(400)

    csv_content, filename = admin_service.generate_csv_report(
        category=category,
        semester=semester if semester else None,
    )

    response = make_response(csv_content)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
