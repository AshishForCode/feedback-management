import os
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .db import close_db, init_db, init_db_command

csrf = CSRFProtect()


def create_app(test_config=None):
    """Create the Flask application and connect its feature blueprints."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-key"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(Path(app.instance_path) / "feedback.sqlite3")
        ),
        FEEDBACK_EDIT_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    csrf.init_app(app)
    app.teardown_appcontext(close_db)

    from . import admin, auth, faculty, student

    app.register_blueprint(auth.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(faculty.bp)
    app.register_blueprint(admin.bp)

    @app.before_request
    def enforce_login_requirement():
        from flask import flash, redirect, request, url_for
        from flask_login import current_user

        if request.endpoint is None:
            return None

        public_endpoints = {
            "auth.login",
            "auth.register",
            "auth.logout",
            "static",
        }

        if request.endpoint not in public_endpoints:
            if not current_user.is_authenticated:
                if request.endpoint != "index":
                    flash("Please log in first to access the system.", "warning")
                next_url = request.url if (request.method == "GET" and request.endpoint != "index") else None
                return redirect(url_for("auth.login", next=next_url))

    @app.get("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for(f"{current_user.role}.dashboard"))
        return redirect(url_for("auth.login"))

    # Flask-Login is initialized here after blueprint imports to keep auth setup centralized.
    from flask_login import LoginManager

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access the system."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    from .auth import load_user

    login_manager.user_loader(load_user)
    app.cli.add_command(init_db_command)
    init_db(app)
    return app
