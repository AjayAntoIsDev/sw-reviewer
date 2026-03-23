"""
Slack slash command handler.
Routes /review [start|status|cancel|verdict] commands.
This is a clean reimplementation that fixes import issues in the legacy slack.py.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from ..models import ReviewRequest, RequestSource, VerdictDecision
from ..state import JobStatus, JobRepository
from .formatting import format_verdict_card, format_progress_message, format_error_message

logger = logging.getLogger(__name__)


class SlackCommandHandler:
    """
    Handles Slack slash commands for the Shipwright AI Reviewer.

    This is the clean implementation that works with ReviewOrchestratorService.
    """

    def __init__(self, db_path: str = "reviewer_state.db"):
        self.db_path = db_path
        self._repo = JobRepository(db_path=db_path)

    def handle_command(self, command: str, user_id: str, text: str) -> Dict[str, Any]:
        """
        Synchronous entry point for Slack slash command routing.
        Long-running operations (start) should be kicked off as background tasks.

        Commands:
            /review start <repo_url> [project_type=web|cli] [demo_url=...]
            /review status <job_id>
            /review cancel <job_id>
            /review verdict <job_id>
        """
        if command != "/review":
            return {"text": f"Unknown command: {command}"}

        parts = text.strip().split(None, 1)
        if not parts:
            return {"text": "Usage: /review [start|status|cancel|verdict] [args...]"}

        action = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if action == "start":
            return self._handle_start(user_id, args)
        elif action == "status":
            return self._handle_status(args.strip())
        elif action == "cancel":
            return self._handle_cancel(args.strip())
        elif action == "verdict":
            return self._handle_verdict(args.strip())
        else:
            return {"text": "Usage: /review [start|status|cancel|verdict] [args...]"}

    def _parse_start_args(self, args: str) -> Dict[str, str]:
        """Parse start command args: <repo_url> [key=value ...]"""
        tokens = args.split()
        if not tokens:
            return {}
        result = {"repo_url": tokens[0]}
        for token in tokens[1:]:
            if "=" in token:
                k, _, v = token.partition("=")
                result[k.strip()] = v.strip()
        return result

    def _handle_start(self, user_id: str, args: str) -> Dict[str, Any]:
        """Handle /review start — validate input and return an ack with the job ID."""
        parsed = self._parse_start_args(args)
        repo_url = parsed.get("repo_url", "").strip()
        if not repo_url:
            return {"text": "Please provide a repository URL.\nUsage: `/review start <repo_url> [project_type=web|cli] [demo_url=...]`"}

        project_type = parsed.get("project_type", "web")
        if project_type not in ("web", "cli"):
            return {"text": f"Invalid project_type '{project_type}'. Must be 'web' or 'cli'."}

        review_id = str(uuid.uuid4())[:8]
        logger.info("Received /review start from user=%s review_id=%s", user_id, review_id)
        return {
            "response_type": "in_channel",
            "text": (
                f"🚢 Review started!\n"
                f"• *Job ID:* `{review_id}`\n"
                f"• *Repo:* {repo_url}\n"
                f"• *Type:* {project_type}\n"
                f"Use `/review status {review_id}` to check progress."
            ),
        }

    def _handle_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {"text": "Please provide a job ID.\nUsage: `/review status <job_id>`"}

        job = self._repo.get_job(job_id)
        if not job:
            return {"text": f"Job `{job_id}` not found."}

        status_emoji = {
            JobStatus.PENDING: "⏳",
            JobStatus.RUNNING: "🔄",
            JobStatus.WEB_TESTING: "🌐",
            JobStatus.CLI_TESTING: "💻",
            JobStatus.POLICY_EVAL: "⚖️",
            JobStatus.COMPLETED: "✅",
            JobStatus.FAILED: "❌",
            JobStatus.CANCELLED: "🚫",
        }
        emoji = status_emoji.get(job.status, "❓")
        text = f"{emoji} Job `{job_id}` status: *{job.status.value.upper()}*"
        if job.error_message:
            text += f"\nError: {job.error_message[:200]}"
        return {"text": text}

    def _handle_cancel(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {"text": "Please provide a job ID.\nUsage: `/review cancel <job_id>`"}

        job = self._repo.get_job(job_id)
        if not job:
            return {"text": f"Job `{job_id}` not found."}

        if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            self._repo.update_job_status(job_id, JobStatus.CANCELLED)
            return {"text": f"🚫 Job `{job_id}` has been cancelled."}
        return {"text": f"Job `{job_id}` cannot be cancelled (status: {job.status.value})."}

    def _handle_verdict(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {"text": "Please provide a job ID.\nUsage: `/review verdict <job_id>`"}

        job = self._repo.get_job(job_id)
        if not job:
            return {"text": f"Job `{job_id}` not found."}

        if job.status != JobStatus.COMPLETED:
            return {"text": f"Verdict for `{job_id}` is not yet available (status: {job.status.value})."}

        decision = job.context_data.get("verdict_decision", "unknown")
        return {
            "text": (
                f"📋 Verdict for `{job_id}`: *{decision.upper()}*\n"
                f"Use the API endpoint `/reviews/{job_id}/verdict` for the full report."
            )
        }


class SlackThreadedReporter:
    """
    Posts threaded progress updates and final verdict cards in Slack.
    Wraps a slack_sdk.WebClient (or any compatible client).
    """

    def __init__(self, slack_client: Any):
        self.client = slack_client

    def post_initial_message(self, channel: str, job_id: str, repo_url: str) -> str:
        """Post the initial ack message and return thread_ts."""
        response = self.client.chat_postMessage(
            channel=channel,
            text=f"🚢 Initializing review for `{repo_url}` (Job: `{job_id}`)...",
        )
        return response["ts"]

    def post_progress_update(self, channel: str, thread_ts: str, stage: str, message: str) -> None:
        """Post a progress update in the thread."""
        self.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=format_progress_message(stage, message),
        )

    def post_error(self, channel: str, thread_ts: str, review_id: str, error: str) -> None:
        """Post an error message in the thread."""
        self.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=format_error_message(review_id, error),
        )

    def post_final_verdict_card(
        self,
        channel: str,
        thread_ts: str,
        verdict: Any,
        job_id: str = "",
    ) -> None:
        """Post the final verdict card as a rich Block Kit message."""
        blocks = format_verdict_card(verdict, job_id)
        self.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"Review verdict: {verdict.decision.value.upper()}",
            blocks=blocks,
            reply_broadcast=True,
        )
