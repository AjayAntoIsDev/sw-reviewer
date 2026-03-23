"""
Shipwright AI Reviewer — FastAPI application entry point.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, Field

from .models import ReviewRequest, RequestSource, FinalVerdict, VerdictDecision
from .orchestrator.service import ReviewOrchestratorService
from .state import JobStatus
from .log_config import setup_logging, set_review_context
from .config import settings

setup_logging()
logger = logging.getLogger(__name__)

# In-memory verdict cache (for completed reviews)
_verdict_cache: Dict[str, FinalVerdict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Shipwright AI Reviewer starting up.")
    yield
    logger.info("Shipwright AI Reviewer shutting down.")


app = FastAPI(
    title="Shipwright AI Reviewer",
    description="Automated review pipeline for web and CLI projects.",
    version="0.1.0",
    lifespan=lifespan,
)

_orchestrator = ReviewOrchestratorService(db_path=settings.db_path)


# ── Pydantic request/response schemas ─────────────────────────────────────────

class StartReviewRequest(BaseModel):
    repo_url: HttpUrl = Field(..., description="Git repository URL")
    project_type: str = Field(..., pattern="^(web|cli)$", description="'web' or 'cli'")
    readme_text: Optional[str] = Field(None, description="README content override")
    demo_url: Optional[str] = Field(None, description="Live demo URL (web projects)")
    cli_commands: Optional[list] = Field(None, description="CLI command hints")
    auth_instructions: Optional[str] = Field(None, description="Auth test instructions")
    requester: str = Field(default="api-user", description="Who triggered the review")


class JobStatusResponse(BaseModel):
    review_id: str
    status: str
    error_message: Optional[str] = None


# ── Background task runner ────────────────────────────────────────────────────

async def _run_review(review_id: str, request: ReviewRequest) -> None:
    """Run the review pipeline in the background and cache the verdict."""
    set_review_context(review_id)
    verdict = await _orchestrator.start_review(request)
    _verdict_cache[review_id] = verdict


# ── API routes ────────────────────────────────────────────────────────────────

@app.post("/reviews", status_code=202, response_model=Dict[str, str])
async def start_review(body: StartReviewRequest, background_tasks: BackgroundTasks):
    """Start a new review. Returns the review_id immediately; review runs in background."""
    review_id = str(uuid.uuid4())[:8]
    metadata: Dict[str, Any] = {
        "project_type": body.project_type,
        "demo_url": str(body.demo_url) if body.demo_url else "",
        "readme_text": body.readme_text or "",
        "cli_commands": body.cli_commands or [],
        "auth_instructions": body.auth_instructions or "",
    }
    request = ReviewRequest(
        review_id=review_id,
        repository_url=body.repo_url,
        source=RequestSource.API,
        requester=body.requester,
        metadata=metadata,
    )
    background_tasks.add_task(_run_review, review_id, request)
    logger.info("Review %s queued for %s", review_id, body.repo_url)
    return {"review_id": review_id, "status": "queued"}


@app.get("/reviews/{review_id}/status", response_model=JobStatusResponse)
async def get_status(review_id: str):
    """Get the current status of a review job."""
    job = _orchestrator.get_job(review_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    return JobStatusResponse(
        review_id=review_id,
        status=job.status.value,
        error_message=job.error_message,
    )


@app.get("/reviews/{review_id}/verdict")
async def get_verdict(review_id: str):
    """Get the final verdict for a completed review."""
    # Check cache first
    if review_id in _verdict_cache:
        return _verdict_cache[review_id].model_dump()

    job = _orchestrator.get_job(review_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=202, detail=f"Review is not complete yet (status: {job.status.value}).")

    return {"review_id": review_id, "status": job.status.value, "context": job.context_data}


@app.delete("/reviews/{review_id}", status_code=200)
async def cancel_review(review_id: str):
    """Cancel a pending or running review."""
    cancelled = _orchestrator.cancel_job(review_id)
    if not cancelled:
        job = _orchestrator.get_job(review_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
        raise HTTPException(status_code=409, detail=f"Cannot cancel review in status '{job.status.value}'.")
    return {"review_id": review_id, "status": "cancelled"}


@app.post("/slack/commands")
async def slack_command(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for Slack slash commands.
    Expects form data: command, user_id, text.
    """
    from .slack.commands import SlackCommandHandler
    form = await request.form()
    command = form.get("command", "/review")
    user_id = form.get("user_id", "unknown")
    text = form.get("text", "")

    handler = SlackCommandHandler(db_path=settings.db_path)
    response = handler.handle_command(command, user_id, text)
    return JSONResponse(content=response)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
