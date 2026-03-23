"""
Main orchestrator service that runs the full review pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..models import ReviewRequest, FinalVerdict, VerdictDecision
from ..state import JobRepository, JobStatus, JobState
from ..log_config import set_review_context
from .stages import (
    stage_policy_prechecks,
    stage_web_execution,
    stage_cli_execution,
    stage_evidence_normalization,
    stage_policy_evaluation,
    stage_verdict_generation,
    stage_report_generation,
)

logger = logging.getLogger(__name__)


class ReviewOrchestratorService:
    """
    Main orchestrator service.
    Runs the full review pipeline from request to final verdict.
    """

    def __init__(self, db_path: str = "reviewer_state.db"):
        self.repo = JobRepository(db_path=db_path)

    async def start_review(self, request: ReviewRequest) -> FinalVerdict:
        """
        Kick off a full review pipeline for the given request.

        Returns the final verdict.
        """
        set_review_context(request.review_id)
        logger.info("Starting review pipeline for review_id=%s", request.review_id)

        # Persist initial job state
        job = JobState(
            review_id=request.review_id,
            status=JobStatus.PENDING,
            repository_url=str(request.repository_url),
            context_data={"metadata": request.metadata},
        )
        self.repo.create_job(job)

        context: Dict[str, Any] = {"evidence_items": []}
        project_type = request.metadata.get("project_type", "").lower()

        try:
            self.repo.update_job_status(request.review_id, JobStatus.RUNNING)

            # Stage 1: Policy prechecks
            context = await stage_policy_prechecks(request, context)

            # Stage 2: Execution (web or CLI, based on project type)
            if project_type == "web":
                self.repo.update_job_status(request.review_id, JobStatus.WEB_TESTING)
                context = await stage_web_execution(request, context)
            elif project_type == "cli":
                self.repo.update_job_status(request.review_id, JobStatus.CLI_TESTING)
                context = await stage_cli_execution(request, context)

            # Stage 3: Evidence normalization
            context = await stage_evidence_normalization(request, context)

            # Stage 4: Policy evaluation
            self.repo.update_job_status(request.review_id, JobStatus.POLICY_EVAL)
            context = await stage_policy_evaluation(request, context)

            # Stage 5: Verdict
            context = await stage_verdict_generation(request, context)

            # Stage 6: Report
            context = await stage_report_generation(request, context)

            verdict: FinalVerdict = context["verdict"]
            self.repo.update_job_status(request.review_id, JobStatus.COMPLETED)
            self.repo.save_context(request.review_id, {"verdict_decision": verdict.decision.value})
            logger.info(
                "Review %s completed: decision=%s", request.review_id, verdict.decision.value
            )
            return verdict

        except Exception as exc:
            logger.error(
                "Review pipeline failed for review_id=%s: %s", request.review_id, exc, exc_info=True
            )
            self.repo.update_job_status(
                request.review_id, JobStatus.FAILED, error_message=str(exc)
            )
            return FinalVerdict(
                review_id=request.review_id,
                decision=VerdictDecision.ERROR,
                summary=f"Pipeline error: {exc}",
            )

    def get_job(self, review_id: str) -> Optional[JobState]:
        return self.repo.get_job(review_id)

    def cancel_job(self, review_id: str) -> bool:
        job = self.repo.get_job(review_id)
        if job and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            self.repo.update_job_status(review_id, JobStatus.CANCELLED)
            return True
        return False

    def get_verdict_from_context(self, review_id: str) -> Optional[Dict]:
        job = self.repo.get_job(review_id)
        if job and job.status == JobStatus.COMPLETED:
            return job.context_data
        return None
