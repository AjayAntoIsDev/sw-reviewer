from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import logfire
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.tools import Tool

import browser_tools

ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / '.env'
DEFAULT_MODEL_NAME = 'xiaomi/mimo-v2-pro'
SYSTEM_PROMPT = """\
You are a software reviewer AI assistant with full browser access.
You can navigate, read, interact with, and debug web applications.

Core browser workflow:
1. browser_navigate(url) — open a page
2. browser_snapshot() — get interactive elements with [N] index refs
3. browser_click(N) / browser_fill(N, text) — interact by element index
4. Always re-snapshot after navigation or DOM changes

Element indices:
- Elements in the snapshot are shown as [N] where N is a number
- Use this number as the 'index' parameter for click, fill, hover, etc.
- Indices become stale after DOM changes — always re-snapshot first

You also have access to:
- Navigation: back, forward, reload
- Reading: get_text, get_html, get_attribute, get_url, get_title
- Interaction: fill, hover, focus, select dropdowns, check, drag
- Keyboard: press keys (Enter, Tab, Escape, Control+a), type text
- Scrolling: scroll up/down/left/right
- Visual: screenshots (base64 or file)
- Tabs: open, close, list, switch between tabs
- JavaScript: run arbitrary JS via browser_eval (use arrow function format)
- Waiting: browser_wait(seconds)

Finding elements — two approaches:
1. By snapshot index (preferred): browser_snapshot() then browser_click(42)
2. By CSS selector: browser_get_text('h1'), browser_get_html('.content')

Keyboard tools (no element index needed — acts on focused element):
- browser_press('Enter') — single key or combo like 'Control+a'
- browser_type('text') — character-by-character typing

Resilience tips:
- If a click doesn't work, try browser_scroll('down') to reveal the element
- Use browser_wait(2) if the page is still loading
- Use browser_eval() for complex JS interactions
- If the browser is hung, use browser_recover()
- Always re-snapshot after ANY interaction

Use these tools freely and creatively to accomplish any browsing task.
"""


@dataclass(slots=True)
class AppConfig:
    model_name: str
    openrouter_api_key: str
    logfire_token: str | None
    logfire_service_name: str


load_dotenv(ENV_FILE)


def load_config() -> AppConfig:
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise RuntimeError('Missing OPENROUTER_API_KEY in .env')

    return AppConfig(
        model_name=os.getenv('MODEL_NAME', DEFAULT_MODEL_NAME),
        openrouter_api_key=api_key,
        logfire_token=os.getenv('LOGFIRE_TOKEN'),
        logfire_service_name=os.getenv('LOGFIRE_SERVICE_NAME', 'pydanticai-openrouter-agent'),
    )


CONFIG = load_config()

logfire.configure(
    service_name=CONFIG.logfire_service_name,
    send_to_logfire='if-token-present',
    token=CONFIG.logfire_token,
)
logfire.instrument_openai()

_browser_tools = [
    Tool(getattr(browser_tools, name), sequential=True)
    for name in sorted(dir(browser_tools))
    if name.startswith('browser_') and callable(getattr(browser_tools, name))
]

agent = Agent(
    f'openrouter:{CONFIG.model_name}',
    instructions=SYSTEM_PROMPT,
    instrument=True,
    tools=_browser_tools,
)

app = agent.to_web()
