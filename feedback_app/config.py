import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class BaseConfig:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-key")
    FEEDBACK_EDIT_HOURS = int(os.environ.get("FEEDBACK_EDIT_HOURS", 24))

    # Security cookie defaults
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def get_database_path(cls, instance_path: str) -> str:
        return os.environ.get(
            "DATABASE_PATH",
            str(Path(instance_path) / "feedback.sqlite3")
        )


class DevelopmentConfig(BaseConfig):
    """Configuration for local development."""
    DEBUG = True


class TestingConfig(BaseConfig):
    """Configuration for automated test runs."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"


class ProductionConfig(BaseConfig):
    """Configuration for production environments."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None) -> type[BaseConfig]:
    """Retrieve configuration class by environment name."""
    if not env_name:
        env_name = os.environ.get("FLASK_ENV", "development").lower()
    return CONFIG_MAP.get(env_name, DevelopmentConfig)
