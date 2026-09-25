"""Bootstrap of the staging SQLite database schema."""

import sqlite3
from collections.abc import Callable
from pathlib import Path


def initialize_sqlite_database(db_path: Path, connection_factory: Callable[[], sqlite3.Connection]) -> None:
    """Initialize the staging SQLite database with the required schema.

    Creates the database's parent directory if needed and executes the bundled ``schema.sql`` script.

    Args:
        db_path: Path to the SQLite database file.
        connection_factory: Factory returning a new connection to the database at ``db_path``.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connection_factory()
    try:
        conn.executescript(_load_schema())
    finally:
        conn.close()


def _load_schema() -> str:
    """Load the staging database schema script.

    Returns:
        The contents of the ``schema.sql`` file next to this module.
    """
    schema_path = Path(__file__).parent / 'schema.sql'
    return schema_path.read_text(encoding='utf-8')
