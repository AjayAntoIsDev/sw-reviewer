# T17 Summary: Structured Logging + Trace IDs

**Task**: T17 (structured logging, trace IDs, failure taxonomy)

Implemented structured JSON logging in `src/sw_reviewer/log_config.py`.
- `StructuredFormatter` outputs each log record as a JSON object with `timestamp`, `level`, `logger`, `message`, and optional `review_id` and `exception` fields.
- `current_review_id` `ContextVar` carries the review ID across async task boundaries without explicit parameter passing.
- `set_review_context(review_id)` / `clear_review_context()` manage the context variable.
- `setup_logging(level)` replaces the root logger's handlers with the structured formatter.
- `get_logger(name)` is a convenience wrapper.
- The orchestrator service calls `set_review_context` at pipeline entry.
