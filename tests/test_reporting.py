"""Tests for the reporting pipeline (T16)."""

import pytest
from pathlib import Path
from sw_reviewer.models import FinalVerdict, VerdictDecision, PolicyCheckResult, PolicyCheck, PolicyLevel
from sw_reviewer.reporting.typst import render_typst_source, generate_report
from sw_reviewer.reporting.bundle import ArtifactBundle


def _make_verdict():
    check = PolicyCheckResult(
        policy=PolicyCheck(id="repo_url_present", category="docs", level=PolicyLevel.REQUIRED, description="Test"),
        passed=True,
        reasoning="URL present",
    )
    return FinalVerdict(
        review_id="rev-report-001",
        decision=VerdictDecision.APPROVE,
        summary="All checks passed.",
        check_results=[check],
    )


def test_render_typst_source():
    verdict = _make_verdict()
    source = render_typst_source(verdict, "https://github.com/test/repo")
    assert "APPROVE" in source
    assert "rev-report-001" in source
    assert "repo_url_present" in source


@pytest.mark.asyncio
async def test_generate_report_no_typst(tmp_path):
    verdict = _make_verdict()
    result = await generate_report(
        verdict=verdict,
        repository_url="https://github.com/test/repo",
        output_dir=str(tmp_path / "report"),
        typst_binary="nonexistent_typst_binary",
        compile_pdf=True,  # Will fail gracefully since binary not found
    )
    assert "typ_path" in result
    assert Path(result["typ_path"]).exists()
    assert Path(result["json_path"]).exists()
    assert result["pdf_path"] is None  # No Typst binary


def test_artifact_bundle(tmp_path):
    bundle = ArtifactBundle(review_id="rev-bundle-001", base_dir=str(tmp_path))
    verdict = _make_verdict()
    path = bundle.save_verdict(verdict)
    assert Path(path).exists()
    index = bundle.save_evidence_index()
    assert Path(index).exists()
