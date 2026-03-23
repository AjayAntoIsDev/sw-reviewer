"""Policy evaluation engine: runs rules against request + evidence."""

from typing import List, Optional, Dict, Any

from ..models import (
    ReviewRequest,
    PolicyCheckResult,
    FinalVerdict,
    VerdictDecision,
    PolicyLevel,
)
from .schema import POLICY_RULE_MAP
from .rules import (
    check_repo_url_present,
    check_project_type_supported,
    check_readme_sufficient,
    check_open_source_heuristic,
    check_web_demo_url_present,
    check_web_demo_host_allowed,
    check_cli_commands_present,
    check_execution_success,
    check_no_special_review_account,
)


def evaluate_policies(
    request: ReviewRequest,
    evidence_summary: Optional[Dict[str, Any]] = None,
) -> List[PolicyCheckResult]:
    """
    Run all applicable policy checks against the request and accumulated evidence.

    Args:
        request: The normalised ReviewRequest.
        evidence_summary: Optional dict with keys like:
            - readme_text: str
            - demo_url: str
            - project_type: str
            - cli_commands: list[str]
            - any_execution_success: bool

    Returns:
        List of PolicyCheckResult for every applicable rule.
    """
    ev = evidence_summary or {}
    metadata = request.metadata
    project_type = ev.get("project_type") or metadata.get("project_type", "")
    readme_text = ev.get("readme_text") or metadata.get("readme_text", "")
    demo_url = ev.get("demo_url") or metadata.get("demo_url", "")
    cli_commands = ev.get("cli_commands") or metadata.get("cli_commands", [])
    any_success = ev.get("any_execution_success", False)

    results: List[PolicyCheckResult] = []

    def _result(
        rule_id: str,
        passed: bool,
        reasoning: str,
        evidence_refs: Optional[List[str]] = None,
    ) -> PolicyCheckResult:
        rule = POLICY_RULE_MAP[rule_id]
        return PolicyCheckResult(
            policy=rule,
            passed=passed,
            reasoning=reasoning,
            evidence_refs=evidence_refs or [],
        )

    # Universal checks
    passed, reason = check_repo_url_present(str(request.repository_url))
    results.append(_result("repo_url_present", passed, reason))

    passed, reason = check_project_type_supported(project_type)
    results.append(_result("project_type_supported", passed, reason))

    passed, reason = check_readme_sufficient(readme_text)
    results.append(_result("readme_sufficient", passed, reason))

    passed, reason = check_open_source_heuristic(str(request.repository_url))
    results.append(_result("open_source_heuristic", passed, reason))

    passed, reason = check_no_special_review_account(metadata)
    results.append(_result("no_special_review_account", passed, reason))

    # not_previously_submitted is always manual_only — mark as passed with note
    not_submitted_rule = POLICY_RULE_MAP["not_previously_submitted"]
    results.append(
        PolicyCheckResult(
            policy=not_submitted_rule,
            passed=True,
            reasoning="Manual confirmation required; assumed OK pending human review.",
            evidence_refs=[],
        )
    )

    # Web-specific checks
    if project_type.lower() == "web":
        passed, reason = check_web_demo_url_present(demo_url)
        results.append(_result("web_demo_url_present", passed, reason))
        passed, reason = check_web_demo_host_allowed(demo_url)
        results.append(_result("web_demo_host_allowed", passed, reason))

    # CLI-specific checks
    if project_type.lower() == "cli":
        passed, reason = check_cli_commands_present(cli_commands)
        results.append(_result("cli_commands_present", passed, reason))

    # Execution check (applies to both)
    passed, reason = check_execution_success(any_success)
    results.append(_result("execution_success", passed, reason))

    return results


def generate_verdict(
    review_id: str,
    check_results: List[PolicyCheckResult],
    web_results: Optional[list] = None,
    cli_results: Optional[list] = None,
    report_url: Optional[str] = None,
) -> FinalVerdict:
    """
    Generate the final verdict from policy check results.

    Rules:
    - REJECT if any REQUIRED check fails.
    - NEEDS_HUMAN_REVIEW if any MANUAL_ONLY check is not passed.
    - APPROVE if all REQUIRED checks pass (ADVISORY warnings noted but not blocking).
    """
    web_results = web_results or []
    cli_results = cli_results or []

    required_failures = [
        r for r in check_results
        if r.policy.level == PolicyLevel.REQUIRED and not r.passed
    ]

    if required_failures:
        failure_list = "; ".join(
            f"{r.policy.id}: {r.reasoning}" for r in required_failures
        )
        decision = VerdictDecision.REJECT
        summary = f"Rejected: {len(required_failures)} required check(s) failed. {failure_list}"
    elif any(
        r.policy.level == PolicyLevel.MANUAL_ONLY and not r.passed
        for r in check_results
    ):
        decision = VerdictDecision.NEEDS_HUMAN_REVIEW
        summary = (
            "Needs human review: one or more manual-only checks could not be "
            "confirmed automatically."
        )
    else:
        decision = VerdictDecision.APPROVE
        advisory_warnings = [
            r for r in check_results
            if r.policy.level == PolicyLevel.ADVISORY and not r.passed
        ]
        if advisory_warnings:
            summary = f"Approved with {len(advisory_warnings)} advisory warning(s)."
        else:
            summary = "Approved: all required checks passed."

    return FinalVerdict(
        review_id=review_id,
        decision=decision,
        summary=summary,
        check_results=check_results,
        web_results=web_results,
        cli_results=cli_results,
        report_url=report_url,
    )
