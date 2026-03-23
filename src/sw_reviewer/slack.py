import logging
from typing import Any, Dict

from pydantic import BaseModel
from .models import ReviewRequest, JobStatus
from .orchestrator import ReviewOrchestrator

logger = logging.getLogger(__name__)

class SlackIntake:
    """Handles Slack slash commands and intakes for the Shipwright AI Reviewer."""
    
    def __init__(self, orchestrator: ReviewOrchestrator):
        self.orchestrator = orchestrator

    def handle_slash_command(self, command: str, user_id: str, text: str) -> Dict[str, Any]:
        """
        Main router for Slack slash commands.
        /review start <repo_url>
        /review status <job_id>
        /review cancel <job_id>
        /review verdict <job_id>
        """
        if command != "/review":
            return {"text": f"Unknown command: {command}"}

        parts = text.strip().split(" ", 1)
        action = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if action == "start":
            return self._handle_start(user_id, args)
        elif action == "status":
            return self._handle_status(user_id, args)
        elif action == "cancel":
            return self._handle_cancel(user_id, args)
        elif action == "verdict":
            return self._handle_verdict(user_id, args)
        else:
            return {"text": "Usage: /review [start|status|cancel|verdict] [args...]"}

    def _handle_start(self, user_id: str, repo_url: str) -> Dict[str, Any]:
        if not repo_url:
            return {"text": "Please provide a repository URL. Usage: /review start <repo_url>"}
        
        job_id = self.orchestrator.start_review(repo_url=repo_url, requester=user_id)
        return {
            "response_type": "in_channel",
            "text": f"🚀 Started review for `{repo_url}`. Job ID: `{job_id}`"
        }

    def _handle_status(self, user_id: str, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {"text": "Please provide a job ID. Usage: /review status <job_id>"}
        
        status = self.orchestrator.get_status(job_id)
        if not status:
            return {"text": f"Job `{job_id}` not found."}
            
        return {"text": f"Job `{job_id}` status: *{status.name}*"}

    def _handle_cancel(self, user_id: str, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {"text": "Please provide a job ID. Usage: /review cancel <job_id>"}
            
        success = self.orchestrator.cancel_job(job_id)
        if success:
            return {"text": f"Job `{job_id}` has been cancelled."}
        return {"text": f"Failed to cancel job `{job_id}` (may already be finished or not found)."}

    def _handle_verdict(self, user_id: str, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {"text": "Please provide a job ID. Usage: /review verdict <job_id>"}
            
        verdict = self.orchestrator.get_verdict(job_id)
        if not verdict:
            return {"text": f"Verdict for job `{job_id}` is not available yet."}
            
        return {"text": f"Verdict for `{job_id}`: *{verdict.decision}*\nDetails: {verdict.summary}"}


class SlackThreadedReporter:
    """Handles threaded progress updates and final verdict cards in Slack."""
    
    def __init__(self, slack_client: Any):
        # slack_client would be e.g. a slack_sdk.WebClient
        self.client = slack_client

    def post_initial_message(self, channel: str, job_id: str, repo_url: str) -> str:
        """Posts the initial message and returns the thread_ts."""
        response = self.client.chat_postMessage(
            channel=channel,
            text=f"🚢 Initializing review for {repo_url} (Job: `{job_id}`)..."
        )
        return response["ts"]

    def post_progress_update(self, channel: str, thread_ts: str, stage: str, message: str):
        """Posts a progress update in the job's thread."""
        self.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"🔄 *[{stage}]* {message}"
        )

    def post_final_verdict_card(self, channel: str, thread_ts: str, verdict: Any):
        """Posts the final verdict as a rich Slack Block Kit layout."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Review Verdict: {verdict.decision.upper()}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{verdict.summary}*\n\nDetailed PDF Report is available."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Report PDF"
                        },
                        "url": verdict.report_url if hasattr(verdict, 'report_url') else "https://example.com/report.pdf",
                        "action_id": "view_report"
                    }
                ]
            }
        ]
        
        # Post in thread and optionally un-thread to channel
        self.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"Review Verdict: {verdict.decision}",
            blocks=blocks,
            reply_broadcast=True
        )
