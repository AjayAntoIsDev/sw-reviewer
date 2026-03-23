# AI Planning Workspace

This folder contains planning, coordination, and execution artifacts for the Shipwright AI Reviewer project.

## What lives here

- `MASTER_PLAN.md` — end-to-end implementation plan and architecture
- `MASTER_TODO.md` — single source of truth for task tracking across agents
- `GUIDELINES_NORMALIZED.md` — normalized Shipwright policy for automated checks
- `AGENT_WORKFLOW.md` — how each implementation agent gets context and reports work
- `templates/` — reusable templates for task packets and Typst review reports
- `context/packets/` — task context packets assigned to agents
- `tasks/` — per-task completion folders with `summary.md`, `changes.md`, and `next.md`

## Operating rule

All planning and AI coordination updates must happen inside this `AI/` folder.

## Completion rule for all agents

When an agent finishes a task, it must:

1. Create a task folder under `tasks/` named:
   - `<task-id>_<slug>/` (example: `T08_web-visible-readme-flows/`)
2. Add:
   - `summary.md` (what was done)
   - `changes.md` (files changed)
   - `next.md` (risks + next steps)
3. Update `MASTER_TODO.md` by checking the task (`[x]`) and setting status to `DONE`.

## Review output format

Automated reviews must produce:

- a Typst source report (`.typ`)
- a rendered PDF (`.pdf`)
- a machine-readable verdict bundle (`.json`)
