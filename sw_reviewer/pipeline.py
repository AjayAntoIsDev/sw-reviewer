from __future__ import annotations
import logging
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.tools import Tool
from sw_reviewer import browser_tools, shipwrights_tools
from sw_reviewer.config import AppConfig
from sw_reviewer.models import PreCheckResult, ChecksResult, ReviewResult

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'

def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()

def _collect_browser_tools() -> list[Tool]:
    return [
        Tool(getattr(browser_tools, name), sequential=True)
        for name in sorted(dir(browser_tools))
        if name.startswith('browser_') and callable(getattr(browser_tools, name))
    ]

def _collect_shipwrights_tools() -> list[Tool]:
    return [
        Tool(getattr(shipwrights_tools, name))
        for name in sorted(dir(shipwrights_tools))
        if name.startswith('shipwrights_') and callable(getattr(shipwrights_tools, name))
    ]

def _create_precheck_agent(config: AppConfig) -> Agent:
    prompt = _load_prompt('precheck.md')
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=prompt,
        instrument=True,
        tools=_collect_browser_tools() + _collect_shipwrights_tools(),
        output_type=PreCheckResult,
    )

def _create_checks_agent(config: AppConfig) -> Agent:
    prompt = _load_prompt('checks.md')
    demo_guidelines = _load_prompt('demo_guidelines.md')
    full_prompt = f"{prompt}\n\n---\n\n## Demo Guidelines Reference\n\n{demo_guidelines}"
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=full_prompt,
        instrument=True,
        tools=_collect_browser_tools() + _collect_shipwrights_tools(),
        output_type=ChecksResult,
    )

def _create_reviewer_agent(config: AppConfig) -> Agent:
    prompt = _load_prompt('reviewer.md')
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=prompt,
        instrument=True,
        output_type=ReviewResult,
    )

async def run_review_pipeline(
    config: AppConfig,
    ship_cert_id: int,
    repo_url: str,
    demo_url: str | None = None,
    api_project_type: str | None = None,
    description: str | None = None,
) -> ReviewResult:
    """Run the full 3-stage review pipeline."""
    
    # Stage 1: Pre-check
    logger.info("Stage 1: Running pre-check for %s", repo_url)
    precheck_agent = _create_precheck_agent(config)
    precheck_input = (
        f"Review this project submission:\n"
        f"- Ship Cert ID: {ship_cert_id}\n"
        f"- Repository URL: {repo_url}\n"
        f"- Demo URL: {demo_url or 'Not provided'}\n"
        f"- API-reported project type: {api_project_type or 'Not provided'}\n"
        f"- Description: {description or 'Not provided'}\n\n"
        f"Run the pre-checks and return the results."
    )
    precheck_result = await precheck_agent.run(precheck_input)
    precheck = precheck_result.output
    logger.info("Pre-check complete: instant_reject=%s", precheck.instant_reject)
    
    # If pre-check is an instant reject, skip to reviewer
    if precheck.instant_reject:
        logger.info("Instant reject — skipping checks stage")
        checks = None
    else:
        # Stage 2: Checks
        logger.info("Stage 2: Running checks")
        checks_agent = _create_checks_agent(config)
        checks_input = (
            f"Run all checks on this project:\n\n"
            f"Pre-check results:\n{precheck.model_dump_json(indent=2)}\n\n"
            f"Description: {description or 'Not provided'}\n"
            f"Repository URL: {repo_url}\n"
            f"Demo URL: {demo_url or 'Not provided'}\n"
        )
        checks_result = await checks_agent.run(checks_input)
        checks = checks_result.output
        logger.info("Checks complete")
    
    # Stage 3: Reviewer
    logger.info("Stage 3: Running reviewer")
    reviewer_agent = _create_reviewer_agent(config)
    reviewer_input = (
        f"Compile the final review verdict.\n\n"
        f"Pre-check results:\n{precheck.model_dump_json(indent=2)}\n\n"
    )
    if checks is not None:
        reviewer_input += f"Check results:\n{checks.model_dump_json(indent=2)}\n\n"
    else:
        reviewer_input += "Checks were SKIPPED because pre-check resulted in instant reject.\n\n"
    reviewer_input += (
        f"Description: {description or 'Not provided'}\n"
        f"Repository URL: {repo_url}\n"
        f"Demo URL: {demo_url or 'Not provided'}\n"
    )
    
    review_result = await reviewer_agent.run(reviewer_input)
    review = review_result.output
    logger.info("Review complete: verdict=%s", review.verdict)
    
    return review
