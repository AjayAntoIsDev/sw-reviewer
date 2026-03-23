"""Tests for Slack command handler (T05, T06)."""

import pytest
from sw_reviewer.slack.commands import SlackCommandHandler
from sw_reviewer.slack.formatting import format_verdict_card, format_progress_message
from sw_reviewer.models import FinalVerdict, VerdictDecision, PolicyCheckResult, PolicyCheck, PolicyLevel
from sw_reviewer.state import JobRepository, JobStatus, JobState


def _make_handler(tmp_path):
    return SlackCommandHandler(db_path=str(tmp_path / "test.db"))


def _make_job(tmp_path, review_id="rev-slack-001", status=JobStatus.PENDING):
    repo = JobRepository(db_path=str(tmp_path / "test.db"))
    job = JobState(
        review_id=review_id,
        status=status,
        repository_url="https://github.com/test/repo",
    )
    repo.create_job(job)
    return repo


# ── SlackCommandHandler tests ────────────────────────────────────────────────

def test_unknown_command(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/unknown", "user1", "start https://github.com/test/repo")
    assert "Unknown" in result["text"]


def test_start_missing_url(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "start")
    assert "repository URL" in result["text"].lower() or "provide" in result["text"].lower()


def test_start_success(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "start https://github.com/test/repo project_type=web")
    assert "review_id" in result["text"].lower() or "job id" in result["text"].lower() or "job:" in result["text"].lower()
    assert result.get("response_type") == "in_channel"


def test_start_invalid_type(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "start https://github.com/test/repo project_type=mobile")
    assert "invalid" in result["text"].lower()


def test_status_not_found(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "status nonexistent-job")
    assert "not found" in result["text"].lower()


def test_status_found(tmp_path):
    _make_job(tmp_path, "rev-slack-status")
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "status rev-slack-status")
    assert "pending" in result["text"].lower()


def test_cancel_success(tmp_path):
    _make_job(tmp_path, "rev-slack-cancel")
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "cancel rev-slack-cancel")
    assert "cancelled" in result["text"].lower()


def test_cancel_not_found(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "cancel no-such-job")
    assert "not found" in result["text"].lower()


def test_verdict_not_complete(tmp_path):
    _make_job(tmp_path, "rev-slack-verdict", status=JobStatus.RUNNING)
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "verdict rev-slack-verdict")
    assert "not" in result["text"].lower() or "available" in result["text"].lower()


def test_verdict_not_found(tmp_path):
    handler = _make_handler(tmp_path)
    result = handler.handle_command("/review", "user1", "verdict no-such-job")
    assert "not found" in result["text"].lower()


# ── Formatting tests ─────────────────────────────────────────────────────────

def test_format_verdict_card():
    check = PolicyCheckResult(
        policy=PolicyCheck(id="repo_url_present", category="docs", level=PolicyLevel.REQUIRED, description="Test"),
        passed=True,
        reasoning="Present",
    )
    verdict = FinalVerdict(
        review_id="rev-fmt-001",
        decision=VerdictDecision.APPROVE,
        summary="All passed.",
        check_results=[check],
    )
    blocks = format_verdict_card(verdict, "rev-fmt-001")
    assert isinstance(blocks, list)
    assert len(blocks) > 0
    # Verify header block
    header = blocks[0]
    assert header["type"] == "header"
    assert "APPROVE" in header["text"]["text"]


def test_format_progress_message():
    msg = format_progress_message("web_testing", "Running UI flows")
    assert "web_testing" in msg or "web" in msg.lower()
    assert "Running UI flows" in msg
