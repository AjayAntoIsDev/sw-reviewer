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
| T01 | [ ] | TODO | Define final policy schema (`required/advisory/manual_only`) | T00A | executable policy schema spec | policy-agent |
| T02 | [ ] | TODO | Define typed data contracts for all review stages | T01 | Pydantic models (`ReviewRequest`, `PolicyCheckResult`, `WebFlowResult`, `CLICommandResult`, `EvidenceBundle`, `FinalVerdict`) | core-agent |
| T03 | [ ] | TODO | Build PydanticAI orchestrator skeleton and stage router | T02 | orchestrator service with stage pipeline hooks | orchestration-agent |
| T04 | [ ] | TODO | Build job state model + persistence | T02 | DB schema, status transitions, repository layer | backend-agent |
| T05 | [ ] | TODO | Implement Slack intake (`/review start`, `/review status`, `/review cancel`, `/review verdict`) | T04 | Slack handler and validated request creation | slack-agent |
| T06 | [ ] | TODO | Implement Slack threaded progress and final verdict card | T05,T12,T16 | progress updates + final card with artifact links | slack-agent |
| T07 | [ ] | TODO | Implement `agent-browser` adapter for deterministic web execution | T03 | reusable web execution client | web-agent |
| T08 | [ ] | TODO | Implement web validator for visible UI flows and README-documented flows | T07,T01 | flow runner + pass/fail evidence mapping | web-agent |
| T09 | [ ] | TODO | Implement mandatory screenshot capture for every validated web flow | T08 | screenshot artifact pack and index | web-agent |
| T10 | [ ] | TODO | Implement auth checks (OAuth if present + conventional sign-in/up) | T08 | auth flow test module with result status | web-agent |
| T11 | [ ] | TODO | Implement CLI sandbox runner (Docker/Podman, non-privileged) | T03 | ephemeral isolated runner with resource limits | cli-agent |
| T12 | [ ] | TODO | Implement README command extraction + deterministic command phases | T11 | command plan builder and phase executor | cli-agent |
| T13 | [ ] | TODO | Implement CLI evidence capture and result normalization | T12 | stdout/stderr/exit/timing evidence bundle | cli-agent |
| T14 | [ ] | TODO | Implement policy check engine and rule evaluation | T01,T02,T09,T13 | normalized checklist evaluation output | policy-agent |
| T15 | [ ] | TODO | Implement verdict engine (`approve/reject/needs-human-review`) | T14 | deterministic verdict module with confidence handling | policy-agent |
| T16 | [ ] | TODO | Implement Typst report generation pipeline (`.typ` + `.pdf`) | T09,T13,T15 | complete report renderer and storage integration | report-agent |
| T17 | [ ] | TODO | Add structured logging, trace IDs, and failure taxonomy | T04,T08,T12 | observability baseline with per-`review_id` traceability | infra-agent |
| T18 | [ ] | TODO | Build regression/eval dataset and baseline metrics | T15 | benchmark set + eval report | eval-agent |
| T19 | [ ] | TODO | Security hardening (RBAC, redaction, sandbox guardrails) | T05,T11,T17 | security controls and review checklist | security-agent |

