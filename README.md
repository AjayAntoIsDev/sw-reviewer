# Shipwright AI Reviewer

An AI-assisted automated review system for Shipwright projects. It ingests review requests via Slack slash commands or a REST API, executes web and CLI automation to gather evidence, evaluates policy rules, and delivers a structured verdict with a PDF report.

---

## Architecture Overview

```
Slack Slash Command
        │
        ▼
  FastAPI Endpoint  ◄──── REST API calls
        │
        ▼
   Orchestrator  (PydanticAI)
   ├── Fetch & parse repository metadata (README, project type, demo URL)
   ├── Web Execution  (Playwright — headless browser automation)
   ├── CLI Execution  (Docker sandbox — sandboxed command runner)
   ├── Policy Evaluator  (rule-based checks + AI-assisted reasoning)
   ├── Verdict Generator  (APPROVE / REJECT / NEEDS_HUMAN_REVIEW)
   └── Report Builder  (Typst → PDF artifact)
        │
        ▼
  Slack Threaded Reporter  (posts progress + final verdict to thread)
```

---

## Supported Project Types

| Type | What is reviewed |
|------|-----------------|
| **web** | Live demo URL verified via Playwright; screenshots, console errors, and HTTP status captured |
| **cli** | Commands executed inside a Docker sandbox; exit codes, stdout/stderr captured |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.12+ | Tested on CPython 3.12 and 3.13 |
| Docker | Required for CLI sandbox execution (`docker_enabled=true`) |
| Typst | Optional — needed for PDF report generation; install from [typst.app](https://typst.app) |
| A Google Gemini API key | Used by the PydanticAI orchestrator |
| A Slack app | Required for Slack intake; needs `commands` and `chat:write` scopes |

---

## Setup & Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/sw-reviewer.git
cd sw-reviewer

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install the package with dev dependencies
pip install -e ".[dev]"

# 4. Copy the example env file and fill in your secrets
cp .env.example .env
$EDITOR .env
```

---

## Environment Variables

Create a `.env` file in the project root (or export these variables directly):

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `reviewer_state.db` | SQLite database path for job state |
| `ARTIFACTS_DIR` | `artifacts` | Base directory where review artifacts are stored |
| `SLACK_BOT_TOKEN` | _(none)_ | Slack bot OAuth token (`xoxb-…`) |
| `SLACK_SIGNING_SECRET` | _(none)_ | Slack signing secret for request verification |
| `GEMINI_API_KEY` | _(none)_ | Google Gemini API key |
| `MODEL_NAME` | `gemini-2.0-flash` | AI model identifier passed to PydanticAI |
| `DOCKER_ENABLED` | `true` | Set to `false` to disable Docker-based CLI sandbox |
| `DOCKER_IMAGE` | `python:3.12-slim` | Default Docker image used for CLI sandboxing |
| `SANDBOX_TIMEOUT_SECONDS` | `120` | Maximum seconds allowed for a CLI sandbox job |
| `PLAYWRIGHT_HEADLESS` | `true` | Run Playwright in headless mode |
| `WEB_TIMEOUT_MS` | `30000` | Playwright default timeout in milliseconds |
| `TYPST_BINARY` | `typst` | Path to the Typst binary |
| `TYPST_ENABLED` | `true` | Set to `false` to skip PDF report generation |

---

## Slack Slash Commands

Configure a Slack app with a slash command pointing to `POST /slack/commands`.

| Command | Description |
|---------|-------------|
| `/review start <repo_url>` | Submit a new review for `<repo_url>` |
| `/review status <job_id>` | Check the current status of a running review |
| `/review cancel <job_id>` | Cancel a running review |
| `/review verdict <job_id>` | Retrieve the final verdict for a completed review |

---

## Running the Server

```bash
uvicorn sw_reviewer.app:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Running Tests

```bash
pytest
```

To run a specific test file with verbose output:

```bash
pytest tests/test_policy_engine.py -v
```

---

## Project Structure

```
src/sw_reviewer/
├── __init__.py          # Package version export
├── app.py               # FastAPI application (entry point)
├── config.py            # Settings loaded from environment
├── log_config.py        # Structured JSON logging with trace IDs
├── models.py            # Pydantic data contracts for all review stages
├── orchestrator.py      # PydanticAI orchestrator (stage tools)
├── slack.py             # Slack intake handler and threaded reporter
├── state.py             # Job state model + SQLite persistence
└── policy/
    ├── __init__.py
    ├── schema.py        # Policy rule definitions
    ├── rules.py         # Heuristic rule evaluation functions
    └── evaluator.py     # Policy evaluation engine + verdict generator
tests/
├── test_models.py       # Data contract model tests
└── test_policy_engine.py # Policy rule and evaluator tests
```

---

## License

MIT
