"""Minimal browser tools — fallback for visual demo verification only.

The agent has purpose-built review_tools for all API/HTTP work. These browser
tools exist ONLY for the rare case where the agent needs to visually check
that a deployed web app actually renders (not just returns HTTP 200).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile

from browser_use import Browser
from browser_use.browser.profile import BrowserProfile
from pydantic_ai import BinaryContent
from pydantic_ai.messages import ToolReturn

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages a single browser session with lazy init and cleanup."""

    def __init__(self, *, headless: bool = True):
        self._headless = headless
        self._lock = asyncio.Lock()
        self._session: Browser | None = None

    async def get_session(self) -> Browser:
        if self._session is not None and self._session.is_cdp_connected:
            return self._session
        async with self._lock:
            if self._session is None or not self._session.is_cdp_connected:
                self._session = Browser(
                    browser_profile=BrowserProfile(
                        headless=self._headless,
                        window_size={'width': 1280, 'height': 900},
                    ),
                )
                await self._session.start()
        return self._session

    async def get_page(self):
        session = await self.get_session()
        page = await session.get_current_page()
        if page is None:
            page = await session.new_page()
        return page

    async def close(self):
        async with self._lock:
            if self._session is not None:
                try:
                    await self._session.kill()
                except Exception:
                    pass
                finally:
                    self._session = None


HEADLESS = os.getenv('BROWSER_HEADLESS', '1') == '1'
_manager = BrowserManager(headless=HEADLESS)


def _ok(message: str = '', **extra) -> str:
    return json.dumps({'ok': True, 'message': message, **extra})


def _err(reason: str) -> str:
    return json.dumps({'ok': False, 'error': reason})


async def browser_screenshot_url(url: str) -> ToolReturn:
    """Navigate to a URL and take a screenshot to verify the page renders.

    Use this ONLY when you need to visually verify a demo site actually
    renders content (not just returns HTTP 200). For all other URL checks,
    use review_check_url or review_fetch_page_text instead.

    The screenshot image is injected into your context so you can see it
    directly (on multimodal models). On text-only models the file path is
    returned instead.
    """
    try:
        session = await _manager.get_session()
        page = await session.get_current_page()
        if page is None:
            page = await session.new_page()
        await page.goto(url, wait_until='networkidle', timeout=20000)
        await asyncio.sleep(2)  # Let JS render

        fd, path = tempfile.mkstemp(suffix='.png', prefix='screenshot_')
        os.close(fd)
        await page.screenshot(path=path, full_page=False)
        title = await page.title()

        image = BinaryContent.from_path(path)
        return ToolReturn(
            return_value={'ok': True, 'message': f'Screenshot of {url}', 'path': path, 'title': title},
            content=[image],
        )
    except Exception as e:
        return ToolReturn(return_value={'ok': False, 'error': f'Screenshot failed: {e}'})


async def browser_close() -> str:
    """Close the browser session. Call this when the review is complete."""
    try:
        await _manager.close()
        return _ok('Browser closed')
    except Exception as e:
        return _err(f'Close failed: {e}')
