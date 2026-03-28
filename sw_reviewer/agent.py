from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from sw_reviewer import browser_tools
from sw_reviewer.config import AppConfig
from sw_reviewer.prompts import SYSTEM_PROMPT


def _collect_browser_tools() -> list[Tool]:
    return [
        Tool(getattr(browser_tools, name), sequential=True)
        for name in sorted(dir(browser_tools))
        if name.startswith('browser_') and callable(getattr(browser_tools, name))
    ]


def create_agent(config: AppConfig) -> Agent:
    return Agent(
        f'openrouter:{config.model_name}',
        instructions=SYSTEM_PROMPT,
        instrument=True,
        tools=_collect_browser_tools(),
    )
