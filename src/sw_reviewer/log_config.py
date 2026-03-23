"""Structured logging configuration with trace ID support."""

import logging
import json
import sys
from contextvars import ContextVar
from typing import Optional
from datetime import datetime, timezone

# Context variable for the current review_id
current_review_id: ContextVar[Optional[str]] = ContextVar("review_id", default=None)


class StructuredFormatter(logging.Formatter):
    """Formats log records as JSON with review_id context."""

    def format(self, record: logging.LogRecord) -> str:
        review_id = current_review_id.get(None)
        log_obj = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if review_id:
            log_obj["review_id"] = review_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with structured JSON output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


def set_review_context(review_id: str) -> None:
    """Set the review_id context var for the current async task."""
    current_review_id.set(review_id)


def clear_review_context() -> None:
    """Clear the review_id context."""
    current_review_id.set(None)
