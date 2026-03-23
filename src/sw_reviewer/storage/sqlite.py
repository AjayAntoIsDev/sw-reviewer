"""SQLite connection and migration utilities."""

import sqlite3
from contextlib import contextmanager
from typing import Generator


@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with row_factory set."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(db_path: str) -> None:
    """Initialize the database schema (idempotent)."""
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                review_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                repository_url TEXT NOT NULL,
                context_data TEXT NOT NULL DEFAULT '{}',
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES jobs(review_id)
            );
        """)
