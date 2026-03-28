from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from sw_reviewer import browser_tools, shipwrights_tools
from sw_reviewer.config import AppConfig
from sw_reviewer.prompts import SYSTEM_PROMPT


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


def create_agent(config: AppConfig) -> Agent:
    """Create the legacy single-agent (used by Slack/web interfaces)."""
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=SYSTEM_PROMPT,
        instrument=True,
        tools=_collect_browser_tools() + _collect_shipwrights_tools(),
    )
