from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import json
import sqlite3

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WEB_TESTING = "web_testing"
    CLI_TESTING = "cli_testing"
    POLICY_EVAL = "policy_eval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobState(BaseModel):
    """Represents the current state of a review job."""
    review_id: str = Field(..., description="Unique ID for the job")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current status of the job")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    repository_url: str = Field(..., description="Target repository URL")
    
    # Store partial results as serialized JSON or dicts
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Context variables passing between stages")
    error_message: Optional[str] = Field(None, description="Reason for failure if any")

class JobRepository:
    """Repository layer for job state persistence."""
    
    def __init__(self, db_path: str = "reviewer_state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    review_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    repository_url TEXT NOT NULL,
                    context_data TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            conn.commit()

    def create_job(self, state: JobState) -> JobState:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO jobs (review_id, status, created_at, updated_at, repository_url, context_data, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                state.review_id,
                state.status.value,
                state.created_at.isoformat(),
                state.updated_at.isoformat(),
                state.repository_url,
                json.dumps(state.context_data),
                state.error_message
            ))
            conn.commit()
        return state

    def update_job_status(self, review_id: str, status: JobStatus, error_message: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                UPDATE jobs 
                SET status = ?, updated_at = ?, error_message = COALESCE(?, error_message)
                WHERE review_id = ?
            """, (status.value, now, error_message, review_id))
            conn.commit()

    def save_context(self, review_id: str, context_data: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                UPDATE jobs 
                SET context_data = ?, updated_at = ?
                WHERE review_id = ?
            """, (json.dumps(context_data), now, review_id))
            conn.commit()

    def get_job(self, review_id: str) -> Optional[JobState]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE review_id = ?", (review_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            return JobState(
                review_id=row[0],
                status=JobStatus(row[1]),
                created_at=datetime.fromisoformat(row[2]),
                updated_at=datetime.fromisoformat(row[3]),
                repository_url=row[4],
                context_data=json.loads(row[5]),
                error_message=row[6]
            )
