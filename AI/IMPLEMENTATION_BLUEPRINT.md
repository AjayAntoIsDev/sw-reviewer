# Implementation Blueprint — Shipwright AI Reviewer MVP

## Goal

Implement a working MVP from the planning-only workspace using Python, with:

- Slack command intake and status/verdict lookup
- Typed review request / evidence / verdict contracts
- Orchestrated review pipeline for `web` and `cli` project types
- Web execution adapter using Playwright-compatible browser automation hooks
- CLI execution runner using Docker when available
- Policy evaluation and deterministic verdict generation
- Artifact persistence (JSON, logs, Typst source, PDF when Typst is installed)
- Structured logging and a small automated test suite

## Technology Decisions

- Language: Python 3.12+
- Packaging: `pyproject.toml`
- HTTP service: FastAPI
- Validation/models: Pydantic v2
- Persistence: SQLite via stdlib `sqlite3`
- Templates/reporting: Typst template fill + optional `typst compile`
- Browser executor: Playwright adapter abstraction
- CLI sandbox: Docker command wrapper with resource limits
- Tests: `pytest`

## Repository Layout

```text
src/sw_reviewer/
  __init__.py
  config.py
  logging.py
  models/
    requests.py
    policy.py
    evidence.py
    verdict.py
    db.py
  policy/
    schema.py
    evaluator.py
    rules.py
  storage/
    jobs.py
    artifacts.py
    sqlite.py
  execution/
    web.py
    cli.py
    readme_parser.py
  reporting/
    typst.py
    bundle.py
  slack/
    commands.py
    formatting.py
  orchestrator/
    service.py
    stages.py
  app.py
tests/
```

## Functional Contract

### Review input

The system must support a normalized review request with at least:

- `review_id`
- `project_name`
- `project_type` (`web` or `cli`)
- `repo_url`
- `demo_url` for web projects
- `readme_text` optional override
- `auth_instructions` optional
- `command_hints` optional list
- `web_flows` optional list of named browser flow steps
- `cli_commands` optional list of documented commands
- Slack metadata (`channel_id`, `thread_ts`, `requested_by`)

### Core behavior

1. Validate request.
2. Persist job in SQLite.
3. Run stage pipeline:
   - request normalization
   - policy prechecks
   - project-type execution (`web` or `cli`)
   - evidence normalization
   - policy evaluation
   - verdict generation
   - report generation
4. Persist artifacts under `artifacts/<review_id>/`.
5. Return structured final verdict payload.

## Policy Baseline

Implement executable policy categories:

- `required`
- `advisory`
- `manual_only`

Minimum required checks for MVP:

- repository URL present
- project type supported
- README sufficiency heuristic from request/readme text
- open-source/public heuristic flag
- web: demo URL present and on allowed host list heuristic
- cli: commands or command hints present
- execution success for at least one meaningful flow/command

## Evidence Contract

Evidence bundle must support:

- checklist results
- web flow results with screenshots
- CLI command results with stdout/stderr/exit code/duration
- artifact paths
- structured risk notes
- summary text for Slack/report

## Workstream Ownership for Subagents

### Workstream A — foundation-agent

Own files:

- `pyproject.toml`
- `README.md`
- `src/sw_reviewer/config.py`
- `src/sw_reviewer/logging.py`
- `src/sw_reviewer/models/**`
- `src/sw_reviewer/policy/**`
- `tests/test_policy_engine.py`
- `tests/test_models.py`

### Workstream B — execution-agent

Own files:

- `src/sw_reviewer/execution/**`
- `src/sw_reviewer/orchestrator/**`
- `src/sw_reviewer/reporting/**`
- `tests/test_orchestrator.py`
- `tests/test_reporting.py`

### Workstream C — interface-agent

Own files:

- `src/sw_reviewer/storage/**`
- `src/sw_reviewer/slack/**`
- `src/sw_reviewer/app.py`
- `tests/test_storage.py`
- `tests/test_slack_commands.py`

## Cross-Workstream Rules

- Import shared types only from `src/sw_reviewer/models/`.
- Do not duplicate domain models in feature modules.
- Keep external integrations swappable behind simple classes/functions.
- Use only stable, deterministic return shapes.
- Write docstrings for public entry points.
- Add task completion artifacts in `AI/tasks/` for the workstream completed.

## Integration Expectations

After subagent runs, the main agent will:

- reconcile imports and package exports
- run tests / static checks available in environment
- fill any missing glue code
- update `AI/MASTER_TODO.md`
- add a top-level completion task record under `AI/tasks/`

## Same Model / Provider Requirement

All spawned subagents must run in `code` mode under the same provider/model context as the parent task.
