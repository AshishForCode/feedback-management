"""Student Blueprint: Presentation layer for student dashboard and course evaluations."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .decorators import roles_required
from .repositories.feedback_repository import FeedbackRepository
from .services.feedback_service import FeedbackService

bp = Blueprint("student", __name__, url_prefix="/student")
feedback_service = FeedbackService(FeedbackRepository)


@bp.get("/dashboard")
@roles_required("student")
def dashboard():
    """Render the student dashboard displaying enrollments, pending forms, and feedback history."""
    courses = FeedbackRepository.get_student_courses(current_user.id)
    history = FeedbackRepository.get_feedback_history(current_user.id)
    forms = FeedbackRepository.get_active_forms_for_student(current_user.id)

    return render_template(
        "student/dashboard.html",
        courses=courses,
        forms=forms,
        history=history,
    )


@bp.route("/feedback/<int:assignment_id>", methods=("GET", "POST"))
@roles_required("student")
def feedback_form(assignment_id: int):
    """View and submit standard anonymous course evaluation feedback."""
    assignment = FeedbackRepository.get_assignment_for_student(assignment_id, current_user.id)
    if assignment is None:
        abort(404)

    feedback = FeedbackRepository.get_feedback_for_course(
        current_user.id, assignment["course_id"], assignment["semester"]
    )
    edit_hours = int(current_app.config.get("FEEDBACK_EDIT_HOURS", 24))
    editable = feedback is None or FeedbackRepository.is_editable(feedback["created_at"], edit_hours)

    if request.method == "POST":
        success, message, category = feedback_service.submit_course_feedback(
            student_id=current_user.id,
            assignment=assignment,
            form_data=request.form,
            existing_feedback=feedback,
            edit_hours=edit_hours,
        )
        flash(message, category)
        if success:
            return redirect(url_for("student.dashboard"))

        # In case of validation errors, re-render form with current context
        return render_template(
            "student/feedback_form.html",
            assignment=assignment,
            feedback=feedback,
            editable=editable,
        )

    return render_template(
        "student/feedback_form.html",
        assignment=assignment,
        feedback=feedback,
        editable=editable,
    )


@bp.post("/feedback/<int:feedback_id>/delete")
@roles_required("student")
def delete_feedback(feedback_id: int):
    """Delete submitted feedback if within the editable window."""
    feedback = FeedbackRepository.get_feedback_by_id(feedback_id, current_user.id)
    if feedback is None:
        abort(404)

    edit_hours = int(current_app.config.get("FEEDBACK_EDIT_HOURS", 24))
    _, message, category = feedback_service.delete_course_feedback(
        feedback=feedback,
        student_id=current_user.id,
        edit_hours=edit_hours,
    )
    flash(message, category)
    return redirect(url_for("student.dashboard"))


@bp.route("/forms/<int:form_id>", methods=("GET", "POST"))
@roles_required("student")
def fill_form(form_id: int):
    """View and submit responses to custom faculty-created evaluation forms."""
    form = FeedbackRepository.get_custom_form_for_student(form_id, current_user.id)
    if form is None:
        abort(404)

    if not form["is_active"]:
        flash("This feedback form is currently closed.", "warning")
        return redirect(url_for("student.dashboard"))

    already_submitted = FeedbackRepository.has_submitted_form(form_id, current_user.id)
    questions = FeedbackRepository.get_form_questions(form_id)

    if request.method == "POST":
        success, message, category = feedback_service.submit_custom_form(
            form_id=form_id,
            student_id=current_user.id,
            questions=questions,
            form_data=request.form,
        )
        flash(message, category)
        if success or already_submitted:
            return redirect(url_for("student.dashboard"))

        return render_template(
            "student/fill_form.html",
            form=form,
            questions=questions,
            already_submitted=already_submitted,
        )

    return render_template(
        "student/fill_form.html",
        form=form,
        questions=questions,
        already_submitted=already_submitted,
    )
