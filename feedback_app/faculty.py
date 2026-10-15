"""Faculty Blueprint: Presentation layer for faculty dashboards, anonymous feedback, and custom forms."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .decorators import roles_required
from .repositories.faculty_repository import FacultyRepository
from .services.faculty_service import FacultyService

bp = Blueprint("faculty", __name__, url_prefix="/faculty")
faculty_service = FacultyService(FacultyRepository)


@bp.get("/dashboard")
@roles_required("faculty")
def dashboard():
    """Render faculty dashboard with course summaries, active forms, and anonymous comments."""
    courses = FacultyRepository.get_assigned_courses_summary(current_user.id)
    forms = FacultyRepository.get_forms_summary(current_user.id)
    comments = FacultyRepository.get_anonymous_comments(current_user.id)
    return render_template("faculty/dashboard.html", courses=courses, forms=forms, comments=comments)


@bp.route("/forms/create", methods=("GET", "POST"))
@roles_required("faculty")
def create_form():
    """Create a new custom feedback form for one of the faculty member's course assignments."""
    assignments = FacultyRepository.get_teaching_assignments(current_user.id)
    if not assignments:
        flash("You do not have any course assignments to create forms for.", "warning")
        return redirect(url_for("faculty.dashboard"))

    if request.method == "POST":
        success, message, category = faculty_service.create_form(
            assignment_id=request.form.get("assignment_id", ""),
            faculty_id=current_user.id,
            title=request.form.get("title", ""),
            instructions=request.form.get("instructions", ""),
            question_texts=request.form.getlist("question_text[]"),
            question_types=request.form.getlist("question_type[]"),
            valid_assignments=assignments,
        )
        flash(message, category)
        if success:
            return redirect(url_for("faculty.dashboard"))

        return render_template("faculty/create_form.html", assignments=assignments)

    return render_template("faculty/create_form.html", assignments=assignments)


@bp.route("/forms/<int:form_id>/edit", methods=("GET", "POST"))
@roles_required("faculty")
def edit_form(form_id: int):
    """Edit an existing custom feedback form owned by the faculty member."""
    form = FacultyRepository.get_form_by_id(form_id, current_user.id)
    if form is None:
        abort(404)

    if request.method == "POST":
        success, message, category = faculty_service.update_form(
            form_id=form_id,
            title=request.form.get("title", ""),
            instructions=request.form.get("instructions", ""),
            question_texts=request.form.getlist("question_text[]"),
            question_types=request.form.getlist("question_type[]"),
        )
        flash(message, category)
        if success:
            return redirect(url_for("faculty.dashboard"))
        return redirect(url_for("faculty.edit_form", form_id=form_id))

    questions = FacultyRepository.get_form_questions(form_id)
    return render_template("faculty/edit_form.html", form=form, questions=questions)


@bp.get("/forms/<int:form_id>")
@roles_required("faculty")
def view_form(form_id: int):
    """View anonymous response analytics for a custom feedback form."""
    form = FacultyRepository.get_form_by_id(form_id, current_user.id)
    if form is None:
        abort(404)

    results = faculty_service.compile_form_analytics(form_id)
    response_count = FacultyRepository.get_form_response_count(form_id)

    return render_template(
        "faculty/form_responses.html",
        form=form,
        results=results,
        response_count=response_count,
    )


@bp.post("/forms/<int:form_id>/toggle")
@roles_required("faculty")
def toggle_form(form_id: int):
    """Open or close a custom form for student submissions."""
    new_status = FacultyRepository.toggle_form_active(form_id, current_user.id)
    if new_status is None:
        abort(404)

    status_label = "opened for student responses" if new_status else "closed"
    flash(f"Feedback form has been {status_label}.", "info")
    return redirect(url_for("faculty.dashboard"))


@bp.post("/forms/<int:form_id>/delete")
@roles_required("faculty")
def delete_form(form_id: int):
    """Permanently delete a custom feedback form and its questions/responses."""
    if not FacultyRepository.delete_custom_form(form_id, current_user.id):
        abort(404)

    flash("Feedback form deleted.", "success")
    return redirect(url_for("faculty.dashboard"))
