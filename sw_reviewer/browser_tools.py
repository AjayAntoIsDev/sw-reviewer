"""Browser tools for Pydantic AI agent using browser-use library."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile

from browser_use import Browser
from browser_use.browser.profile import BrowserProfile

logger = logging.getLogger(__name__)

# ── Browser Manager (singleton) ────────────────────────────────────


class BrowserManager:
    """Manages a single BrowserSession with lazy init and cleanup."""

    def __init__(self, *, headless: bool = False):
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
        """Get the current page, creating one if needed."""
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


HEADLESS = os.getenv('BROWSER_HEADLESS', '0') != '1'
_manager = BrowserManager(headless=not HEADLESS)


def _ok(message: str = '', **extra) -> str:
    return json.dumps({'ok': True, 'message': message, **extra})


def _err(reason: str) -> str:
    return json.dumps({'ok': False, 'error': reason})


# ── Navigation ──────────────────────────────────────────────────────


async def browser_navigate(url: str) -> str:
    """Navigate the browser to a URL and load the page."""
    try:
        session = await _manager.get_session()
        await session.navigate_to(url)
        page = await session.get_current_page()
        title = await page.get_title() if page else ''
        return _ok(f'Navigated to {url}', title=title)
    except Exception as e:
        return _err(f'Navigation failed: {e}')


async def browser_back() -> str:
    """Go back to the previous page."""
    try:
        page = await _manager.get_page()
        await page.go_back()
        url = await page.get_url()
        return _ok('Navigated back', url=url)
    except Exception as e:
        return _err(f'Go back failed: {e}')


async def browser_forward() -> str:
    """Go forward to the next page."""
    try:
        page = await _manager.get_page()
        await page.go_forward()
        url = await page.get_url()
        return _ok('Navigated forward', url=url)
    except Exception as e:
        return _err(f'Go forward failed: {e}')


async def browser_reload() -> str:
    """Reload the current page."""
    try:
        page = await _manager.get_page()
        await page.reload()
        return _ok('Page reloaded')
    except Exception as e:
        return _err(f'Reload failed: {e}')


# ── Reading page content ────────────────────────────────────────────


async def browser_snapshot() -> str:
    """Get the current page state as text.

    Returns interactive elements with [N] index refs for clicking/filling.
    Always call this after any navigation or DOM change to see what's on
    the page and get element indices for interaction.
    """
    try:
        session = await _manager.get_session()
        state_text = await session.get_state_as_text()
        return state_text or 'Empty page'
    except Exception as e:
        return _err(f'Snapshot failed: {e}')


async def browser_get_text(selector: str) -> str:
    """Get the text content of an element by CSS selector."""
    try:
        page = await _manager.get_page()
        elements = await page.get_elements_by_css_selector(selector)
        if not elements:
            return _err(f'No element found for selector: {selector}')
        text = await elements[0].evaluate('() => this.textContent')
        return json.dumps({'ok': True, 'text': text})
    except Exception as e:
        return _err(f'Get text failed: {e}')


async def browser_get_html(selector: str) -> str:
    """Get the innerHTML of an element by CSS selector."""
    try:
        page = await _manager.get_page()
        elements = await page.get_elements_by_css_selector(selector)
        if not elements:
            return _err(f'No element found for selector: {selector}')
        html = await elements[0].evaluate('() => this.innerHTML')
        # Truncate large HTML
        if len(html) > 50000:
            html = html[:50000] + '... (truncated)'
        return json.dumps({'ok': True, 'html': html})
    except Exception as e:
        return _err(f'Get HTML failed: {e}')


async def browser_get_attribute(selector: str, attribute: str) -> str:
    """Get an attribute value of an element (e.g. href, src, class)."""
    try:
        page = await _manager.get_page()
        elements = await page.get_elements_by_css_selector(selector)
        if not elements:
            return _err(f'No element found for selector: {selector}')
        value = await elements[0].get_attribute(attribute)
        return json.dumps({'ok': True, 'value': value})
    except Exception as e:
        return _err(f'Get attribute failed: {e}')


async def browser_get_url() -> str:
    """Get the current page URL."""
    try:
        page = await _manager.get_page()
        url = await page.get_url()
        return json.dumps({'ok': True, 'url': url})
    except Exception as e:
        return _err(f'Get URL failed: {e}')


async def browser_get_title() -> str:
    """Get the current page title."""
    try:
        page = await _manager.get_page()
        title = await page.get_title()
        return json.dumps({'ok': True, 'title': title})
    except Exception as e:
        return _err(f'Get title failed: {e}')


# ── Interaction (by element index) ──────────────────────────────────


async def _get_element_by_index(index: int):
    """Resolve an element index from the last snapshot to a browser-use Element."""
    session = await _manager.get_session()
    node = await session.get_element_by_index(index)
    if node is None:
        raise ValueError(
            f'Element index {index} not found — page may have changed. '
            'Call browser_snapshot() to refresh element indices.'
        )
    page = await _manager.get_page()
    return await page.get_element(node.backend_node_id)


async def browser_click(index: int) -> str:
    """Click an element by its [N] index from browser_snapshot().

    index: the numeric index shown as [N] in the snapshot output.
    """
    try:
        element = await _get_element_by_index(index)
        await element.click()
        return _ok(f'Clicked element [{index}]')
    except Exception as e:
        return _err(f'Click failed: {e}')


async def browser_double_click(index: int) -> str:
    """Double-click an element by its [N] index from browser_snapshot()."""
    try:
        element = await _get_element_by_index(index)
        await element.click(click_count=2)
        return _ok(f'Double-clicked element [{index}]')
    except Exception as e:
        return _err(f'Double-click failed: {e}')


async def browser_fill(index: int, text: str) -> str:
    """Clear and type text into an input by its [N] index from browser_snapshot().

    index: the numeric index shown as [N] in the snapshot output.
    text: the text to fill into the input.
    """
    try:
        element = await _get_element_by_index(index)
        await element.fill(text)
        return _ok(f'Filled element [{index}]')
    except Exception as e:
        return _err(f'Fill failed: {e}')


async def browser_hover(index: int) -> str:
    """Hover over an element by its [N] index from browser_snapshot()."""
    try:
        element = await _get_element_by_index(index)
        await element.hover()
        return _ok(f'Hovered element [{index}]')
    except Exception as e:
        return _err(f'Hover failed: {e}')


async def browser_focus(index: int) -> str:
    """Focus an element by its [N] index from browser_snapshot()."""
    try:
        element = await _get_element_by_index(index)
        await element.focus()
        return _ok(f'Focused element [{index}]')
    except Exception as e:
        return _err(f'Focus failed: {e}')


async def browser_select(index: int, value: str) -> str:
    """Select a dropdown option by element [N] index and value."""
    try:
        element = await _get_element_by_index(index)
        await element.select_option(value)
        return _ok(f'Selected "{value}" in element [{index}]')
    except Exception as e:
        return _err(f'Select failed: {e}')


async def browser_check(index: int) -> str:
    """Check a checkbox by its [N] index from browser_snapshot()."""
    try:
        element = await _get_element_by_index(index)
        await element.check()
        return _ok(f'Checked element [{index}]')
    except Exception as e:
        return _err(f'Check failed: {e}')


async def browser_drag(source_index: int, target_index: int) -> str:
    """Drag one element to another by their [N] indices from browser_snapshot()."""
    try:
        source = await _get_element_by_index(source_index)
        target = await _get_element_by_index(target_index)
        await source.drag_to(target)
        return _ok(f'Dragged [{source_index}] to [{target_index}]')
    except Exception as e:
        return _err(f'Drag failed: {e}')


# ── Keyboard (page-level, no selector needed) ──────────────────────


async def browser_press(key: str) -> str:
    """Press a keyboard key (e.g. Enter, Tab, Escape, Control+a, ArrowDown).

    Types into whatever element currently has focus.
    Supports key combinations like 'Control+a', 'Shift+Tab'.
    """
    try:
        page = await _manager.get_page()
        await page.press(key)
        return _ok(f'Pressed {key}')
    except Exception as e:
        return _err(f'Press failed: {e}')


async def browser_type(text: str) -> str:
    """Type text character-by-character into the currently focused element.

    Unlike browser_fill, this does NOT need an element index — it types
    into whatever element currently has focus. Useful for contenteditable
    editors and as a fallback when fill fails.

    Workflow: browser_click(N) then browser_type('the text to type')
    """
    try:
        page = await _manager.get_page()
        # Type each character using press
        for char in text:
            await page.press(char)
        return _ok(f'Typed {len(text)} characters')
    except Exception as e:
        return _err(f'Type failed: {e}')


# ── Scrolling ──────────────────────────────────────────────────────


async def browser_scroll(direction: str, pixels: int = 500) -> str:
    """Scroll the page. direction: up, down, left, right."""
    try:
        page = await _manager.get_page()
        mouse = await page.mouse
        dx, dy = 0, 0
        if direction == 'down':
            dy = pixels
        elif direction == 'up':
            dy = -pixels
        elif direction == 'right':
            dx = pixels
        elif direction == 'left':
            dx = -pixels
        else:
            return _err(f'Invalid direction: {direction}. Use up/down/left/right.')
        await mouse.scroll(x=640, y=450, delta_x=dx, delta_y=dy)
        return _ok(f'Scrolled {direction} {pixels}px')
    except Exception as e:
        return _err(f'Scroll failed: {e}')


# ── Visual capture ──────────────────────────────────────────────────


async def browser_screenshot() -> str:
    """Take a screenshot of the current page and save it to a temp file. Returns the file path."""
    try:
        page = await _manager.get_page()
        fd, path = tempfile.mkstemp(suffix='.png', prefix='screenshot_')
        os.close(fd)
        await page.screenshot(path=path, full_page=False)
        return _ok('Screenshot saved', path=path)
    except Exception as e:
        return _err(f'Screenshot failed: {e}')


async def browser_screenshot_to_file(path: str = '') -> str:
    """Take a screenshot and save it to a file. Returns the file path."""
    try:
        session = await _manager.get_session()
        if not path:
            fd, path = tempfile.mkstemp(suffix='.png', prefix='screenshot_')
            os.close(fd)
        await session.take_screenshot(path=path, format='png')
        return _ok('Screenshot saved', path=path)
    except Exception as e:
        return _err(f'Screenshot to file failed: {e}')


# ── JavaScript ──────────────────────────────────────────────────────


async def browser_eval(js: str) -> str:
    """Execute JavaScript in the browser and return the result.

    The JS must use arrow function format: '() => document.title'
    For arguments: '(x, y) => x + y' with values passed separately.
    """
    try:
        page = await _manager.get_page()
        result = await page.evaluate(js)
        if len(result) > 50000:
            result = result[:50000] + '... (truncated)'
        return json.dumps({'ok': True, 'result': result})
    except Exception as e:
        return _err(f'Eval failed: {e}')


# ── Tab management ──────────────────────────────────────────────────


async def browser_tab_list() -> str:
    """List all open browser tabs with their IDs, URLs, and titles."""
    try:
        session = await _manager.get_session()
        tabs = await session.get_tabs()
        tab_info = []
        for tab in tabs:
            tab_info.append({
                'tab_id': tab.target_id[-4:],
                'url': tab.url,
                'title': tab.title,
            })
        return json.dumps({'ok': True, 'tabs': tab_info})
    except Exception as e:
        return _err(f'Tab list failed: {e}')


async def browser_tab_new(url: str = '') -> str:
    """Open a new tab, optionally navigating to a URL."""
    try:
        session = await _manager.get_session()
        page = await session.new_page(url or None)
        new_url = await page.get_url()
        return _ok(f'Opened new tab', url=new_url)
    except Exception as e:
        return _err(f'New tab failed: {e}')


async def browser_tab_close(tab_id: str = '') -> str:
    """Close a tab by its tab_id (last 4 chars shown in browser_tab_list)."""
    try:
        session = await _manager.get_session()
        if tab_id:
            from browser_use.browser.events import CloseTabEvent
            target_id = await session.get_target_id_from_tab_id(tab_id)
            event = session.event_bus.dispatch(CloseTabEvent(target_id=target_id))
            await event
        else:
            page = await session.get_current_page()
            if page:
                await session.close_page(page)
        return _ok(f'Closed tab {tab_id or "(current)"}')
    except Exception as e:
        return _err(f'Close tab failed: {e}')


async def browser_tab_switch(tab_id: str) -> str:
    """Switch to a tab by its tab_id (last 4 chars shown in browser_tab_list)."""
    try:
        session = await _manager.get_session()
        from browser_use.browser.events import SwitchTabEvent
        target_id = await session.get_target_id_from_tab_id(tab_id)
        event = session.event_bus.dispatch(SwitchTabEvent(target_id=target_id))
        await event
        return _ok(f'Switched to tab {tab_id}')
    except Exception as e:
        return _err(f'Switch tab failed: {e}')


# ── Element inspection by CSS selector ─────────────────────────────


async def browser_is_visible(selector: str) -> str:
    """Check if an element matching a CSS selector is visible."""
    try:
        page = await _manager.get_page()
        elements = await page.get_elements_by_css_selector(selector)
        if not elements:
            return json.dumps({'ok': True, 'visible': False, 'reason': 'not_found'})
        box = await elements[0].get_bounding_box()
        visible = box is not None and box['width'] > 0 and box['height'] > 0
        return json.dumps({'ok': True, 'visible': visible})
    except Exception as e:
        return _err(f'Visibility check failed: {e}')


# ── Waiting ─────────────────────────────────────────────────────────


async def browser_wait(seconds: int = 3) -> str:
    """Wait for a specified number of seconds (max 30)."""
    seconds = min(max(seconds, 1), 30)
    await asyncio.sleep(seconds)
    return _ok(f'Waited {seconds} seconds')


# ── Recovery ────────────────────────────────────────────────────────


async def browser_recover() -> str:
    """Recover from a hung browser state.

    Kills the browser session and starts a fresh one.
    After calling this, you must re-navigate to the desired URL.
    """
    try:
        await _manager.close()
        await _manager.get_session()
        return _ok('Browser recovered — re-navigate to your target URL')
    except Exception as e:
        return _err(f'Recovery failed: {e}')


async def browser_close() -> str:
    """Close the browser session."""
    try:
        await _manager.close()
        return _ok('Browser closed')
    except Exception as e:
        return _err(f'Close failed: {e}')
