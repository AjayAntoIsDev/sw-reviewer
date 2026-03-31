"""Watch for new ships and auto-review them, posting results to Slack."""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from slack_sdk.web.async_client import AsyncWebClient

from sw_reviewer.config import configure_observability, load_config
from sw_reviewer.agent import create_agent
from sw_reviewer.shipwrights_tools import _get_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "C0ANDAD1DRC"
POLL_INTERVAL = 20.0
SHIP_LIMIT = 30


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sw_request(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    headers, cookies = _get_auth()
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url, params=params, headers=headers, cookies=cookies)
    if resp.status_code != 200:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")
    return resp


def fetch_latest_ships(base_url: str, status: str, limit: int) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/admin/ship_certifications"
    resp = _sw_request(url, {"sortBy": "newest", "status": status})
    body = resp.json()
    certs = body.get("certifications", []) if isinstance(body, dict) else []
    if not isinstance(certs, list):
        return []
    return certs[:limit]


def fetch_ship_by_id(base_url: str, ship_id: int) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/admin/ship_certifications/{ship_id}"
    return _sw_request(url).json()


def _build_ship_text(ship: dict) -> str:
    """Build a Slack mrkdwn message for a new ship."""
    ship_id = ship.get("id")
    project_name = ship.get("project") or "Unknown"
    project_type = ship.get("type") or "unknown"
    desc = ship.get("desc") or ""

    lines = [f"*New ship!!* :yay:  \n {project_name} · {project_type}"]
    if desc:
        lines.append(desc)

    # Footer links
    footer_parts: list[str] = []
    if ship_id:
        cert_url = f"https://review.hackclub.com/admin/ship_certifications/{ship_id}/edit"
        footer_parts.append(f"<{cert_url}|#{ship_id}>")

    links = ship.get("links") or {}
    if isinstance(links, dict):
        demo = links.get("demo") or links.get("demo_url") or links.get("deploymentUrl") or ""
        repo = links.get("repo") or links.get("repo_url") or links.get("repoUrl") or ""
        readme = links.get("readme") or links.get("readmeUrl") or ""
    else:
        demo, repo, readme = "", "", ""

    if demo:
        footer_parts.append(f"<{demo}|Demo>")
    if repo:
        footer_parts.append(f"<{repo}|Repo>")
        if not readme:
            readme = repo.rstrip("/") + "#readme"
    if readme:
        footer_parts.append(f"<{readme}|README>")

    ft_id = ship.get("ftId") or ship.get("ftProjectId")
    if ft_id:
        ft_url = f"https://flavortown.hackclub.com/projects/{ft_id}"
        footer_parts.append(f"<{ft_url}|Flavortown>")

    if footer_parts:
        lines.append(" · ".join(footer_parts))

    return "\n".join(lines)


async def run_review_for_ship(agent, ship: dict, slack: AsyncWebClient, channel: str) -> None:
    """Post ship details to Slack, run the review, and post the PDF."""
    ship_id = ship.get("id")

    # Post the ship details message
    post_resp = await slack.chat_postMessage(channel=channel, text=_build_ship_text(ship))
    msg_ts = post_resp["ts"]

    # Reply in thread: starting review
    await slack.chat_postMessage(
        channel=channel,
        thread_ts=msg_ts,
        text=":think: Running the automated review this might take 1-2 min…",
    )

    # Run the agent (non-streaming) to perform the review
    pdf_path = None
    try:
        result = await agent.run(
            f"Review the project {ship_id}",
        )

        # Extract PDF path from tool results in the messages
        for msg in result.all_messages():
            for part in getattr(msg, "parts", []):
                tool_name = getattr(part, "tool_name", None)
                if tool_name == "review_generate_pdf":
                    content = getattr(part, "content", "")
                    try:
                        parsed = json.loads(content) if isinstance(content, str) else {}
                        path = parsed.get("path", "")
                        if path and os.path.isfile(path):
                            pdf_path = path
                    except (json.JSONDecodeError, TypeError):
                        pass

        if pdf_path:
            await slack.files_upload_v2(
                channel=channel,
                thread_ts=msg_ts,
                file=pdf_path,
                filename="review_report.pdf",
                initial_comment=":thumbup-nobg: Review complete!",
            )
        else:
            await slack.chat_postMessage(
                channel=channel,
                thread_ts=msg_ts,
                text="Review completed but no PDF was generated, ping floppy :sorrytutter:",
            )

    except Exception:
        logger.exception(f"Review failed for ship {ship_id}")
        await slack.chat_postMessage(
            channel=channel,
            thread_ts=msg_ts,
            text=":explode: Review failed. yea idk ping floppy.",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch for new ships or test a single review.")
    parser.add_argument(
        "--test-ship",
        type=int,
        default=None,
        help="Run a single review for this ship cert ID and exit (e.g. --test-ship 5868)",
    )
    parser.add_argument(
        "--channel",
        default=DEFAULT_CHANNEL,
        help=f"Slack channel ID to post to (default: {DEFAULT_CHANNEL})",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    config = load_config()
    configure_observability(config)

    base_url = os.getenv("SW_DASH_BASE_URL", "https://review.hackclub.com")
    if not config.slack_bot_token:
        raise RuntimeError("Missing SLACK_BOT_TOKEN in .env")

    agent = create_agent(config)
    slack = AsyncWebClient(token=config.slack_bot_token)
    channel = args.channel

    # Single-shot test mode
    if args.test_ship is not None:
        logger.info(f"[{utc_now()}] Testing review for ship {args.test_ship} → channel {channel}")
        ship = fetch_ship_by_id(base_url, args.test_ship)
        await run_review_for_ship(agent, ship, slack, channel)
        logger.info(f"[{utc_now()}] Test complete")
        return

    # Watch mode
    seen_ids: set[int] = set()
    first_poll = True

    logger.info(f"[{utc_now()}] Watching new ships on {base_url} → channel {channel} (interval={POLL_INTERVAL}s)")

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
                logger.info(f"[{utc_now()}] Initial poll: {len(seen_ids)} existing ships tracked")
            else:
                seen_ids |= current_ids
                for ship in new_ships:
                    logger.info(f"[{utc_now()}] NEW_SHIP id={ship.get('id')}")
                    await run_review_for_ship(agent, ship, slack, channel)

        except Exception:
            logger.exception(f"[{utc_now()}] Poll error")

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
