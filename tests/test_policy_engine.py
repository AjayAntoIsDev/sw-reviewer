"""Tests for the policy evaluation engine (T14, T15)."""

import pytest
from sw_reviewer.models import ReviewRequest, RequestSource, PolicyLevel
from sw_reviewer.policy.rules import (
    check_repo_url_present,
    check_project_type_supported,
    check_readme_sufficient,
    check_open_source_heuristic,
    check_web_demo_url_present,
    check_web_demo_host_allowed,
    check_cli_commands_present,
    check_execution_success,
)
from sw_reviewer.policy.evaluator import evaluate_policies, generate_verdict
from sw_reviewer.models import VerdictDecision


def _make_request(metadata=None):
    return ReviewRequest(
        review_id="rev-test",
        repository_url="https://github.com/test/myproject",
        source=RequestSource.API,
        requester="tester",
        metadata=metadata or {},
    )


# ── Rule unit tests ─────────────────────────────────────────────────────────

def test_repo_url_present_pass():
    passed, _ = check_repo_url_present("https://github.com/test/repo")
    assert passed


def test_repo_url_present_fail():
    passed, reason = check_repo_url_present("")
    assert not passed
    assert "missing" in reason.lower()


def test_project_type_supported():
    assert check_project_type_supported("web")[0]
    assert check_project_type_supported("cli")[0]
    assert not check_project_type_supported("mobile")[0]


def test_readme_sufficient_pass():
    readme = "## Installation\n\nRun `pip install myproject` to install.\n\nUsage: myproject --help\n" + "x" * 200
    passed, _ = check_readme_sufficient(readme)
    assert passed


def test_readme_sufficient_fail_short():
    passed, reason = check_readme_sufficient("tiny")
    assert not passed
    assert "short" in reason.lower()


def test_readme_sufficient_fail_no_keywords():
    passed, reason = check_readme_sufficient("x" * 200)
    assert not passed


def test_open_source_heuristic():
    assert check_open_source_heuristic("https://github.com/test/repo")[0]
    assert not check_open_source_heuristic("https://bitbucket.private.corp/repo")[0]


def test_web_demo_url_present():
    assert check_web_demo_url_present("https://myapp.vercel.app")[0]
    assert not check_web_demo_url_present("")[0]


def test_web_demo_host_blocked():
    assert not check_web_demo_host_allowed("https://render.com/my-app")[0]
    assert not check_web_demo_host_allowed("https://abc.ngrok.io")[0]
    assert check_web_demo_host_allowed("https://myapp.vercel.app")[0]


def test_cli_commands_present():
    assert check_cli_commands_present(["myapp --help", "myapp run"])[0]
    assert not check_cli_commands_present([])[0]


def test_execution_success():
    assert check_execution_success(True)[0]
    assert not check_execution_success(False)[0]


# ── Evaluator integration tests ─────────────────────────────────────────────

def test_evaluate_web_project_approve():
    req = _make_request()
    ev = {
        "project_type": "web",
        "readme_text": "## Installation\nRun `npm install` to install.\nUsage: open the app at the demo URL.\n" + "x" * 200,
        "demo_url": "https://myapp.vercel.app",
        "any_execution_success": True,
    }
    results = evaluate_policies(req, ev)
    verdict = generate_verdict("rev-test", results)
    assert verdict.decision == VerdictDecision.APPROVE


def test_evaluate_web_project_reject_no_demo():
    req = _make_request()
    ev = {
        "project_type": "web",
        "readme_text": "## Installation\nRun `npm install` to install.\n" + "x" * 200,
        "demo_url": "",  # Missing demo URL
        "any_execution_success": False,
    }
    results = evaluate_policies(req, ev)
    verdict = generate_verdict("rev-test", results)
    assert verdict.decision == VerdictDecision.REJECT


def test_evaluate_cli_project_approve():
    req = _make_request()
    ev = {
        "project_type": "cli",
        "readme_text": "## Installation\nRun `pip install mytool` to install.\nUsage: mytool --help\n" + "x" * 200,
        "cli_commands": ["mytool --help", "mytool run"],
        "any_execution_success": True,
    }
    results = evaluate_policies(req, ev)
    verdict = generate_verdict("rev-test", results)
    assert verdict.decision == VerdictDecision.APPROVE


def test_evaluate_cli_project_reject_no_commands():
    req = _make_request()
    ev = {
        "project_type": "cli",
        "readme_text": "## Installation\nRun `pip install mytool`.\nUsage: run the tool.\n" + "x" * 200,
        "cli_commands": [],
        "any_execution_success": False,
    }
    results = evaluate_policies(req, ev)
    verdict = generate_verdict("rev-test", results)
    assert verdict.decision == VerdictDecision.REJECT
