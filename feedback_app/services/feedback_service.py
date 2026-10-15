"""Feedback Service: Core business logic for feedback validation, submission, and dynamic forms."""

import sqlite3
from typing import Any
from feedback_app.repositories.feedback_repository import FeedbackRepository


class FeedbackService:
    """Encapsulates business rules and workflows for course feedback."""

    def __init__(self, repo: type[FeedbackRepository] = FeedbackRepository):
        self.repo = repo

    def validate_scores(self, form_data: dict[str, Any]) -> tuple[list[int] | None, str | None]:
        """Validate that all required rating scores are integers between 1 and 5."""
        scores = []
        for field in ("teaching_quality", "course_content", "punctuality"):
            try:
                score = int(form_data.get(field, 0))
            except (ValueError, TypeError):
                score = 0
            if score not in range(1, 6):
                return None, "Each rating must be a whole number from 1 to 5."
            scores.append(score)
        return scores, None

    def validate_comments(self, comments: str) -> str | None:
        """Validate comments length limit."""
        if len(comments) > 1000:
            return "Comments must be 1,000 characters or fewer."
        return None

    def submit_course_feedback(
        self,
        student_id: int,
        assignment: sqlite3.Row,
        form_data: dict[str, Any],
        existing_feedback: sqlite3.Row | None,
        edit_hours: int,
    ) -> tuple[bool, str, str]:
        """Submit new course feedback or update an existing one within the edit window.

        Returns (success: bool, message: str, category: str).
        """
        # 1. Edit window check
        if existing_feedback is not None:
            if not self.repo.is_editable(existing_feedback["created_at"], edit_hours):
                return False, "The 24-hour feedback editing window has ended.", "danger"

        # 2. Rating validation
        scores, error = self.validate_scores(form_data)
        if error or scores is None:
            return False, error or "Invalid rating values.", "danger"

        # 3. Comment length validation
        comments = str(form_data.get("comments", "")).strip()
        comment_error = self.validate_comments(comments)
        if comment_error:
            return False, comment_error, "danger"

        # 4. Save to repository
        try:
            feedback_id = existing_feedback["feedback_id"] if existing_feedback else None
            self.repo.save_feedback(
                student_id=student_id,
                assignment_id=assignment["assignment_id"],
                course_id=assignment["course_id"],
                semester=assignment["semester"],
                scores=scores,
                comments=comments,
                feedback_id=feedback_id,
            )
            msg = "Your feedback was updated." if existing_feedback else "Your feedback was submitted anonymously."
            return True, msg, "success"
        except sqlite3.IntegrityError:
            return False, "Feedback could not be saved. Check your enrollment and try again.", "danger"

    def delete_course_feedback(
        self,
        feedback: sqlite3.Row,
        student_id: int,
        edit_hours: int,
    ) -> tuple[bool, str, str]:
        """Delete feedback if it is within the editable window."""
        if not self.repo.is_editable(feedback["created_at"], edit_hours):
            return False, "The 24-hour feedback editing window has ended.", "danger"

        self.repo.delete_feedback(feedback["feedback_id"], student_id)
        return True, "Your feedback was deleted.", "success"

    def submit_custom_form(
        self,
        form_id: int,
        student_id: int,
        questions: list[sqlite3.Row],
        form_data: dict[str, Any],
    ) -> tuple[bool, str, str]:
        """Validate and persist responses to a faculty custom form."""
        if self.repo.has_submitted_form(form_id, student_id):
            return False, "You have already submitted a response for this feedback form.", "warning"

        responses_to_save: list[tuple[int, int, int, int | None, str]] = []

        for q in questions:
            q_id = q["question_id"]
            field_name = f"question_{q_id}"
            q_type = q["question_type"]

            if q_type == "rating":
                try:
                    val = int(form_data.get(field_name, 0))
                except (ValueError, TypeError):
                    val = 0
                if val not in range(1, 6):
                    return False, f"Please select a rating between 1 and 5 for: {q['question_text']}", "danger"
                responses_to_save.append((form_id, student_id, q_id, val, ""))

            elif q_type == "yes_no":
                yn_val = str(form_data.get(field_name, "")).strip().title()
                if yn_val not in ("Yes", "No"):
                    return False, f"Please select Yes or No for: {q['question_text']}", "danger"
                responses_to_save.append((form_id, student_id, q_id, None, yn_val))

            else:  # text question
                text_val = str(form_data.get(field_name, "")).strip()
                if len(text_val) > 1000:
                    return False, "Text comments must be 1,000 characters or fewer.", "danger"
                responses_to_save.append((form_id, student_id, q_id, None, text_val))

        try:
            self.repo.save_form_responses(responses_to_save)
            return True, "Thank you! Your feedback has been submitted anonymously.", "success"
        except sqlite3.IntegrityError:
            return False, "Could not submit feedback. You may have already responded.", "danger"
