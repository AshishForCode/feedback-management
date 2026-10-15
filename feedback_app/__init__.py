from pathlib import Path

from flask import Flask, flash, redirect, request, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

from .config import BaseConfig, get_config
from .db import close_db, init_db, init_db_command

csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(test_config=None, config_name=None):
    """Application factory for the Student Feedback Management System."""
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration class
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    # Set default database location inside instance/ if not specified
    if not app.config.get("DATABASE"):
        app.config["DATABASE"] = BaseConfig.get_database_path(app.instance_path)

    # Apply test config overrides if provided
    if test_config:
        app.config.update(test_config)

    # Ensure instance directory exists
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    csrf.init_app(app)
    app.teardown_appcontext(close_db)

    # Configure Flask-Login
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access the system."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    from .auth import load_user
    login_manager.user_loader(load_user)

    # Register blueprints
    from . import admin, auth, faculty, student
    app.register_blueprint(auth.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(faculty.bp)
    app.register_blueprint(admin.bp)

    @app.before_request
    def enforce_login_requirement():
        if request.endpoint is None:
            return None

        public_endpoints = {
            "auth.login",
            "auth.register",
            "auth.logout",
            "static",
            "healthz",
        }

        if request.endpoint not in public_endpoints and not current_user.is_authenticated:
            if request.endpoint != "index":
                flash("Please log in first to access the system.", "warning")
            next_url = (
                request.url
                if (request.method == "GET" and request.endpoint != "index")
                else None
            )
            return redirect(url_for("auth.login", next=next_url))

    @app.get("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.get("/healthz")
    def healthz():
        """Liveness & readiness probe for cloud monitoring and container orchestration."""
        try:
            from .db import get_db
            get_db().execute("SELECT 1").fetchone()
            return {"status": "healthy", "database": "connected"}, 200
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}, 503

    # Register CLI commands and ensure DB tables exist
    app.cli.add_command(init_db_command)
    init_db(app)

    return app
