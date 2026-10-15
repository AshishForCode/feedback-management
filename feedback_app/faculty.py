from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .db import get_db
from .decorators import roles_required

bp = Blueprint("faculty", __name__, url_prefix="/faculty")


@bp.get("/dashboard")
@roles_required("faculty")
def dashboard():
    db = get_db()
    courses = db.execute(
        """SELECT ca.assignment_id, ca.semester, c.course_code, c.course_name,
                  COUNT(f.feedback_id) AS response_count,
                  ROUND(AVG(f.teaching_quality), 2) AS teaching_average,
                  ROUND(AVG(f.course_content), 2) AS content_average,
                  ROUND(AVG(f.punctuality), 2) AS punctuality_average,
                  ROUND(AVG((f.teaching_quality + f.course_content + f.punctuality) / 3.0), 2)
                    AS overall_average
           FROM course_assignments ca
           JOIN courses c ON c.course_id = ca.course_id
           LEFT JOIN feedback f ON f.assignment_id = ca.assignment_id
           WHERE ca.faculty_id = ?
           GROUP BY ca.assignment_id, ca.semester, c.course_code, c.course_name
           ORDER BY ca.semester DESC, c.course_code""",
        (current_user.id,),
    ).fetchall()

    forms = db.execute(
        """SELECT ff.form_id, ff.title, ff.instructions, ff.is_active, ff.created_at,
                  ca.assignment_id, ca.semester, c.course_code, c.course_name,
                  COUNT(DISTINCT fr.student_id) AS response_count,
                  (SELECT COUNT(*) FROM form_questions fq WHERE fq.form_id = ff.form_id) AS question_count
           FROM feedback_forms ff
           JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
           JOIN courses c ON c.course_id = ca.course_id
           LEFT JOIN form_responses fr ON fr.form_id = ff.form_id
           WHERE ff.faculty_id = ?
           GROUP BY ff.form_id, ff.title, ff.instructions, ff.is_active, ff.created_at,
                    ca.assignment_id, ca.semester, c.course_code, c.course_name
           ORDER BY ff.created_at DESC""",
        (current_user.id,),
    ).fetchall()

    comments = db.execute(
        """SELECT c.course_code, c.course_name, ca.semester, f.comments, f.created_at
           FROM feedback f
           JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
           JOIN courses c ON c.course_id = f.course_id
           WHERE ca.faculty_id = ? AND trim(f.comments) != ''
           ORDER BY f.created_at DESC""",
        (current_user.id,),
    ).fetchall()
    return render_template("faculty/dashboard.html", courses=courses, forms=forms, comments=comments)


