"""
Stage pipeline for the review orchestrator.
Each stage function receives a review context dict and returns updated context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..models import (
    ReviewRequest,
    EvidenceBundle,
    EvidenceItem,
    FinalVerdict,
    WebFlowResult,
    CLICommandResult,
)

logger = logging.getLogger(__name__)


async def stage_policy_prechecks(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stage 1: Run policy prechecks before execution.
    Validates that the request has enough data to proceed.
    """
    from ..policy.evaluator import evaluate_policies

    project_type = request.metadata.get("project_type", "")
    readme_text = request.metadata.get("readme_text", "")
    demo_url = request.metadata.get("demo_url", "")
    cli_commands = request.metadata.get("cli_commands", [])

    evidence_summary = {
        "project_type": project_type,
        "readme_text": readme_text,
        "demo_url": demo_url,
        "cli_commands": cli_commands,
        "any_execution_success": False,
    }

    precheck_results = evaluate_policies(request, evidence_summary)
    context["precheck_results"] = precheck_results
    context["evidence_summary"] = evidence_summary

    failed_required = [r for r in precheck_results if r.policy.level.value == "required" and not r.passed]
    if failed_required:
        logger.warning(
            "Review %s has %d required precheck failure(s)", request.review_id, len(failed_required)
        )

    logger.info("Stage prechecks complete for review %s", request.review_id)
    return context


