import sqlite3
from pathlib import Path


class SQLiteSessionFactory:
    """Factory for creating SQLite connections."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the factory with the path to the SQLite database."""
        self.db_path = db_path

    def __call__(self) -> sqlite3.Connection:
        """Create and return a new SQLite connection."""
        return self._create_sqlite_connection(self.db_path)

    def _create_sqlite_connection(self, db_path: Path) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(
            db_path,
            isolation_level=None,  # Required to control transactions manually
            check_same_thread=True,  # Keep default safety (single-threaded)
        )
        conn.row_factory = sqlite3.Row  # Enable named column access
        self._apply_pragmas(conn)
        return conn

    @staticmethod
    def _apply_pragmas(conn: sqlite3.Connection) -> None:
        """Apply SQLite connection PRAGMAs for performance and integrity."""
        cursor = conn.cursor()

        # --- Core Correctness ---
        cursor.execute('PRAGMA foreign_keys = ON')

        # --- Performance & Concurrency ---
        cursor.execute('PRAGMA journal_mode = WAL')
        cursor.execute('PRAGMA synchronous = NORMAL')

        # --- Memory Optimizations ---
        cursor.execute('PRAGMA temp_store = MEMORY')
        cursor.execute('PRAGMA cache_size = -20000')  # ~20MB

        cursor.close()
