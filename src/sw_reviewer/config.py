"""Application configuration loaded from environment variables."""

from typing import Optional
from pydantic import Field

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore[assignment]


class Settings(BaseSettings):
    # Database
    db_path: str = Field(default="reviewer_state.db", description="SQLite database path")

    # Artifacts
    artifacts_dir: str = Field(default="artifacts", description="Base directory for review artifacts")

    # Slack
    slack_bot_token: Optional[str] = Field(default=None, description="Slack bot OAuth token")
    slack_signing_secret: Optional[str] = Field(default=None, description="Slack signing secret")

    # AI model
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    model_name: str = Field(default="gemini-2.0-flash", description="AI model to use")

    # CLI sandbox
    docker_enabled: bool = Field(default=True, description="Whether Docker is available for CLI sandboxing")
    docker_image: str = Field(default="python:3.12-slim", description="Default Docker image for CLI sandbox")
    sandbox_timeout_seconds: int = Field(default=120, description="CLI sandbox job timeout")

    # Web execution
    playwright_headless: bool = Field(default=True, description="Run Playwright in headless mode")
    web_timeout_ms: int = Field(default=30000, description="Playwright default timeout in ms")

    # Typst
    typst_binary: str = Field(default="typst", description="Path to Typst binary")
    typst_enabled: bool = Field(default=True, description="Whether to attempt Typst PDF compilation")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Global singleton
settings = Settings()
