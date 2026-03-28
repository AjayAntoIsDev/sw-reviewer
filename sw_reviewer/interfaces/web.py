"""Web interface — wraps agent.to_web() for the Starlette chat UI."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent


def create_web_app(agent: Agent) -> Any:
    return agent.to_web()
