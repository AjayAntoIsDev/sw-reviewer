# Master Todo List (Multi-Agent)

Status legend: `TODO` | `IN_PROGRESS` | `BLOCKED` | `DONE`

## Task completion rule

When a task is completed, the agent must:

1. Set checklist to `[x]` and status to `DONE` in the table below.
2. Create a task folder at `AI/tasks/<task-id>_<slug>/` (example: `AI/tasks/T03_policy-schema/`).
3. Add exactly these files:
	- `summary.md`
	- `changes.md`
	- `next.md`

## Master checklist table

| ID | Check | Status | Task | Depends on | Deliverable | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| T00 | [x] | DONE | Legacy audit, roadmap, and AI workflow setup | - | planning docs and initial context | planning-agent |
| T00A | [x] | DONE | Polish plan (visible+README validation, screenshot-first evidence, Typst output) | T00 | updated plan and output/report requirements | planning-agent |
| T01 | [x] | DONE | Define final policy schema (`required/advisory/manual_only`) | T00A | executable policy schema spec | policy-agent |
| T02 | [x] | DONE | Define typed data contracts for all review stages | T01 | Pydantic models (`ReviewRequest`, `PolicyCheckResult`, `WebFlowResult`, `CLICommandResult`, `EvidenceBundle`, `FinalVerdict`) | core-agent |
| T03 | [x] | DONE | Build PydanticAI orchestrator skeleton and stage router | T02 | orchestrator service with stage pipeline hooks | orchestration-agent |
| T04 | [x] | DONE | Build job state model + persistence | T02 | DB schema, status transitions, repository layer | backend-agent |
| T05 | [x] | DONE | Implement Slack intake (`/review start`, `/review status`, `/review cancel`, `/review verdict`) | T04 | Slack handler and validated request creation | slack-agent |
| T06 | [x] | DONE | Implement Slack threaded progress and final verdict card | T05,T12,T16 | progress updates + final card with artifact links | slack-agent |
| T07 | [x] | DONE | Implement `agent-browser` adapter for deterministic web execution | T03 | reusable web execution client | execution-agent |
| T08 | [x] | DONE | Implement web validator for visible UI flows and README-documented flows | T07,T01 | flow runner + pass/fail evidence mapping | execution-agent |
| T09 | [x] | DONE | Implement mandatory screenshot capture for every validated web flow | T08 | screenshot artifact pack and index | execution-agent |
| T10 | [x] | DONE | Implement auth checks (OAuth if present + conventional sign-in/up) | T08 | auth flow test module with result status | execution-agent |
| T11 | [x] | DONE | Implement CLI sandbox runner (Docker/Podman, non-privileged) | T03 | ephemeral isolated runner with resource limits | execution-agent |
| T12 | [x] | DONE | Implement README command extraction + deterministic command phases | T11 | command plan builder and phase executor | execution-agent |
| T13 | [x] | DONE | Implement CLI evidence capture and result normalization | T12 | stdout/stderr/exit/timing evidence bundle | execution-agent |
| T14 | [x] | DONE | Implement policy check engine and rule evaluation | T01,T02,T09,T13 | normalized checklist evaluation output | foundation-agent |
| T15 | [x] | DONE | Implement verdict engine (`approve/reject/needs-human-review`) | T14 | deterministic verdict module with confidence handling | foundation-agent |
| T16 | [x] | DONE | Implement Typst report generation pipeline (`.typ` + `.pdf`) | T09,T13,T15 | complete report renderer and storage integration | execution-agent |
| T17 | [x] | DONE | Add structured logging, trace IDs, and failure taxonomy | T04,T08,T12 | observability baseline with per-`review_id` traceability | foundation-agent |
| T18 | [ ] | TODO | Build regression/eval dataset and baseline metrics | T15 | benchmark set + eval report | eval-agent |
| T19 | [x] | DONE | Security hardening (RBAC, redaction, sandbox guardrails) | T05,T11,T17 | security controls and review checklist | execution-agent |

