"""Entry point for the Slack interface."""

import asyncio
import logging

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from sw_reviewer.config import configure_observability, load_config
from sw_reviewer.agent import create_agent
from sw_reviewer.interfaces.slack.app import create_slack_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    configure_observability(config)

    if not config.slack_app_token:
        raise RuntimeError('Missing SLACK_APP_TOKEN in .env — required for Socket Mode')

    agent = create_agent(config)
    slack_app = create_slack_app(config, agent)

    handler = AsyncSocketModeHandler(slack_app, config.slack_app_token)
    logger.info('⚡ Slack bot is running (Socket Mode)')
    await handler.start_async()


if __name__ == '__main__':
    asyncio.run(main())
