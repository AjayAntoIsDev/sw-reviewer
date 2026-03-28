"""Download Slack file attachments and convert to pydantic-ai input parts."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic_ai import BinaryContent

logger = logging.getLogger(__name__)

MAX_IMAGES = 3
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
SUPPORTED_IMAGE_TYPES = frozenset({
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
})


async def download_slack_file(url: str, bot_token: str) -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={'Authorization': f'Bearer {bot_token}'},
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content


async def build_user_content(
    text: str,
    files: list[dict[str, Any]] | None,
    bot_token: str,
) -> str | list[Any]:
    """Build pydantic-ai user content from Slack message text + attached files.

    Returns plain text if no supported images, or a multimodal list otherwise.
    """
    if not files:
        return text

    parts: list[Any] = [text] if text else []
    image_count = 0

    for file_info in files:
        mimetype = file_info.get('mimetype', '')
        if mimetype not in SUPPORTED_IMAGE_TYPES:
            continue
        if image_count >= MAX_IMAGES:
            break

        size = file_info.get('size', 0)
        if size > MAX_FILE_SIZE:
            logger.warning('Skipping file %s: too large (%d bytes)', file_info.get('name'), size)
            continue

        url = file_info.get('url_private')
        if not url:
            continue

        try:
            data = await download_slack_file(url, bot_token)
            parts.append(BinaryContent(data=data, media_type=mimetype))
            image_count += 1
        except Exception:
            logger.exception('Failed to download Slack file: %s', file_info.get('name'))

    if not parts:
        return text
    if len(parts) == 1 and isinstance(parts[0], str):
        return text
    return parts
