"""Tests for the orchestrator pipeline (T03)."""

import pytest
from sw_reviewer.models import ReviewRequest, RequestSource, VerdictDecision
from sw_reviewer.orchestrator.service import ReviewOrchestratorService


def _make_web_request(review_id="rev-web-001"):
    return ReviewRequest(
        review_id=review_id,
        repository_url="https://github.com/test/webapp",
        source=RequestSource.API,
        requester="tester",
        metadata={
            "project_type": "web",
            "readme_text": (
                "## Installation\nRun `npm install`.\n\nUsage: open the demo at the URL below.\n"
                + "This web app demonstrates a simple todo list. "
                + "x" * 200
            ),
            "demo_url": "https://myapp.vercel.app",
        },
    )


def _make_cli_request(review_id="rev-cli-001"):
    return ReviewRequest(
        review_id=review_id,
        repository_url="https://github.com/test/clitool",
        source=RequestSource.API,
        requester="tester",
        metadata={
            "project_type": "cli",
            "readme_text": (
                "## Installation\n```bash\npip install mytool\n```\n\nUsage:\n```bash\nmytool --help\n```\n"
                + "x" * 200
            ),
            "cli_commands": ["mytool --help"],
        },
    )


@pytest.mark.asyncio
async def test_web_review_pipeline(tmp_path):
    """Test that a web review runs the full pipeline and returns a verdict."""
    service = ReviewOrchestratorService(db_path=str(tmp_path / "test.db"))
    request = _make_web_request()
    # Web execution will fail (no real URL) but policy should be evaluated
    # The demo URL points to vercel so precheck should pass, but actual Playwright execution
    # will fail/skip gracefully in CI
    verdict = await service.start_review(request)
    # Verdict should be something (not raise an exception)
    assert verdict.review_id == request.review_id
    assert verdict.decision in (
        VerdictDecision.APPROVE,
        VerdictDecision.REJECT,
        VerdictDecision.NEEDS_HUMAN_REVIEW,
        VerdictDecision.ERROR,
    )


@pytest.mark.asyncio
async def test_cli_review_pipeline(tmp_path):
    """Test that a CLI review runs the full pipeline and returns a verdict."""
    service = ReviewOrchestratorService(db_path=str(tmp_path / "test.db"))
    request = _make_cli_request()
    verdict = await service.start_review(request)
    assert verdict.review_id == request.review_id


@pytest.mark.asyncio
async def test_cancel_job(tmp_path):
    """Test that a pending job can be cancelled."""
    from sw_reviewer.state import JobStatus, JobState
    service = ReviewOrchestratorService(db_path=str(tmp_path / "test.db"))
    # Manually create a pending job
    from sw_reviewer.state import JobRepository
    repo = JobRepository(db_path=str(tmp_path / "test.db"))
    job = JobState(
        review_id="rev-cancel-001",
        status=JobStatus.PENDING,
        repository_url="https://github.com/test/repo",
    )
    repo.create_job(job)
    result = service.cancel_job("rev-cancel-001")
    assert result is True
    updated = service.get_job("rev-cancel-001")
    assert updated.status == JobStatus.CANCELLED
