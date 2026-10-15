import sqlite3

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .db import get_db
from .decorators import roles_required

bp = Blueprint("student", __name__, url_prefix="/student")


def _student_courses():
    return get_db().execute(
        """SELECT sc.course_id, sc.semester, c.course_code, c.course_name,
                  ca.assignment_id, u.full_name AS faculty_name,
                  f.feedback_id, f.created_at
           FROM student_courses sc
           JOIN courses c ON c.course_id = sc.course_id
           LEFT JOIN course_assignments ca
             ON ca.course_id = sc.course_id AND ca.semester = sc.semester
           LEFT JOIN faculty fac ON fac.faculty_id = ca.faculty_id
           LEFT JOIN users u ON u.user_id = fac.faculty_id
           LEFT JOIN feedback f
             ON f.student_id = sc.student_id AND f.course_id = sc.course_id
            AND f.semester = sc.semester
           WHERE sc.student_id = ? ORDER BY sc.semester DESC, c.course_code, u.full_name""",
        (current_user.id,),
    ).fetchall()


def _can_edit(feedback):
    hours = int(current_app.config["FEEDBACK_EDIT_HOURS"])
    row = get_db().execute(
        "SELECT julianday(?) >= julianday('now', ? ) AS allowed",
        (feedback["created_at"], f"-{hours} hours"),
    ).fetchone()
    return bool(row["allowed"])


@bp.get("/dashboard")
@roles_required("student")
def dashboard():
    db = get_db()
    courses = _student_courses()
    history = db.execute(
        """SELECT f.*, c.course_code, c.course_name
           FROM feedback f JOIN courses c ON c.course_id = f.course_id
           WHERE f.student_id = ? ORDER BY f.created_at DESC""",
        (current_user.id,),
    ).fetchall()

    forms = db.execute(
        """SELECT ff.form_id, ff.title, ff.instructions, ff.is_active, ff.created_at,
                  c.course_code, c.course_name, ca.semester, u.full_name AS faculty_name,
                  (SELECT COUNT(*) FROM form_questions fq WHERE fq.form_id = ff.form_id) AS question_count,
                  (SELECT COUNT(*) FROM form_responses fr WHERE fr.form_id = ff.form_id AND fr.student_id = ?) AS has_submitted
           FROM feedback_forms ff
           JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
           JOIN courses c ON c.course_id = ca.course_id
           JOIN faculty fac ON fac.faculty_id = ca.faculty_id
           JOIN users u ON u.user_id = fac.faculty_id
           JOIN student_courses sc ON sc.course_id = ca.course_id AND sc.semester = ca.semester
           WHERE sc.student_id = ? AND ff.is_active = 1
           ORDER BY ff.created_at DESC""",
        (current_user.id, current_user.id),
    ).fetchall()

    return render_template("student/dashboard.html", courses=courses, forms=forms, history=history)


