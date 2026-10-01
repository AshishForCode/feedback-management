from flask import Blueprint, render_template
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
    comments = db.execute(
        """SELECT c.course_code, c.course_name, ca.semester, f.comments, f.created_at
           FROM feedback f
           JOIN course_assignments ca ON ca.assignment_id = f.assignment_id
           JOIN courses c ON c.course_id = f.course_id
           WHERE ca.faculty_id = ? AND trim(f.comments) != ''
           ORDER BY f.created_at DESC""",
        (current_user.id,),
    ).fetchall()
    return render_template("faculty/dashboard.html", courses=courses, comments=comments)
