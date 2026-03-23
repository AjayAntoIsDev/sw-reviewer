"""Tests for Pydantic data contract models (T02)."""

import pytest
from sw_reviewer.models import (
    PolicyLevel,
    PolicyCheck,
    ReviewRequest,
    RequestSource,
    EvidenceItem,
    EvidenceBundle,
    PolicyCheckResult,
    WebFlowResult,
    CLICommandResult,
    VerdictDecision,
    FinalVerdict,
)


def test_policy_check_model():
    check = PolicyCheck(
        id="test_check",
        category="docs",
        level=PolicyLevel.REQUIRED,
        description="A test check",
    )
    assert check.id == "test_check"
    assert check.level == PolicyLevel.REQUIRED


def test_review_request_model():
    req = ReviewRequest(
        review_id="rev-001",
        repository_url="https://github.com/test/repo",
        source=RequestSource.API,
        requester="user123",
    )
    assert req.review_id == "rev-001"
    assert req.branch == "main"


def test_evidence_bundle():
    item = EvidenceItem(
        id="ev-001",
        type="screenshot",
        source_stage="web",
        payload={"path": "/artifacts/screenshot.png"},
    )
    bundle = EvidenceBundle(review_id="rev-001", items=[item])
    assert len(bundle.items) == 1


def test_cli_command_result():
    result = CLICommandResult(
        command="python --version",
        exit_code=0,
        duration_ms=100,
        success=True,
    )
    assert result.success is True
    assert result.exit_code == 0


def test_final_verdict_approve():
    verdict = FinalVerdict(
        review_id="rev-001",
        decision=VerdictDecision.APPROVE,
        summary="All checks passed.",
    )
    assert verdict.decision == VerdictDecision.APPROVE
