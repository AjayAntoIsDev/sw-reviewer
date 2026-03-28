"""Agent that wraps the review pipeline, usable via web UI and Slack.

Responds to prompts like "review the project 5683" by calling stage tools
in sequence. Each tool call is visible in the web UI and Slack streaming.
For all other messages it falls back to the legacy browser/shipwrights agent.
"""

from __future__ import annotations

import json

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from sw_reviewer import browser_tools, shipwrights_tools
from sw_reviewer.config import AppConfig
from sw_reviewer.models import ChecksResult, PreCheckResult, ReviewResult
from sw_reviewer.pipeline import (
    ProjectDetails,
    fetch_project_details,
    run_checks,
    run_precheck,
    run_reviewer,
)
from sw_reviewer.prompts import SYSTEM_PROMPT

# Module-level cache so stage tools can pass data between calls
_project_cache: dict[int, ProjectDetails] = {}
_precheck_cache: dict[int, PreCheckResult] = {}
_checks_cache: dict[int, ChecksResult | None] = {}


def _format_review(ship_cert_id: int, review: ReviewResult) -> str:
    """Format a ReviewResult into a readable markdown string."""
    parts: list[str] = [
        f'## Review for Ship Cert #{ship_cert_id}',
        f'**Verdict:** {review.verdict.value}',
        f'**Project type:** {review.project_type}',
        '',
        '### Reasoning',
        review.reasoning,
    ]

    if review.required_fixes:
        parts.append('')
        parts.append('### Required fixes')
        for fix in review.required_fixes:
            parts.append(f'- {fix}')

    if review.feedback:
        parts.append('')
        parts.append('### Feedback')
        for note in review.feedback:
            parts.append(f'- {note}')

    if review.special_flags:
        parts.append('')
        parts.append(f'**Flags:** {", ".join(review.special_flags)}')

    parts.append('')
    parts.append(f'**Checks performed:** {", ".join(review.checks_performed)}')

    return '\n'.join(parts)


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


_PIPELINE_INSTRUCTIONS = """\

## Review pipeline

When the user asks to review a project (e.g. "review the project 5683"),
call these tools **in order**:

1. `fetch_project(ship_cert_id)` — fetches project details from the API.
2. `pipeline_precheck(ship_cert_id)` — runs Stage 1 pre-checks.
   Read the result. If `instant_reject` is true, skip straight to step 4.
3. `pipeline_checks(ship_cert_id)` — runs Stage 2 deeper checks.
4. `pipeline_review(ship_cert_id)` — runs Stage 3 final verdict.

Present the final result from step 4 to the user as-is (it is markdown).
Do NOT summarise or alter the review output.
"""


def create_pipeline_agent(config: AppConfig) -> Agent:
    """Create an agent with per-stage pipeline tools visible in the UI."""
    agent = Agent(
        f'openrouter:{config.model_name}',
        instructions=f'{SYSTEM_PROMPT}\n{_PIPELINE_INSTRUCTIONS}',
        instrument=True,
        tools=_collect_browser_tools() + _collect_shipwrights_tools(),
    )

    # ── Stage tools ──────────────────────────────────────────────

    @agent.tool_plain
    async def fetch_project(ship_cert_id: int) -> str:
        """Fetch project details from the Shipwrights API.

        Must be called first before any pipeline stage.
        Returns project metadata as JSON.
        """
        try:
            proj = await fetch_project_details(ship_cert_id)
            _project_cache[ship_cert_id] = proj
            return json.dumps({
                'ship_cert_id': proj.ship_cert_id,
                'repo_url': proj.repo_url,
                'demo_url': proj.demo_url,
                'description': proj.description[:500] if proj.description else None,
                'api_project_type': proj.api_project_type,
            }, indent=2)
        except RuntimeError as exc:
            return f'❌ {exc}'

    @agent.tool_plain
    async def pipeline_precheck(ship_cert_id: int) -> str:
        """Stage 1: Run pre-checks (repo access, README, project type, etc.).

        Call fetch_project first. Returns structured pre-check results as JSON.
        """
        proj = _project_cache.get(ship_cert_id)
        if proj is None:
            return '❌ Call fetch_project first.'
        try:
            precheck = await run_precheck(config, proj)
            _precheck_cache[ship_cert_id] = precheck
            return precheck.model_dump_json(indent=2)
        except Exception as exc:
            return f'❌ Pre-check failed: {exc}'

    @agent.tool_plain
    async def pipeline_checks(ship_cert_id: int) -> str:
        """Stage 2: Run deeper checks (README quality, demo validity, AI, commits, etc.).

        Only call if pre-check did NOT instant-reject. Returns check results as JSON.
        """
        proj = _project_cache.get(ship_cert_id)
        precheck = _precheck_cache.get(ship_cert_id)
        if proj is None or precheck is None:
            return '❌ Call fetch_project and pipeline_precheck first.'
        if precheck.instant_reject:
            _checks_cache[ship_cert_id] = None
            return 'Skipped — pre-check was an instant reject.'
        try:
            checks = await run_checks(config, proj, precheck)
            _checks_cache[ship_cert_id] = checks
            return checks.model_dump_json(indent=2)
        except Exception as exc:
            return f'❌ Checks failed: {exc}'

    @agent.tool_plain
    async def pipeline_review(ship_cert_id: int) -> str:
        """Stage 3: Compile final verdict from pre-check and checks results.

        Returns the formatted review with verdict, reasoning, and required fixes.
        """
        proj = _project_cache.get(ship_cert_id)
        precheck = _precheck_cache.get(ship_cert_id)
        if proj is None or precheck is None:
            return '❌ Call fetch_project and pipeline_precheck first.'
        checks = _checks_cache.get(ship_cert_id)
        try:
            review = await run_reviewer(config, proj, precheck, checks)
            # Clean up caches
            _project_cache.pop(ship_cert_id, None)
            _precheck_cache.pop(ship_cert_id, None)
            _checks_cache.pop(ship_cert_id, None)
            return _format_review(ship_cert_id, review)
        except Exception as exc:
            return f'❌ Review failed: {exc}'

    return agent
