from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from pydantic_ai import Agent, PromptedOutput, UsageLimits
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
        retries=5,
        tools=_collect_browser_tools() + _collect_shipwrights_tools(),
        output_type=PromptedOutput(PreCheckResult),
    )

def _create_checks_agent(config: AppConfig) -> Agent:
    prompt = _load_prompt('checks.md')
    demo_guidelines = _load_prompt('demo_guidelines.md')
    full_prompt = f"{prompt}\n\n---\n\n## Demo Guidelines Reference\n\n{demo_guidelines}"
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=full_prompt,
        instrument=True,
        retries=5,
        tools=_collect_browser_tools() + _collect_shipwrights_tools(),
        output_type=PromptedOutput(ChecksResult),
    )

def _create_reviewer_agent(config: AppConfig) -> Agent:
    prompt = _load_prompt('reviewer.md')
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=prompt,
        instrument=True,
        retries=10,
        output_type=PromptedOutput(ReviewResult),
    )

@dataclass
class ProjectDetails:
    """Parsed submission details from the Shipwrights API."""
    ship_cert_id: int
    repo_url: str
    demo_url: str | None
    description: str
    api_project_type: str | None
    raw: dict


async def fetch_project_details(ship_cert_id: int) -> ProjectDetails:
    """Fetch and parse project details from the Shipwrights API."""
    raw = await shipwrights_tools.shipwrights_get_ship_cert_details(ship_cert_id)
    data = json.loads(raw)

    if not data.get('ok'):
        raise RuntimeError(
            f"Failed to fetch ship cert {ship_cert_id}: {data.get('error', 'unknown error')}"
        )

    details = data['data']
    links = details.get('links') or {}
    repo_url = links.get('repo', '')
    demo_url = links.get('demo') or links.get('play') or None

    if not repo_url:
        raise RuntimeError(
            f"Ship cert {ship_cert_id} has no repo URL in links: {links}"
        )

    return ProjectDetails(
        ship_cert_id=ship_cert_id,
        repo_url=repo_url,
        demo_url=demo_url,
        description=details.get('desc') or '',
        api_project_type=details.get('ai_summary_type'),
        raw=details,
    )


async def run_precheck(config: AppConfig, proj: ProjectDetails) -> PreCheckResult:
    """Stage 1: Run pre-checks and return structured result."""
    logger.info("Stage 1: Running pre-check for %s", proj.repo_url)
    agent = _create_precheck_agent(config)
    result = await agent.run(
        f"Review this project submission:\n"
        f"- Ship Cert ID: {proj.ship_cert_id}\n"
        f"- Repository URL: {proj.repo_url}\n"
        f"- Demo URL: {proj.demo_url or 'Not provided'}\n"
        f"- API-reported project type: {proj.api_project_type or 'Not provided'}\n"
        f"- Description: {proj.description or 'Not provided'}\n\n"
        f"Run the pre-checks and return the results."
    )
    logger.info("Pre-check complete: instant_reject=%s", result.output.instant_reject)
    return result.output


async def run_checks(
    config: AppConfig,
    proj: ProjectDetails,
    precheck: PreCheckResult,
) -> ChecksResult:
    """Stage 2: Run deeper checks. Only call if precheck did not instant-reject."""
    logger.info("Stage 2: Running checks")
    agent = _create_checks_agent(config)
    result = await agent.run(
        f"Run all checks on this project:\n\n"
        f"Pre-check results:\n{precheck.model_dump_json(indent=2)}\n\n"
        f"Description: {proj.description or 'Not provided'}\n"
        f"Repository URL: {proj.repo_url}\n"
        f"Demo URL: {proj.demo_url or 'Not provided'}\n",
        usage_limits=UsageLimits(tool_calls_limit=100)
    )
    logger.info("Checks complete")
    return result.output


async def run_reviewer(
    config: AppConfig,
    proj: ProjectDetails,
    precheck: PreCheckResult,
    checks: ChecksResult | None,
) -> ReviewResult:
    """Stage 3: Compile final verdict from pre-check and checks results."""
    logger.info("Stage 3: Running reviewer")
    agent = _create_reviewer_agent(config)
    prompt = (
        f"Compile the final review verdict.\n\n"
        f"Pre-check results:\n{precheck.model_dump_json(indent=2)}\n\n"
    )
    if checks is not None:
        prompt += f"Check results:\n{checks.model_dump_json(indent=2)}\n\n"
    else:
        prompt += "Checks were SKIPPED because pre-check resulted in instant reject.\n\n"
    prompt += (
        f"Description: {proj.description or 'Not provided'}\n"
        f"Repository URL: {proj.repo_url}\n"
        f"Demo URL: {proj.demo_url or 'Not provided'}\n"
    )

    result = await agent.run(prompt)
    logger.info("Review complete: verdict=%s", result.output.verdict)
    return result.output


async def run_review_pipeline(
    config: AppConfig,
    ship_cert_id: int,
    repo_url: str,
    demo_url: str | None = None,
    api_project_type: str | None = None,
    description: str | None = None,
) -> ReviewResult:
    """Run the full 3-stage review pipeline end-to-end."""
    proj = ProjectDetails(
        ship_cert_id=ship_cert_id,
        repo_url=repo_url,
        demo_url=demo_url,
        description=description or '',
        api_project_type=api_project_type,
        raw={},
    )

    precheck = await run_precheck(config, proj)

    if precheck.instant_reject:
        logger.info("Instant reject — skipping checks stage")
        checks = None
    else:
        checks = await run_checks(config, proj, precheck)

    return await run_reviewer(config, proj, precheck, checks)
