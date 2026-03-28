"""Web interface — thin wrapper around agent.to_web()."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent


def create_web_app(agent: Agent) -> Any:
    return agent.to_web()
