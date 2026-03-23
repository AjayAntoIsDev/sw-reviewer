"""Artifact record persistence."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from .sqlite import get_connection

logger = logging.getLogger(__name__)


class ArtifactRepository:
    """Stores and retrieves artifact metadata in SQLite."""

    def __init__(self, db_path: str = "reviewer_state.db"):
        self.db_path = db_path

    def save_artifact(self, review_id: str, artifact_type: str, file_path: str) -> int:
        """Record an artifact file path and return its row ID."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (review_id, artifact_type, file_path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (review_id, artifact_type, file_path, datetime.now(tz=timezone.utc).isoformat()),
            )
            return cursor.lastrowid

    def get_artifacts(self, review_id: str) -> List[dict]:
        """Return all artifact records for a review."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, review_id, artifact_type, file_path, created_at FROM artifacts WHERE review_id = ?",
                (review_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_artifact_by_type(self, review_id: str, artifact_type: str) -> Optional[dict]:
        """Return the first artifact of a given type for a review."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, review_id, artifact_type, file_path, created_at FROM artifacts WHERE review_id = ? AND artifact_type = ? LIMIT 1",
                (review_id, artifact_type),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
