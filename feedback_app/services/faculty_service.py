"""Faculty Service: Business logic for faculty form creation, question validation, and analytics."""

from typing import Any
from feedback_app.repositories.faculty_repository import FacultyRepository


class FacultyService:
    """Encapsulates business rules for faculty form management and response analytics."""

    def __init__(self, repo: type[FacultyRepository] = FacultyRepository):
        self.repo = repo

    def clean_and_validate_questions(
        self,
        question_texts: list[str],
        question_types: list[str],
    ) -> tuple[list[tuple[str, str]], str | None]:
        """Sanitize and validate dynamic form questions."""
        cleaned = []
        for text, q_type in zip(question_texts, question_types):
            t = text.strip()
            if t:
                valid_type = q_type if q_type in ("rating", "text", "yes_no") else "rating"
                cleaned.append((t, valid_type))

        if not cleaned:
            return [], "Please add at least one question to your feedback form."
        return cleaned, None

    def create_form(
        self,
        assignment_id: str | int,
        faculty_id: int,
        title: str,
        instructions: str,
        question_texts: list[str],
        question_types: list[str],
        valid_assignments: list[Any],
    ) -> tuple[bool, str, str]:
        """Validate input and create a custom feedback form."""
        is_valid_assignment = any(str(a["assignment_id"]) == str(assignment_id) for a in valid_assignments)
        if not is_valid_assignment:
            return False, "Please select a valid course assignment.", "danger"

        clean_title = title.strip()
        if not clean_title or len(clean_title) > 150:
            return False, "Form title must be between 1 and 150 characters.", "danger"

        cleaned_questions, error = self.clean_and_validate_questions(question_texts, question_types)
        if error:
            return False, error, "danger"

        self.repo.create_custom_form(
            assignment_id=int(assignment_id),
            faculty_id=faculty_id,
            title=clean_title,
            instructions=instructions.strip(),
            questions=cleaned_questions,
        )
        return True, f"Feedback form '{clean_title}' created successfully! Students enrolled in this course can now fill it.", "success"

    def update_form(
        self,
        form_id: int,
        title: str,
        instructions: str,
        question_texts: list[str],
        question_types: list[str],
    ) -> tuple[bool, str, str]:
        """Validate input and update an existing custom feedback form."""
        clean_title = title.strip()
        if not clean_title or len(clean_title) > 150:
            return False, "Form title must be between 1 and 150 characters.", "danger"

        cleaned_questions, error = self.clean_and_validate_questions(question_texts, question_types)
        if error:
            return False, error, "danger"

        self.repo.update_custom_form(
            form_id=form_id,
            title=clean_title,
            instructions=instructions.strip(),
            questions=cleaned_questions,
        )
        return True, f"Feedback form '{clean_title}' updated successfully!", "success"

    def compile_form_analytics(self, form_id: int) -> list[dict[str, Any]]:
        """Calculate summary statistics and distributions for each question in a form."""
        questions = self.repo.get_form_questions(form_id)
        results = []

        for q in questions:
            q_type = q["question_type"]
            q_id = q["question_id"]

            if q_type == "rating":
                avg, total, dist = self.repo.get_rating_question_stats(q_id)
                results.append({
                    "question": q,
                    "type": "rating",
                    "average": avg,
                    "total": total,
                    "distribution": dist,
                })
            elif q_type == "yes_no":
                yes_cnt, no_cnt, total, yes_pct, no_pct = self.repo.get_yes_no_question_stats(q_id)
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
                comments = self.repo.get_text_question_comments(q_id)
                results.append({
                    "question": q,
                    "type": "text",
                    "comments": comments,
                    "total": len(comments),
                })

        return results
