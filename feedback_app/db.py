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


def init_db(app=None):
    """Create the schema and load the bundled demonstration records once."""
    schema_path = Path(__file__).parent / "schema.sql"
    if app is None:
        app = current_app
    with app.app_context():
        db = get_db()
        db.executescript(schema_path.read_text(encoding="utf-8"))
        db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized.")
