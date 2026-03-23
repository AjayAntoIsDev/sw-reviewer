# Master Plan — Shipwright AI Reviewer (Web + CLI First)

## 0) Objective

Build an AI-assisted review system that automates Shipwright project checks for:

1. Web apps/websites
2. CLI tools

Human reviewers remain in control for ambiguous or high-risk cases.
Slack is the operator surface for submission intake, run control, and result delivery.

---

## 1) Product outcomes (Phase 1)

- Input: reviewer manually provides project data in Slack.
- System executes automated review pipeline.
- Output: structured verdict with evidence and policy checklist, plus a generated Typst review report.
- Categories supported now: web apps + CLI tools.
- Strong isolation/sandboxing for untrusted code execution.

---

## 2) Architecture (high-level)

### A. Slack Control Plane

- Slack app with slash commands + message actions:
  - `/review start`
  - `/review status`
  - `/review cancel`
  - `/review verdict`
- Slack event handler stores review jobs in queue.
- Threads become canonical timeline for each review.

### B. Orchestrator (PydanticAI)

- `ReviewOrchestratorAgent` routes each job by type.
- Specialized agents:
  - `PolicyAgent` (rules/checklist evaluation)
  - `WebTestAgent` (browser-driven validation)
  - `CLITestAgent` (sandboxed CLI validation)
  - `EvidenceAgent` (collect/normalize artifacts)
  - `VerdictAgent` (final decision payload)
- Use typed outputs (`Pydantic` models) for every stage.

### C. Execution Backends

- Web: `agent-browser` for deterministic browser actions + screenshot evidence of working visible and README-documented flows.
- CLI: isolated sandbox runner for build/install/command tests.

### D. Storage & Evidence

- Job DB (Postgres/SQLite for start) with status transitions.
- Artifact store (local + object storage later) for logs/screenshots/report JSON and Typst/PDF review artifacts.
- All review decisions are reproducible from stored evidence.

### E. Observability

- Structured JSON logs by `review_id`.
- Agent traces + retries + step timings.
- Failure taxonomy (policy ambiguity vs infra failure vs project failure).

---

## 3) Decision model and policy framework

Represent policy as executable checks:

- `required`: fail blocks approval
- `advisory`: include warning but not immediate reject
- `manual_only`: requires human confirmation

Every check returns:

- `status`: pass/fail/warn/unknown
- `evidence`
- `reason`
- `confidence`

Final verdict rule (Phase 1 default):

- `approve` if all required checks pass and no critical unknowns
- `reject` if any required check fails
- `needs-human-review` if required checks remain unknown/ambiguous

---

## 4) Web review design

### Capabilities

- Validate repo visibility and README basics.
- Validate demo URL host policy.
- Launch browser and test visible core flows.
- Test everything visible in the UI and everything explicitly documented in the README.
- Record screenshot evidence for each validated flow and feature.
- For auth projects: validate at least one OAuth (if present) and normal sign-up/sign-in.

### `agent-browser` usage principles

- Ref/snapshot workflow for reliable interaction.
- Save screenshots for every successful visible flow and README-documented flow.

### Exit criteria

- All required flows complete or fail with clear evidence.

---

## 5) CLI review design (sandbox/isolation)

### Core approach (recommended)

Use an **ephemeral, locked-down container runner** per job:

- Container runtime (Docker or Podman). Rootless is preferred, but not required for MVP.
- Read-only base image + writable temp workspace
- CPU/memory/time limits
- No privileged mode
- Restricted network policy:
  - allow package registries and declared endpoints only
  - block metadata/internal ranges
- No host mounts except dedicated temp workspace
- Drop Linux capabilities + seccomp/AppArmor profile

### Command execution strategy

- Parse documented install/use commands from README (plus operator-provided commands if needed).
- Execute in deterministic phases:
  1. Environment bootstrap
  2. Install/build
  3. Smoke command tests (`--help`, version, primary commands)
  4. Feature commands from docs
