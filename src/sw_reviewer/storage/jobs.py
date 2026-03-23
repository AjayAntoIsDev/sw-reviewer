"""
Extended job storage utilities built on the storage.sqlite module.
Provides a clean API for the FastAPI app layer.
"""

import logging
from typing import Any, Dict, Optional

from ..state import JobRepository, JobStatus, JobState

logger = logging.getLogger(__name__)


class JobStore:
    """
    Thin wrapper around JobRepository that provides additional query methods
    for the API layer.
    """

    def __init__(self, db_path: str = "reviewer_state.db"):
        self._repo = JobRepository(db_path=db_path)

    def create(self, job: JobState) -> JobState:
        return self._repo.create_job(job)

    def get(self, review_id: str) -> Optional[JobState]:
        return self._repo.get_job(review_id)

    def update_status(self, review_id: str, status: JobStatus, error: Optional[str] = None) -> None:
        self._repo.update_job_status(review_id, status, error_message=error)

    def save_context(self, review_id: str, data: Dict[str, Any]) -> None:
        self._repo.save_context(review_id, data)

    def cancel(self, review_id: str) -> bool:
        job = self._repo.get_job(review_id)
        if job and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            self._repo.update_job_status(review_id, JobStatus.CANCELLED)
            return True
        return False
