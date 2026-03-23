# Agent Workflow and Context Protocol

This protocol ensures multiple agents can collaborate safely and asynchronously.

## 1) Context handoff to an agent

For each task, create a packet in `context/packets/` using template:

- `TASK-<id>-context.md`

Required sections:

- Goal
- Scope boundaries (what is in/out)
- Inputs (links, repos, Slack payload shape, prior decisions)
- Constraints (security, timeouts, budget)
- Deliverables
- Acceptance criteria
- Dependencies

## 2) During execution

Agent must:

- Keep all planning/notes under `AI/`.
- Write interim decisions to its task folder.
- Avoid changing out-of-scope tasks.

## 3) Completion output

Agent creates:

`tasks/<task-id>_<slug>/`

with:

- `summary.md`
- `changes.md`
- `next.md`

## 4) Master todo update (mandatory)

On completion, agent updates `MASTER_TODO.md`:

- Set checklist to `[x]`
- Move task to `DONE`
- Add task folder path in task notes (if notes column exists)
- Note blockers or follow-up tasks in `next.md`

## 5) Escalation rule

If confidence is low, policy is ambiguous, or security risk is high:

- Mark task as `Blocked`
- Add escalation note
- Assign to human review queue
