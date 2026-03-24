# PydanticAI Web UI

This project now uses [`agent.to_web()`](app.py:52) directly instead of Gradio or the CLI wrapper.

## What the app does

- loads [`.env`](.env) from the project root
- creates a reusable [`Agent`](app.py:46) using `openrouter:<model>`
- configures [`logfire.configure()`](app.py:40) once at import time
- exposes the built-in web UI via [`app = agent.to_web()`](app.py:52)
- serves the app with [`app.serve()`](app.py:56)

## Environment variables

Put these in [`.env`](.env):

- `OPENROUTER_API_KEY` — required
- `MODEL_NAME` — optional, defaults to `xiaomi/mimo-v2-pro`
- `LOGFIRE_TOKEN` — optional, only needed if you want traces sent to Logfire cloud
- `LOGFIRE_SERVICE_NAME` — optional, defaults to `pydanticai-openrouter-agent`

Example:

```env
OPENROUTER_API_KEY=your_openrouter_key
MODEL_NAME=xiaomi/mimo-v2-omni
LOGFIRE_TOKEN=your_logfire_write_token
LOGFIRE_SERVICE_NAME=sw-reviewer
```

## Install

```bash
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
./.venv/bin/python app.py
```

This starts the built-in PydanticAI web app from [`agent.to_web()`](app.py:52).

## How Logfire should be set up

### Without Logfire cloud

If `LOGFIRE_TOKEN` is not set in [`.env`](.env), [`logfire.configure()`](app.py:40) uses `send_to_logfire='if-token-present'`, so the app still runs normally without sending traces remotely.

### With Logfire cloud

1. Create a project in Logfire.
2. Copy the project write token.
3. Add `LOGFIRE_TOKEN` to [`.env`](.env).
4. Optionally add `LOGFIRE_SERVICE_NAME` to identify this app in Logfire.
5. Restart [`app.py`](app.py).

Because [`logfire.instrument_openai()`](app.py:45) is enabled and the [`Agent`](app.py:46) uses `instrument=True`, model activity from the web UI will be exported to Logfire when a token is present.

## Notes

- The app uses OpenRouter through `openrouter:<model>` in [`Agent(...)`](app.py:46)
- [`.gitignore`](.gitignore) already excludes [`.env`](.env)
- You can add tools later with decorators such as [`@agent.tool_plain`](app.py:46) if needed
