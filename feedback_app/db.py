import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    """Return this request's SQLite connection, creating it when needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def is_db_initialized(db):
    """Check if primary tables already exist in the database."""
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    return cursor.fetchone() is not None


def init_db(app=None, force=False):
    """Create the schema and load the bundled demonstration records when needed."""
    schema_path = Path(__file__).parent / "schema.sql"
    if app is None:
        app = current_app
    with app.app_context():
        db = get_db()
        if force or not is_db_initialized(db):
            db.executescript(schema_path.read_text(encoding="utf-8"))
            db.commit()


@click.command("init-db")
@click.option("--force", is_flag=True, help="Force re-running the schema script.")
def init_db_command(force):
    init_db(force=force)
    click.echo("Database initialized.")
