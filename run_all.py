"""Start all services (web, watcher, slack) concurrently."""

import asyncio
import logging
import os

import uvicorn
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient

from sw_reviewer.config import configure_observability, load_config
from sw_reviewer.agent import create_agent
from sw_reviewer.interfaces.slack.app import create_slack_app
from sw_reviewer.interfaces.web import create_web_app
from run_watcher import (
    DEFAULT_CHANNEL,
    POLL_INTERVAL,
    SHIP_LIMIT,
    fetch_latest_ships,
    run_review_for_ship,
    utc_now,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _run_web(agent, host: str, port: int) -> None:
    config = uvicorn.Config(create_web_app(agent), host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    logger.info("🌐 Web UI starting on http://%s:%d", host, port)
    await server.serve()


async def _run_watcher(agent, slack: AsyncWebClient, channel: str, base_url: str) -> None:
    # Announce online
    try:
        await slack.chat_postMessage(
            channel=channel,
            text=f":shipitparrot: Watching for new ships! Polling every {int(POLL_INTERVAL)}s",
        )
    except Exception:
        logger.exception("Failed to send watcher online announcement")

    seen_ids: set[int] = set()
    first_poll = True
    logger.info("[%s] Watcher polling %s → %s (interval=%ss)", utc_now(), base_url, channel, POLL_INTERVAL)

    while True:
        try:
            ships = fetch_latest_ships(base_url, "pending", SHIP_LIMIT)
            current_ids = set()
            new_ships = []
            for ship in ships:
                ship_id_raw = ship.get("id")
                if ship_id_raw is None:
                    continue
                ship_id = int(ship_id_raw)
                current_ids.add(ship_id)
                if ship_id not in seen_ids and not first_poll:
                    new_ships.append(ship)

            if first_poll:
                seen_ids = current_ids
                first_poll = False
                logger.info("[%s] Initial poll: %d existing ships tracked", utc_now(), len(seen_ids))
            else:
                seen_ids |= current_ids
                for ship in new_ships:
                    logger.info("[%s] NEW_SHIP id=%s", utc_now(), ship.get("id"))
                    await run_review_for_ship(agent, ship, slack, channel)
        except Exception:
            logger.exception("[%s] Poll error", utc_now())

        await asyncio.sleep(POLL_INTERVAL)


async def _run_slack(config, agent) -> None:
    if not config.slack_app_token:
        logger.warning("⚠️  SLACK_APP_TOKEN not set — skipping Slack bot")
        return

    slack_app = create_slack_app(config, agent)
    handler = AsyncSocketModeHandler(slack_app, config.slack_app_token)
    logger.info("⚡ Slack bot starting (Socket Mode)")
    await handler.start_async()


async def main() -> None:
    config = load_config()
    configure_observability(config)
    agent = create_agent(config)

    if not config.slack_bot_token:
        raise RuntimeError("Missing SLACK_BOT_TOKEN in .env")

    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "7932"))
    base_url = os.getenv("SW_DASH_BASE_URL", "https://review.hackclub.com")
    channel = os.getenv("WATCHER_CHANNEL", DEFAULT_CHANNEL)
    slack = AsyncWebClient(token=config.slack_bot_token)

    tasks = [
        asyncio.create_task(_run_web(agent, host, port), name="web"),
        asyncio.create_task(_run_watcher(agent, slack, channel, base_url), name="watcher"),
        asyncio.create_task(_run_slack(config, agent), name="slack"),
    ]

    logger.info("🚀 All services starting…")

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for t in done:
        if t.exception():
            logger.error("Service '%s' crashed: %s", t.get_name(), t.exception())
    for t in pending:
        t.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down…")
