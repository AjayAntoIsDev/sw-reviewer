"""Single-agent setup for the SW Reviewer.

One agent with review tools, shipwrights tools, and minimal browser fallback.
Returns plain text/markdown — no structured output models.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModelSettings
from pydantic_ai.tools import Tool

from sw_reviewer import review_tools, shipwrights_tools
from sw_reviewer.config import AppConfig

PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def _build_system_prompt() -> str:
    """Combine the tool-usage guide with the full review workflow."""
    from sw_reviewer.prompts import SYSTEM_PROMPT

    precheck = _load_prompt('precheck.md')
    checks = _load_prompt('checks.md')
    reviewer = _load_prompt('reviewer.md')
    demo_guidelines = _load_prompt('demo_guidelines.md')

    return (
        f'{SYSTEM_PROMPT}\n\n'
        '---\n\n'
        '# Review Pipeline\n\n'
        'When the user asks to review a project (e.g. "review the project 5683"), '
        'perform all of the following stages in order within this single conversation. '
        'Present your final review as markdown.\n\n'
        '---\n\n'
        '## Stage 1: Pre-Check\n\n'
        f'{precheck}\n\n'
        '---\n\n'
        '## Stage 2: Checks\n\n'
        f'{checks}\n\n'
        '---\n\n'
        '## Stage 3: Final Review\n\n'
        f'{reviewer}\n\n'
        '---\n\n'
        '## Demo Guidelines Reference\n\n'
        f'{demo_guidelines}\n\n'
        '---\n\n'
        '## Output Instructions\n\n'
        'After performing all stages:\n\n'
        '1. Present the final review as a **single markdown message** with these sections:\n'
        '   - **Verdict**: APPROVE, REJECT, or FLAG_FOR_HUMAN\n'
        '   - **Project type**: The detected project type\n'
        '   - **Reasoning**: Detailed explanation referencing specific check results\n'
        '   - **Required fixes** (if rejecting): Exactly what must change for approval\n'
        '   - **Feedback**: Short helpful suggestions\n'
        '   - **Special flags**: Any applicable flags (UPDATED PROJECT, AI CONCERN, etc.)\n'
        '   - **Checks performed**: List of all checks evaluated with pass/fail/warn/skip status\n\n'
        '2. **ALWAYS** call `review_generate_pdf` as your FINAL action to generate the PDF report. '
        'Pass a single `review_json` argument — a JSON string with these keys:\n'
        '   `verdict`, `project_type`, `checks` (array of {name, status, details}), '
        '`reasoning`, `repo_url`, `demo_url`, `project_name`, `project_desc`, '
        '`project_url`, `required_fixes`, `feedback`, `special_flags`.\n'
        '   URLs should be without the https:// prefix.\n\n'
        'Do NOT skip the PDF generation step. It is a required part of every review.\n'
        '⚠️ CRITICAL: You MUST call `review_generate_pdf` before writing your final message. '
        'The review is INCOMPLETE without the PDF. Never skip it.\n'
    )


def _collect_review_tools() -> list[Tool]:
    return [
        Tool(getattr(review_tools, name))
        for name in sorted(dir(review_tools))
        if name.startswith('review_') and callable(getattr(review_tools, name))
    ]


def _collect_shipwrights_tools() -> list[Tool]:
    return [
        Tool(getattr(shipwrights_tools, name))
        for name in sorted(dir(shipwrights_tools))
        if name.startswith('shipwrights_') and callable(getattr(shipwrights_tools, name))
    ]


def create_agent(config: AppConfig) -> Agent:
    """Create the single review agent with all tools and the full system prompt."""
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=_build_system_prompt(),
        instrument=True,
        model_settings=OpenRouterModelSettings(
            timeout=120,
            openrouter_reasoning={'effort': 'medium'},
        ),
        tools=_collect_review_tools() + _collect_shipwrights_tools(),
    )
