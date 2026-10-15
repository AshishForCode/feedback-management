import os
import tempfile
import pytest

from feedback_app import create_app
from feedback_app.db import get_db


class AuthActions:
    """Helper class for authenticating test clients."""
    def __init__(self, client):
        self._client = client

    def login(self, email="student@feedback.local", password="DemoPass123!", remember=False):
        data = {"email": email, "password": password}
        if remember:
            data["remember"] = "1"
        return self._client.post("/auth/login", data=data)

    def logout(self):
        return self._client.post("/auth/logout", follow_redirects=True)


@pytest.fixture
def app():
    """Create and configure a new Flask app instance for each test with an isolated database."""
    handle, database_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(handle)

    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "DATABASE": database_path,
        "FEEDBACK_EDIT_HOURS": 24,
    })

    yield app

    # Cleanup temporary SQLite file after test execution
    if os.path.exists(database_path):
        try:
            os.unlink(database_path)
        except PermissionError:
            pass


@pytest.fixture
def client(app):
    """A test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture
def auth(client):
    """Authentication actions helper fixture."""
    return AuthActions(client)


@pytest.fixture
def db(app):
    """Provide a database connection context for assertions."""
    with app.app_context():
        yield get_db()
