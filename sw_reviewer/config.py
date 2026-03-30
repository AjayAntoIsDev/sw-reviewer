from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import logfire
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / '.env'

DEFAULT_MODEL_NAME = 'xiaomi/mimo-v2-pro'


@dataclass(slots=True)
class AppConfig:
    model_name: str
    openrouter_api_key: str
    logfire_token: str | None
    logfire_service_name: str
    github_token: str | None
    slack_bot_token: str | None
    slack_app_token: str | None


def load_config() -> AppConfig:
    load_dotenv(ENV_FILE)

    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise RuntimeError('Missing OPENROUTER_API_KEY in .env')

    return AppConfig(
        model_name=os.getenv('MODEL_NAME', DEFAULT_MODEL_NAME),
        openrouter_api_key=api_key,
        github_token=os.getenv('GITHUB_TOKEN'),
        logfire_token=os.getenv('LOGFIRE_TOKEN'),
        logfire_service_name=os.getenv('LOGFIRE_SERVICE_NAME', 'pydanticai-openrouter-agent'),
        slack_bot_token=os.getenv('SLACK_BOT_TOKEN'),
        slack_app_token=os.getenv('SLACK_APP_TOKEN'),
    )


def configure_observability(config: AppConfig) -> None:
    logfire.configure(
        service_name=config.logfire_service_name,
        send_to_logfire='if-token-present',
        token=config.logfire_token,
    )
    logfire.instrument_openai()
