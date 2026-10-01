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
    courses = _student_courses()
    history = get_db().execute(
        """SELECT f.*, c.course_code, c.course_name
           FROM feedback f JOIN courses c ON c.course_id = f.course_id
           WHERE f.student_id = ? ORDER BY f.created_at DESC""",
        (current_user.id,),
    ).fetchall()
    return render_template("student/dashboard.html", courses=courses, history=history)


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
