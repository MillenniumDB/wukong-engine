import sqlite3
from collections.abc import Callable
from pathlib import Path


def initialize_sqlite_database(db_path: Path, connection_factory: Callable[[], sqlite3.Connection]) -> None:
    """Initialize the staging SQLite database with the required schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = connection_factory()
        conn.executescript(_load_schema())
    finally:
        conn.close()


def _load_schema() -> str:
    schema_path = Path(__file__).parent / 'schema.sql'
    return schema_path.read_text(encoding='utf-8')