@bp.route("/forms/create", methods=("GET", "POST"))
@roles_required("faculty")
def create_form():
    db = get_db()
    assignments = db.execute(
        """SELECT ca.assignment_id, ca.semester, c.course_code, c.course_name
           FROM course_assignments ca
           JOIN courses c ON c.course_id = ca.course_id
           WHERE ca.faculty_id = ?
           ORDER BY ca.semester DESC, c.course_code""",
        (current_user.id,),
    ).fetchall()

    if not assignments:
        flash("You do not have any course assignments to create forms for.", "warning")
        return redirect(url_for("faculty.dashboard"))

    if request.method == "POST":
        assignment_id = request.form.get("assignment_id", "")
        title = request.form.get("title", "").strip()
        instructions = request.form.get("instructions", "").strip()

        valid_assignment = any(str(a["assignment_id"]) == str(assignment_id) for a in assignments)
        if not valid_assignment:
            flash("Please select a valid course assignment.", "danger")
            return render_template("faculty/create_form.html", assignments=assignments)

        if not title or len(title) > 150:
            flash("Form title must be between 1 and 150 characters.", "danger")
            return render_template("faculty/create_form.html", assignments=assignments)

        question_texts = request.form.getlist("question_text[]")
        question_types = request.form.getlist("question_type[]")

        cleaned_questions = []
        for text, q_type in zip(question_texts, question_types):
            t = text.strip()
            if t:
                if q_type not in ("rating", "text", "yes_no"):
                    q_type = "rating"
                cleaned_questions.append((t, q_type))

        if not cleaned_questions:
            flash("Please add at least one question to your feedback form.", "danger")
            return render_template("faculty/create_form.html", assignments=assignments)

        cursor = db.execute(
            """INSERT INTO feedback_forms (assignment_id, faculty_id, title, instructions, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (assignment_id, current_user.id, title, instructions),
        )
        form_id = cursor.lastrowid

        for idx, (q_text, q_type) in enumerate(cleaned_questions, start=1):
            db.execute(
                """INSERT INTO form_questions (form_id, question_text, question_type, order_num)
                   VALUES (?, ?, ?, ?)""",
                (form_id, q_text, q_type, idx),
            )
        db.commit()
        flash(f"Feedback form '{title}' created successfully! Students enrolled in this course can now fill it.", "success")
        return redirect(url_for("faculty.dashboard"))

    return render_template("faculty/create_form.html", assignments=assignments)


@bp.route("/forms/<int:form_id>/edit", methods=("GET", "POST"))
@roles_required("faculty")
def edit_form(form_id):
    db = get_db()
    form = db.execute(
        """SELECT ff.*, ca.semester, c.course_code, c.course_name
           FROM feedback_forms ff
           JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
           JOIN courses c ON c.course_id = ca.course_id
           WHERE ff.form_id = ? AND ff.faculty_id = ?""",
        (form_id, current_user.id),
    ).fetchone()
    if form is None:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        instructions = request.form.get("instructions", "").strip()
        if not title or len(title) > 150:
            flash("Form title must be between 1 and 150 characters.", "danger")
            return redirect(url_for("faculty.edit_form", form_id=form_id))

        question_texts = request.form.getlist("question_text[]")
        question_types = request.form.getlist("question_type[]")
        cleaned_questions = []
        for text, q_type in zip(question_texts, question_types):
            t = text.strip()
            if t:
                if q_type not in ("rating", "text", "yes_no"):
                    q_type = "rating"
                cleaned_questions.append((t, q_type))

        if not cleaned_questions:
            flash("Please add at least one question to your feedback form.", "danger")
            return redirect(url_for("faculty.edit_form", form_id=form_id))

        db.execute(
            "UPDATE feedback_forms SET title = ?, instructions = ? WHERE form_id = ?",
            (title, instructions, form_id),
        )
        db.execute("DELETE FROM form_questions WHERE form_id = ?", (form_id,))
        for idx, (q_text, q_type) in enumerate(cleaned_questions, start=1):
            db.execute(
                """INSERT INTO form_questions (form_id, question_text, question_type, order_num)
                   VALUES (?, ?, ?, ?)""",
                (form_id, q_text, q_type, idx),
            )
        db.commit()
        flash(f"Feedback form '{title}' updated successfully!", "success")
        return redirect(url_for("faculty.dashboard"))

    questions = db.execute(
        "SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num ASC",
        (form_id,),
    ).fetchall()
    return render_template("faculty/edit_form.html", form=form, questions=questions)


@bp.get("/forms/<int:form_id>")
@roles_required("faculty")
def view_form(form_id):
    db = get_db()
    form = db.execute(
        """SELECT ff.*, ca.semester, c.course_code, c.course_name
           FROM feedback_forms ff
           JOIN course_assignments ca ON ca.assignment_id = ff.assignment_id
           JOIN courses c ON c.course_id = ca.course_id
           WHERE ff.form_id = ? AND ff.faculty_id = ?""",
        (form_id, current_user.id),
    ).fetchone()
    if form is None:
        abort(404)

    questions = db.execute(
        """SELECT * FROM form_questions WHERE form_id = ? ORDER BY order_num ASC""",
        (form_id,),
    ).fetchall()

    response_count = db.execute(
        """SELECT COUNT(DISTINCT student_id) FROM form_responses WHERE form_id = ?""",
        (form_id,),
    ).fetchone()[0]

    results = []
    for q in questions:
        if q["question_type"] == "rating":
            stats = db.execute(
                """SELECT ROUND(AVG(rating_value), 2) AS average,
                          COUNT(rating_value) AS total
                   FROM form_responses
                   WHERE question_id = ? AND rating_value IS NOT NULL""",
                (q["question_id"],),
            ).fetchone()
            distribution = {}
            for score in range(1, 6):
                cnt = db.execute(
                    "SELECT COUNT(*) FROM form_responses WHERE question_id = ? AND rating_value = ?",
                    (q["question_id"], score),
                ).fetchone()[0]
                distribution[score] = cnt
            results.append({
                "question": q,
                "type": "rating",
                "average": stats["average"] if stats["average"] is not None else "—",
                "total": stats["total"],
                "distribution": distribution,
            })
        elif q["question_type"] == "yes_no":
            yes_cnt = db.execute(
                "SELECT COUNT(*) FROM form_responses WHERE question_id = ? AND (text_value = 'Yes' OR text_value = 'yes')",
                (q["question_id"],),
            ).fetchone()[0]
            no_cnt = db.execute(
                "SELECT COUNT(*) FROM form_responses WHERE question_id = ? AND (text_value = 'No' OR text_value = 'no')",
                (q["question_id"],),
            ).fetchone()[0]
            total = yes_cnt + no_cnt
            yes_pct = round((yes_cnt / total) * 100) if total > 0 else 0
            no_pct = round((no_cnt / total) * 100) if total > 0 else 0
            results.append({
                "question": q,
                "type": "yes_no",
                "yes_count": yes_cnt,
                "no_count": no_cnt,
                "total": total,
                "yes_pct": yes_pct,
                "no_pct": no_pct,
            })
        else:
            text_rows = db.execute(
                """SELECT text_value, created_at FROM form_responses
                   WHERE question_id = ? AND trim(text_value) != ''
                   ORDER BY created_at DESC""",
                (q["question_id"],),
            ).fetchall()
            results.append({
                "question": q,
                "type": "text",
                "comments": text_rows,
                "total": len(text_rows),
            })

    return render_template("faculty/form_responses.html", form=form, results=results, response_count=response_count)


@bp.post("/forms/<int:form_id>/toggle")
@roles_required("faculty")
def toggle_form(form_id):
    db = get_db()
    form = db.execute(
        "SELECT is_active FROM feedback_forms WHERE form_id = ? AND faculty_id = ?",
        (form_id, current_user.id),
    ).fetchone()
    if form is None:
        abort(404)
    new_status = 0 if form["is_active"] else 1
    db.execute(
        "UPDATE feedback_forms SET is_active = ? WHERE form_id = ?",
        (new_status, form_id),
    )
    db.commit()
    status_label = "opened for student responses" if new_status else "closed"
    flash(f"Feedback form has been {status_label}.", "info")
    return redirect(url_for("faculty.dashboard"))


@bp.post("/forms/<int:form_id>/delete")
@roles_required("faculty")
def delete_form(form_id):
    db = get_db()
    form = db.execute(
        "SELECT form_id FROM feedback_forms WHERE form_id = ? AND faculty_id = ?",
        (form_id, current_user.id),
    ).fetchone()
    if form is None:
        abort(404)
    db.execute("DELETE FROM feedback_forms WHERE form_id = ?", (form_id,))
    db.commit()
    flash("Feedback form deleted.", "success")
    return redirect(url_for("faculty.dashboard"))
