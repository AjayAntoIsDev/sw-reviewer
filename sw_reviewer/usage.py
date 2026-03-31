"""Token usage tracking and cost calculation for agent runs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import logfire

if TYPE_CHECKING:
    from pydantic_ai.usage import RunUsage

logger = logging.getLogger(__name__)

# Logfire agent pricing (USD per million tokens)
INPUT_COST_PER_M = 0.10
OUTPUT_COST_PER_M = 0.30


def _cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost from token counts."""
    return (input_tokens * INPUT_COST_PER_M + output_tokens * OUTPUT_COST_PER_M) / 1_000_000


def log_usage(usage: RunUsage, *, label: str = "agent_run") -> dict:
    """Log token usage and estimated cost, returning the metrics dict."""
    input_t = usage.input_tokens
    output_t = usage.output_tokens
    total_t = usage.total_tokens
    cost = _cost(input_t, output_t)

    metrics = {
        "input_tokens": input_t,
        "output_tokens": output_t,
        "total_tokens": total_t,
        "requests": usage.requests,
        "cost_usd": round(cost, 6),
    }

    logger.info(
        "[%s] tokens: %d in / %d out / %d total | requests: %d | cost: $%.6f",
        label,
        input_t,
        output_t,
        total_t,
        usage.requests,
        cost,
    )

    logfire.info(
        "{label} usage: {input_tokens} in / {output_tokens} out — ${cost_usd}",
        label=label,
        **metrics,
    )

    return metrics
