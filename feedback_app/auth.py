"""Auth Blueprint: Presentation layer for authentication, login, student registration, and logout."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, current_user, login_user, logout_user

from .repositories.user_repository import UserRepository
from .services.auth_service import AuthService

bp = Blueprint("auth", __name__, url_prefix="/auth")
auth_service = AuthService(UserRepository)


class User(UserMixin):
    """Small authenticated-user object backed by the users table."""

    def __init__(self, row):
        self.id = str(row["user_id"])
        self.email = row["email"]
        self.full_name = row["full_name"]
        self.role = row["role"]
        self._active = bool(row["is_active"])

    @property
    def is_active(self):
        return self._active


def load_user(user_id: str | int) -> User | None:
    """Flask-Login user loader callback backed by UserRepository."""
    row = UserRepository.get_by_id(user_id)
    return User(row) if row else None


@bp.route("/login", methods=("GET", "POST"))
def login():
    """User authentication view with role-based redirection and next URL handling."""
    if current_user.is_authenticated:
        return redirect(url_for(auth_service.get_dashboard_endpoint(current_user.role)))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user_row, error = auth_service.authenticate(email, password)
        if error:
            category = "warning" if "deactivated" in error else "danger"
            flash(error, category)
        elif user_row:
            login_user(User(user_row), remember=remember)
            flash(f"Welcome back, {user_row['full_name']}!", "success")
            safe_next = auth_service.is_safe_redirect_url(request.args.get("next"), request.host_url)
            target_endpoint = safe_next or url_for(auth_service.get_dashboard_endpoint(user_row["role"]))
            return redirect(target_endpoint)

    return render_template("auth/login.html")


@bp.route("/register", methods=("GET", "POST"))
def register():
    """Student registration view."""
    if current_user.is_authenticated:
        return redirect(url_for(auth_service.get_dashboard_endpoint(current_user.role)))

    if request.method == "POST":
        success, errors = auth_service.register_student(request.form)
        if success:
            flash("Registration complete. You can now log in.", "success")
            return redirect(url_for("auth.login"))
        for error in errors:
            flash(error, "danger")

    return render_template("auth/register.html")


@bp.post("/logout")
def logout():
    """Sign the active user out and clear session."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