@bp.route("/feedback/<int:assignment_id>", methods=("GET", "POST"))
@roles_required("student")
def feedback_form(assignment_id):
    db = get_db()
    assignment = db.execute(
        """SELECT ca.assignment_id, ca.course_id, ca.semester, c.course_code, c.course_name,
                  u.full_name AS faculty_name
           FROM course_assignments ca
           JOIN courses c ON c.course_id = ca.course_id
           JOIN faculty f ON f.faculty_id = ca.faculty_id
           JOIN users u ON u.user_id = f.faculty_id
           JOIN student_courses sc ON sc.course_id = ca.course_id AND sc.semester = ca.semester
           WHERE ca.assignment_id = ? AND sc.student_id = ?""",
        (assignment_id, current_user.id),
    ).fetchone()
    if assignment is None:
        abort(404)

    feedback = db.execute(
        """SELECT * FROM feedback
           WHERE student_id = ? AND course_id = ? AND semester = ?""",
        (current_user.id, assignment["course_id"], assignment["semester"]),
    ).fetchone()
    editable = feedback is None or _can_edit(feedback)
    if request.method == "POST":
        if not editable:
            flash("The 24-hour feedback editing window has ended.", "danger")
            return redirect(url_for("student.dashboard"))
        scores = []
        for field in ("teaching_quality", "course_content", "punctuality"):
            try:
                score = int(request.form.get(field, ""))
            except ValueError:
                score = 0
            if score not in range(1, 6):
                flash("Each rating must be a whole number from 1 to 5.", "danger")
                return render_template("student/feedback_form.html", assignment=assignment,
                                       feedback=feedback, editable=editable)
            scores.append(score)
        comments = request.form.get("comments", "").strip()
        if len(comments) > 1000:
            flash("Comments must be 1,000 characters or fewer.", "danger")
            return render_template("student/feedback_form.html", assignment=assignment,
                                   feedback=feedback, editable=editable)
        try:
            if feedback:
                db.execute(
                    """UPDATE feedback SET assignment_id = ?, teaching_quality = ?,
                       course_content = ?, punctuality = ?, comments = ?, updated_at = datetime('now')
                       WHERE feedback_id = ? AND student_id = ?""",
                    (assignment_id, *scores, comments, feedback["feedback_id"], current_user.id),
                )
                flash("Your feedback was updated.", "success")
            else:
                db.execute(
                    """INSERT INTO feedback
                       (student_id, course_id, assignment_id, semester, teaching_quality,
                        course_content, punctuality, comments)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (current_user.id, assignment["course_id"], assignment_id,
                     assignment["semester"], *scores, comments),
                )
                flash("Your feedback was submitted anonymously.", "success")
            db.commit()
            return redirect(url_for("student.dashboard"))
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Feedback could not be saved. Check your enrollment and try again.", "danger")

    return render_template("student/feedback_form.html", assignment=assignment,
                           feedback=feedback, editable=editable)


@bp.post("/feedback/<int:feedback_id>/delete")
@roles_required("student")
def delete_feedback(feedback_id):
    db = get_db()
    feedback = db.execute(
        "SELECT * FROM feedback WHERE feedback_id = ? AND student_id = ?",
        (feedback_id, current_user.id),
    ).fetchone()
    if feedback is None:
        abort(404)
    if not _can_edit(feedback):
        flash("The 24-hour feedback editing window has ended.", "danger")
    else:
        db.execute("DELETE FROM feedback WHERE feedback_id = ? AND student_id = ?",
                   (feedback_id, current_user.id))
        db.commit()
        flash("Your feedback was deleted.", "success")
    return redirect(url_for("student.dashboard"))


@bp.route("/forms/<int:form_id>", methods=("GET", "POST"))
@roles_required("student")
def fill_form(form_id):
    db = get_db()
    form = db.execute(
        """SELECT ff.*, c.course_code, c.course_name, ca.semester, u.full_name AS faculty_name
           FROM feedback_forms ff
           JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
           JOIN courses c ON c.course_id = ca.course_id
           JOIN faculty fac ON fac.faculty_id = ca.faculty_id
           JOIN users u ON u.user_id = fac.faculty_id
           JOIN student_courses sc ON sc.course_id = ca.course_id AND sc.semester = ca.semester
           WHERE ff.form_id = ? AND sc.student_id = ?""",
        (form_id, current_user.id),
    ).fetchone()
    if form is None:
        abort(404)

    if not form["is_active"]:
        flash("This feedback form is currently closed.", "warning")
        return redirect(url_for("student.dashboard"))

    already_submitted = db.execute(
        "SELECT 1 FROM form_responses WHERE form_id = ? AND student_id = ? LIMIT 1",
        (form_id, current_user.id),
    ).fetchone() is not None

    questions = db.execute(
        "SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num ASC",
        (form_id,),
    ).fetchall()

    if request.method == "POST":
        if already_submitted:
            flash("You have already submitted a response for this feedback form.", "warning")
            return redirect(url_for("student.dashboard"))

        responses_to_save = []
        for q in questions:
            q_id = q["question_id"]
            if q["question_type"] == "rating":
                try:
                    val = int(request.form.get(f"question_{q_id}", 0))
                except ValueError:
                    val = 0
                if val not in range(1, 6):
                    flash(f"Please select a rating between 1 and 5 for: {q['question_text']}", "danger")
                    return render_template("student/fill_form.html", form=form, questions=questions, already_submitted=already_submitted)
                responses_to_save.append((form_id, current_user.id, q_id, val, ""))
            elif q["question_type"] == "yes_no":
                yn_val = request.form.get(f"question_{q_id}", "").strip().title()
                if yn_val not in ("Yes", "No"):
                    flash(f"Please select Yes or No for: {q['question_text']}", "danger")
                    return render_template("student/fill_form.html", form=form, questions=questions, already_submitted=already_submitted)
                responses_to_save.append((form_id, current_user.id, q_id, None, yn_val))
            else:
                text_val = request.form.get(f"question_{q_id}", "").strip()
                if len(text_val) > 1000:
                    flash("Text comments must be 1,000 characters or fewer.", "danger")
                    return render_template("student/fill_form.html", form=form, questions=questions, already_submitted=already_submitted)
                responses_to_save.append((form_id, current_user.id, q_id, None, text_val))

        try:
            for item in responses_to_save:
                db.execute(
                    """INSERT INTO form_responses (form_id, student_id, question_id, rating_value, text_value)
                       VALUES (?, ?, ?, ?, ?)""",
                    item,
                )
            db.commit()
            flash("Thank you! Your feedback has been submitted anonymously.", "success")
            return redirect(url_for("student.dashboard"))
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Could not submit feedback. You may have already responded.", "danger")
            return redirect(url_for("student.dashboard"))

    return render_template("student/fill_form.html", form=form, questions=questions, already_submitted=already_submitted)

