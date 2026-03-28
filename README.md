# SW Reviewer

A software reviewer AI assistant with full browser access, powered by [Pydantic AI](https://ai.pydantic.dev/).
Supports two interfaces: **Web UI** and **Slack**.

## Project structure

```
sw_reviewer/
  config.py           # Config loading, logfire setup
  prompts.py           # System prompt
  agent.py             # Agent creation + browser tool registration
  browser_tools.py     # Browser automation tools (browser-use)
  history.py           # Per-thread conversation history store
  interfaces/
    web.py             # Web UI (agent.to_web())
    slack/
      app.py           # Slack Bolt app + Assistant handlers
      stream.py        # Pydantic-AI → Slack streaming bridge
      files.py         # Slack file downloads → BinaryContent
run_web.py             # Entry point: web interface
run_slack.py           # Entry point: Slack interface
```

## Environment variables

Put these in `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | ✅ | — | OpenRouter API key |
| `MODEL_NAME` | — | `xiaomi/mimo-v2-pro` | Model to use via OpenRouter |
| `LOGFIRE_TOKEN` | — | — | Logfire write token (optional) |
| `LOGFIRE_SERVICE_NAME` | — | `pydanticai-openrouter-agent` | Service name in Logfire |
| `SLACK_BOT_TOKEN` | For Slack | — | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | For Slack | — | Slack app-level token (`xapp-...`) |
| `BROWSER_HEADLESS` | — | `0` | Set to `1` for headless browser |

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run — Web UI

```bash
python run_web.py
```

## Run — Slack Bot

### Slack app setup

1. Create a Slack app at https://api.slack.com/apps (or use Slack CLI)
2. Enable **Socket Mode** and generate an app-level token with `connections:write` scope
3. Enable **Agents & AI Apps** in app features
4. Add bot scopes: `assistant:write`, `chat:write`, `im:history`, `files:read`, `app_mentions:read`
5. Subscribe to bot events: `assistant_thread_started`, `assistant_thread_context_changed`, `message.im`, `app_mention`
6. Install the app to your workspace

### Run

```bash
python run_slack.py
```

### Slack features

- **Streaming responses** — text streams progressively into the thread
- **Tool call visibility** — browser tool calls appear as task updates in the stream
- **Image support** — send images in the thread and the agent can see them
- **Conversation history** — each thread maintains its own conversation context
- **Suggested prompts** — first interaction offers example prompts
- **@mention support** — mention the bot in any channel to start a conversation in-thread
- **Agent status** — shows "Thinking..." while the agent works

## Notes

- Web and Slack are separate processes — run them independently
- All Slack threads share a single browser session (for now)
- The agent uses OpenRouter via `openrouter:<model>`
