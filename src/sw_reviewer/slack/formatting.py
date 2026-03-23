"""Slack Block Kit formatting helpers."""

from typing import Any, Dict, List, Optional

from ..models import FinalVerdict, VerdictDecision

# Emoji map for verdict decisions
VERDICT_EMOJI = {
    VerdictDecision.APPROVE: "✅",
    VerdictDecision.REJECT: "❌",
    VerdictDecision.NEEDS_HUMAN_REVIEW: "👀",
    VerdictDecision.ERROR: "🚨",
}


def format_verdict_card(verdict: FinalVerdict, job_id: str) -> List[Dict[str, Any]]:
    """
    Build Slack Block Kit blocks for the final verdict card.

    Returns a list of block dicts ready to pass to chat.postMessage blocks=[...].
    """
    emoji = VERDICT_EMOJI.get(verdict.decision, "❓")
    decision_label = verdict.decision.value.replace("_", " ").upper()

    blocks: List[Dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Review Verdict: {decision_label}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Job ID:*\n`{job_id}`"},
                {"type": "mrkdwn", "text": f"*Decision:*\n{decision_label}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{verdict.summary}",
            },
        },
    ]

    # Policy checklist section
    if verdict.check_results:
        checklist_lines = []
        for r in verdict.check_results[:10]:  # Cap at 10 for readability
            icon = "✅" if r.passed else "❌"
            checklist_lines.append(f"{icon} *{r.policy.id}*: {r.reasoning[:80]}")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Policy Checklist:*\n" + "\n".join(checklist_lines),
            },
        })

    # Report link button
    report_url = verdict.report_url or "https://example.com/report"
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📄 View Report", "emoji": True},
                "url": report_url,
                "action_id": "view_report",
            }
        ],
    })

    return blocks


def format_progress_message(stage: str, message: str) -> str:
    """Format a stage progress message."""
    stage_emoji = {
        "policy_prechecks": "🔍",
        "web_testing": "🌐",
        "cli_testing": "💻",
        "evidence": "📦",
        "policy_eval": "⚖️",
        "verdict": "📋",
        "report": "📄",
    }
    emoji = stage_emoji.get(stage.lower(), "🔄")
    return f"{emoji} *[{stage}]* {message}"


def format_error_message(review_id: str, error: str) -> str:
    """Format a review error message."""
    return f"🚨 *Review `{review_id}` failed*\nError: {error[:200]}"