async def stage_web_execution(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 2a: Execute web flows using Playwright."""
    from ..execution.web import WebExecutor, WebFlowSpec
    from ..execution.readme_parser import extract_web_flows
    from ..config import settings

    metadata = request.metadata
    demo_url = metadata.get("demo_url", "")
    readme_text = metadata.get("readme_text", "")

    if not demo_url:
        logger.info("No demo_url for review %s; skipping web execution.", request.review_id)
        context["web_results"] = []
        return context

    # Build flow specs from demo URL and README-documented flows
    flows_from_readme = extract_web_flows(readme_text) if readme_text else []
    specs = [
        WebFlowSpec(
            flow_id="main_demo",
            url=demo_url,
            description="Main demo URL",
            is_auth_flow=bool(metadata.get("auth_instructions")),
        )
    ]
    # Add up to 3 additional flows from README
    for i, flow_name in enumerate(flows_from_readme[:3], start=1):
        specs.append(WebFlowSpec(
            flow_id=f"readme_flow_{i}",
            url=demo_url,
            description=flow_name,
        ))

    executor = WebExecutor(
        artifacts_dir=settings.artifacts_dir,
        headless=settings.playwright_headless,
        timeout_ms=settings.web_timeout_ms,
    )

    evidence_items: List[EvidenceItem] = context.get("evidence_items", [])
    raw_results = await executor.execute_flows(request.review_id, specs)
    web_results = executor.to_web_flow_results(raw_results, evidence_items)

    context["web_results"] = web_results
    context["evidence_items"] = evidence_items
    context["any_execution_success"] = any(r.success for r in web_results)
    logger.info(
        "Web execution complete for review %s: %d/%d flows succeeded",
        request.review_id, sum(1 for r in web_results if r.success), len(web_results),
    )
    return context


async def stage_cli_execution(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 2b: Execute CLI commands in Docker sandbox."""
    from ..execution.cli import CLISandboxRunner, CommandPhase
    from ..execution.readme_parser import extract_shell_commands, categorise_commands
    from ..config import settings

    metadata = request.metadata
    readme_text = metadata.get("readme_text", "")
    command_hints = metadata.get("cli_commands", [])

    if not readme_text and not command_hints:
        logger.info("No README or command hints for review %s; skipping CLI execution.", request.review_id)
        context["cli_results"] = []
        return context

    # Parse commands
    readme_cmds = extract_shell_commands(readme_text) if readme_text else []
    all_cmds = command_hints + [c for c in readme_cmds if c not in command_hints]

    install_cmds, build_cmds, run_cmds = categorise_commands(all_cmds)

    phases = []
    if install_cmds:
        phases.append(CommandPhase("install", install_cmds[:3]))
    if build_cmds:
        phases.append(CommandPhase("build", build_cmds[:3]))
    if run_cmds:
        # For smoke tests, append --help or --version variants
        smoke_cmds = [cmd.split()[0] + " --help" for cmd in run_cmds[:2] if cmd.split()]
        phases.append(CommandPhase("smoke", smoke_cmds[:3] + run_cmds[:3]))

    if not phases:
        logger.info("No parseable CLI phases for review %s.", request.review_id)
        context["cli_results"] = []
        return context

    runner = CLISandboxRunner(
        docker_enabled=settings.docker_enabled,
        docker_image=settings.docker_image,
        timeout_seconds=settings.sandbox_timeout_seconds,
        artifacts_dir=settings.artifacts_dir,
    )

    raw_results = await runner.run_phases(request.review_id, phases)
    cli_results, cli_evidence = runner.to_cli_results_with_evidence(raw_results, request.review_id)

    evidence_items = context.get("evidence_items", [])
    evidence_items.extend(cli_evidence)

    context["cli_results"] = cli_results
    context["evidence_items"] = evidence_items
    context["any_execution_success"] = (
        context.get("any_execution_success", False) or any(r.success for r in cli_results)
    )
    logger.info(
        "CLI execution complete for review %s: %d/%d commands succeeded",
        request.review_id, sum(1 for r in cli_results if r.success), len(cli_results),
    )
    return context


async def stage_evidence_normalization(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 3: Normalize collected evidence into an EvidenceBundle."""
    from ..reporting.bundle import ArtifactBundle
    from ..config import settings

    bundle = ArtifactBundle(review_id=request.review_id, base_dir=settings.artifacts_dir)
    bundle.add_evidence_batch(context.get("evidence_items", []))
    evidence_bundle = bundle.build_bundle()
    bundle.save_evidence_index()

    context["evidence_bundle"] = evidence_bundle
    context["artifact_bundle"] = bundle
    return context


async def stage_policy_evaluation(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 4: Full policy evaluation including execution results."""
    from ..policy.evaluator import evaluate_policies

    evidence_summary = context.get("evidence_summary", {})
    evidence_summary["any_execution_success"] = context.get("any_execution_success", False)

    check_results = evaluate_policies(request, evidence_summary)
    context["check_results"] = check_results
    return context


async def stage_verdict_generation(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 5: Generate the final verdict."""
    from ..policy.evaluator import generate_verdict

    verdict = generate_verdict(
        review_id=request.review_id,
        check_results=context.get("check_results", []),
        web_results=context.get("web_results", []),
        cli_results=context.get("cli_results", []),
        report_url=context.get("report_url"),
    )
    context["verdict"] = verdict
    return context


async def stage_report_generation(
    request: ReviewRequest,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 6: Generate Typst report and persist artifacts."""
    from ..reporting.typst import generate_report
    from ..config import settings

    verdict: Optional[FinalVerdict] = context.get("verdict")
    if not verdict:
        logger.warning("No verdict available for report generation in review %s", request.review_id)
        return context

    output_dir = f"{settings.artifacts_dir}/{request.review_id}/report"
    report_paths = await generate_report(
        verdict=verdict,
        repository_url=str(request.repository_url),
        output_dir=output_dir,
        typst_binary=settings.typst_binary,
        compile_pdf=settings.typst_enabled,
    )

    # Update verdict with report URL
    report_url = report_paths.get("pdf_path") or report_paths.get("typ_path")
    verdict_with_report = verdict.model_copy(update={"report_url": report_url})

    # Save final verdict with report link
    bundle: Optional[Any] = context.get("artifact_bundle")
    if bundle:
        bundle.save_verdict(verdict_with_report)

    context["verdict"] = verdict_with_report
    context["report_paths"] = report_paths
    return context