- Capture stdout/stderr/exit code/timings per command.

### Safety and reliability

- Hard timeout per command and per job.
- Max output limits + truncation markers.
- Redact known secret patterns.
- Kill switch on suspicious behavior (fork bomb-like behavior, long idle loops, large unexpected egress).

### Future hardening path

- Move from container-only to microVM runner for high-risk submissions.

---

## 6) Slack integration design

### Intake

Manual data from shipwrights via Slack payload:

- project type (`web`/`cli`)
- repo URL
- demo URL (web) / binary + usage docs (cli)
- optional auth test instructions
- optional command hints

### Responses in thread

- Acknowledgement + `review_id`
- Progress updates by stage
- Final verdict card:
  - verdict
  - required/advisory checklist
  - key failures
  - artifact links
  - Typst/PDF report link
  - suggested feedback text

### Controls

- retry failed stage
- cancel run
- force escalate to human

---

## 7) Data contracts (typed)

Define strict Pydantic models for:

- `ReviewRequest`
- `PolicyCheckResult`
- `WebFlowResult`
- `CLICommandResult`
- `EvidenceBundle`
- `FinalVerdict`

Typed contracts prevent drift across multiple agents and make multi-agent orchestration safer.

---

## 8) Review output document (Typst)

Every review run must generate a Typst document that includes:

- Review metadata (project, repo, reviewer, run id, timestamps)
- Final verdict (`approve` / `reject` / `needs-human-review`)
- Rule-by-rule checklist with pass/fail/unknown
- Evidence index grouped by feature/flow
- Screenshot gallery proving visible UI and README-documented functionality
- CLI command result table (command, exit code, duration, result)
- Rejection reasons or risk notes
- Suggested feedback text for the submitter

Primary output artifacts:

1. `.typ` source report
2. rendered `.pdf`
3. machine-readable `.json` verdict bundle

---

## 9) Testing and quality gates

### A. Unit tests

- policy parser/check evaluator
- verdict decision engine
- Slack payload validation

### B. Integration tests

- web review against known good/bad demo projects
- CLI review against controlled fixture repos

### C. Evals

- Maintain benchmark dataset of prior submissions + expected verdict.
- Track precision/recall for approve/reject/human-review routing.

### D. Non-functional

- timeout reliability
- sandbox escape resistance checks
- observability completeness

---

## 10) Security model

- Never trust repository code or links.
- Sandbox all execution.
- Keep secrets out of agent context.
- Artifact and log redaction by default.
- Role-based Slack command access.
- Full audit trail of decisions and tool actions.

---

## 11) Delivery phases

### Phase 0 — Planning + policy normalization

- finalize checks and verdict criteria
- freeze typed contracts

### Phase 1 — MVP (web + CLI + Slack)

- single queue, single worker process
- web automation, CLI sandbox runner, evidence pack
- basic verdict + thread reporting

### Phase 2 — Reliability and scale

- parallel workers
- retries by stage
- richer analytics and dashboards

### Phase 3 — Scope expansion

- additional project types (extensions, libs, bots, mobile, games)
- stronger autonomous triage

---

## 12) Risks and mitigations

- **Policy ambiguity** → encode `manual_only` checks + human escalation path.
- **Flaky web tests** → deterministic wait strategy + retry budget + evidence snapshots.
- **Unsafe CLI execution** → strict isolation, resource caps, network controls.
- **False rejects** → confidence scoring + `needs-human-review` route.
- **Slack UX overload** → concise status schema + thread-only updates.

---

## 13) Definition of done for MVP

- Reviewer can trigger review from Slack with manual payload.
- Web and CLI reviews run end-to-end.
- Final verdict and checklist returned in Slack.
- Typst/PDF report is attached or linked in Slack output.
- Artifacts are persisted and linked.
- Master todo workflow supports multi-agent execution and completion tracking.
