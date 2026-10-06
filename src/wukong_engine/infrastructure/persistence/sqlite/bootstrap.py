"""Bootstrap of the staging SQLite database schema."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

# Columns added to existing tables after their first release, as (table, column, definition)
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (('extraction_jobs', 'raw_response', 'TEXT'),)


def initialize_sqlite_database(db_path: Path, connection_factory: Callable[[], sqlite3.Connection]) -> None:
    """Initialize the staging SQLite database with the required schema.

    Creates the database's parent directory if needed, executes the bundled ``schema.sql`` script, and adds the
    columns that databases created by earlier versions lack.

    Args:
        db_path: Path to the SQLite database file.
        connection_factory: Factory returning a new connection to the database at ``db_path``.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connection_factory()
    try:
        conn.executescript(_load_schema())
        _add_missing_columns(conn)
    finally:
        conn.close()


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Add the columns introduced after a table was first created, which ``CREATE TABLE IF NOT EXISTS`` skips.

    Args:
        conn: Open connection to the staging database, in autocommit mode.
    """
    for table, column, definition in _ADDED_COLUMNS:
        existing = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
        if column not in existing:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def _load_schema() -> str:
    """Load the staging database schema script.

    Returns:
        The contents of the ``schema.sql`` file next to this module.
    """
    schema_path = Path(__file__).parent / 'schema.sql'
    return schema_path.read_text(encoding='utf-8')
