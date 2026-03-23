# Changes T17: Structured Logging

- Created `src/sw_reviewer/log_config.py`: `StructuredFormatter`, `setup_logging()`, `get_logger()`, `set_review_context()`, `clear_review_context()`, `current_review_id` ContextVar.
- Wired into `src/sw_reviewer/app.py` via `setup_logging()` at startup.
- Wired into `src/sw_reviewer/orchestrator/service.py` via `set_review_context()`.
- Updated `AI/MASTER_TODO.md` T17 to DONE.
