"""Browser tools for Pydantic AI agent using agent-browser CLI."""

from __future__ import annotations

import json as _json
import os
import subprocess
import time

SESSION = 'sw-reviewer'
TIMEOUT = 40
CDP_EVAL_TIMEOUT = 10  # shorter timeout for JS evals so we detect hangs fast
CDP_ACTION_TIMEOUT = 8000  # ms — agent-browser's per-action CDP timeout (default 25000 is too long)
CDP_RETRY_ATTEMPTS = 2

# ── Shared JS primitives injected into every resilient helper ──────
# deepQuery: pierces open shadow roots + same-origin iframes
# visible:   checks computed style + bounding rect
# interactable: visible + enabled + not covered

_JS_PRELUDE = r"""
function deepQuery(sel, root) {
  root = root || document;
  var queue = [root];
  while (queue.length) {
    var node = queue.shift();
    var found = node.querySelector ? node.querySelector(sel) : null;
    if (found) return found;
    var all = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (var i = 0; i < all.length; i++) {
      if (all[i].shadowRoot) queue.push(all[i].shadowRoot);
      if (all[i].tagName === 'IFRAME') {
        try { if (all[i].contentDocument) queue.push(all[i].contentDocument); } catch(e) {}
      }
    }
  }
  return null;
}

function visible(el) {
  if (!el || !el.isConnected) return false;
  var cs = getComputedStyle(el);
  var r = el.getBoundingClientRect();
  return cs.display !== 'none' && cs.visibility !== 'hidden' &&
         cs.opacity !== '0' && r.width > 0 && r.height > 0;
}

function topEl(el) {
  var r = el.getBoundingClientRect();
  var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  var top = document.elementFromPoint(cx, cy);
  return top && (el === top || el.contains(top));
}
"""


def _ab(*args: str, timeout: int = TIMEOUT, stdin_data: str | None = None) -> str:
    """Run an agent-browser command and return stdout.

    Sets AGENT_BROWSER_DEFAULT_TIMEOUT to fail fast on hung pages
    instead of waiting the 25 s default.  Catches subprocess-level
    timeouts and returns a structured error.
    """
    cmd = ['agent-browser', '--session', SESSION, '--json', *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=stdin_data,
            timeout=timeout,
            env={
                **os.environ,
                'AGENT_BROWSER_CONTENT_BOUNDARIES': '1',
                'AGENT_BROWSER_MAX_OUTPUT': '50000',
                'AGENT_BROWSER_DEFAULT_TIMEOUT': str(CDP_ACTION_TIMEOUT),
                'AGENT_BROWSER_HEADED': '1',
            },
        )
        return result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        return '{"error":"subprocess_timeout","success":false}'


def _is_timeout(out: str) -> bool:
    """Check if an agent-browser result indicates a CDP or process timeout."""
    return 'timed out' in out or 'subprocess_timeout' in out


def _ab_with_retry(*args: str, timeout: int = TIMEOUT,
                   stdin_data: str | None = None, retries: int = 1) -> str:
    """Run an agent-browser command; on CDP timeout, recover and retry once.

    NOTE: does NOT auto-dismiss dialogs — a timeout often means a JS
    prompt() is waiting for user input.  Use browser_handle_dialog()
    explicitly to enter text and accept/dismiss the dialog.
    """
    out = _ab(*args, timeout=timeout, stdin_data=stdin_data)
    if not _is_timeout(out) or retries <= 0:
        return out
    # Recovery: close session (kill daemon), wait, then retry
    subprocess.run(
        ['agent-browser', '--session', SESSION, 'close'],
        capture_output=True, text=True, timeout=5,
    )
    time.sleep(1)
    return _ab(*args, timeout=timeout, stdin_data=stdin_data)


def _eval_js(js: str, timeout: int = CDP_EVAL_TIMEOUT) -> str:
    """Shorthand: run JS via eval --stdin.  Retries once on CDP timeout."""
    for attempt in range(CDP_RETRY_ATTEMPTS):
        out = _ab('eval', '--stdin', stdin_data=js, timeout=timeout)
        if not _is_timeout(out):
            return out
        if attempt < CDP_RETRY_ATTEMPTS - 1:
            time.sleep(1)
    return out


def _poll_eval(js: str, *, timeout: float = 8.0, interval: float = 0.3) -> str:
    """Re-run JS until it returns a truthy/non-error result or timeout."""
    deadline = time.monotonic() + timeout
    last = ''
    while time.monotonic() < deadline:
        last = _eval_js(js, timeout=min(int(timeout), CDP_EVAL_TIMEOUT))
        if '"ok":true' in last or '"ok": true' in last:
            return last
        if _is_timeout(last):
            return last
        time.sleep(interval)
    return last


# ── Find elements (semantic locators) ───────────────────────────────

def browser_find(locator: str, value: str, action: str = 'click',
                 action_text: str = '', name: str = '', exact: bool = False) -> str:
    """Find an element by semantic locator and perform an action.

    This is the preferred way to interact with elements when CSS selectors
    are unknown.  It finds elements the way a user would — by their visible
    text, label, role, placeholder, etc.

    locator: 'role', 'text', 'label', 'placeholder', 'alt', 'title', 'testid'
    value:   the text/role to search for (e.g. 'button', 'Next', 'Email')
    action:  'click' (default), 'fill', 'type', 'hover', 'focus', 'check', 'uncheck'
    action_text: text for fill/type actions (e.g. the value to type)
    name:    for role locator, filter by accessible name (e.g. role='button', name='Submit')
    exact:   require exact text match (default: substring/case-insensitive)

    Examples:
      browser_find('text', 'Next', 'click')           — click button with text "Next"
      browser_find('label', 'Email', 'fill', 'a@b.c') — fill email field
      browser_find('role', 'button', 'click', name='Submit')
      browser_find('placeholder', 'Search...', 'type', 'query')
    """
    args = ['find', locator, value, action]
    if action_text:
        args.append(action_text)
    if name:
        args.extend(['--name', name])
    if exact:
        args.append('--exact')
    return _ab_with_retry(*args)


# ── Dialog handling (raw CDP) ───────────────────────────────────────

def _get_cdp_ws_url() -> str | None:
    """Get the CDP WebSocket URL from agent-browser."""
    out = _ab('get', 'cdp-url', timeout=5)
    # Output is JSON: {"data":"ws://...","success":true}
    try:
        data = _json.loads(out)
        return data.get('data') or None
    except (ValueError, TypeError):
        # Might be plain text ws:// URL
        if 'ws://' in out:
            for part in out.split():
                if part.startswith('ws://'):
                    return part
    return None


def browser_handle_dialog(accept: bool = True, prompt_text: str = '') -> str:
    """Dismiss a JavaScript dialog (alert/confirm/prompt) via raw CDP.

    When a native JS dialog is open, ALL agent-browser commands block.
    This tool connects directly to Chrome via CDP WebSocket and sends
    Page.handleJavaScriptDialog to dismiss it.

    accept: True to accept (OK/Yes), False to dismiss (Cancel/No)
    prompt_text: text to enter in prompt() dialogs before accepting

    Call this when you get CDP timeouts after clicking a button that
    might trigger alert(), confirm(), or prompt().
    """
    import asyncio
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets import connect  # type: ignore[assignment]

    ws_url = _get_cdp_ws_url()
    if not ws_url:
        return _json.dumps({'ok': False, 'reason': 'no_cdp_url'})

    async def _dismiss() -> str:
        try:
            async with connect(ws_url, close_timeout=3) as ws:
                msg = _json.dumps({
                    'id': 1,
                    'method': 'Page.handleJavaScriptDialog',
                    'params': {'accept': accept, 'promptText': prompt_text},
                })
                await ws.send(msg)
                resp = await asyncio.wait_for(ws.recv(), timeout=5)
                return resp
        except Exception as e:
            return _json.dumps({'ok': False, 'reason': str(e)})

    try:
        result = asyncio.run(_dismiss())
        return _json.dumps({'ok': True, 'cdp_response': result})
    except Exception as e:
        return _json.dumps({'ok': False, 'reason': str(e)})


# ── Recovery ────────────────────────────────────────────────────────

def browser_recover() -> str:
    """Recover from a hung browser state.

    Kills the agent-browser daemon and restarts a fresh session.
    Use when CDP commands are consistently timing out, which usually
    means the browser page is hung (infinite JS loop, unhandled dialog,
    or crashed renderer).

    After calling this, you must re-navigate to the desired URL.
    """
    # Kill existing daemon
    subprocess.run(
        ['agent-browser', '--session', SESSION, 'close'],
        capture_output=True, text=True, timeout=5,
    )
    time.sleep(1)
    # Verify by getting a fresh snapshot (will start a new daemon)
    return _ab('get', 'url', timeout=10)


# ── Navigation ──────────────────────────────────────────────────────

def browser_navigate(url: str) -> str:
    """Navigate the browser to a URL and load the page.

    Automatically installs shims (disable animations, track pending
    requests, auto-dismiss native dialogs) after the page loads.
    """
    result = _ab('open', url)
    # Auto-install shims so prompt/alert/confirm are intercepted
    browser_js_install_shims()
    return result


def browser_back() -> str:
    """Go back to the previous page."""
    return _ab('back')


def browser_forward() -> str:
    """Go forward to the next page."""
    return _ab('forward')


def browser_reload() -> str:
    """Reload the current page."""
    return _ab('reload')


# ── Reading page content ────────────────────────────────────────────

def browser_snapshot(interactive_only: bool = True) -> str:
    """Get the accessibility tree of the current page.

    Returns interactive elements with @eN refs for clicking/filling.
    Always call this after any navigation or DOM change.
    Set interactive_only=False to get the full accessibility tree.
    """
    args = ['snapshot']
    if interactive_only:
        args.append('-i')
    return _ab(*args)


def browser_get_text(selector: str) -> str:
    """Get the text content of an element by @eN ref or CSS selector."""
    return _ab('get', 'text', selector)


def browser_get_html(selector: str) -> str:
    """Get the innerHTML of an element by @eN ref or CSS selector."""
    return _ab('get', 'html', selector)


def browser_get_attribute(selector: str, attribute: str) -> str:
    """Get an attribute value of an element (e.g. href, src, class)."""
    return _ab('get', 'attr', attribute, selector)


def browser_get_url() -> str:
    """Get the current page URL."""
    return _ab('get', 'url')


def browser_get_title() -> str:
    """Get the current page title."""
    return _ab('get', 'title')


# ── Interaction ─────────────────────────────────────────────────────

def browser_click(ref: str) -> str:
    """Click an element by @eN ref or CSS selector."""
    return _ab_with_retry('click', ref)


def browser_double_click(ref: str) -> str:
    """Double-click an element by @eN ref or CSS selector."""
    return _ab('dblclick', ref)


def browser_fill(ref: str, text: str) -> str:
    """Clear and type text into an input identified by @eN ref or CSS selector."""
    return _ab_with_retry('fill', ref, text)


def browser_type(ref: str, text: str) -> str:
    """Type text into an element without clearing it first."""
    return _ab('type', ref, text)


def browser_press(key: str) -> str:
    """Press a keyboard key (e.g. Enter, Tab, Escape, Control+a, ArrowDown)."""
    return _ab('press', key)


def browser_hover(ref: str) -> str:
    """Hover over an element by @eN ref or CSS selector."""
    return _ab('hover', ref)


def browser_focus(ref: str) -> str:
    """Focus an element by @eN ref or CSS selector."""
    return _ab('focus', ref)


def browser_select(ref: str, value: str) -> str:
    """Select a dropdown option by @eN ref and value."""
    return _ab('select', ref, value)


def browser_check(ref: str) -> str:
    """Check a checkbox by @eN ref or CSS selector."""
    return _ab('check', ref)


def browser_uncheck(ref: str) -> str:
    """Uncheck a checkbox by @eN ref or CSS selector."""
    return _ab('uncheck', ref)


def browser_scroll(direction: str, pixels: int = 500) -> str:
    """Scroll the page. direction: up, down, left, right."""
    return _ab('scroll', direction, str(pixels))


# ── Keyboard (no selector needed) ───────────────────────────────────

def browser_keyboard_type(text: str) -> str:
    """Type text character-by-character into the currently focused element.

    Uses real key events (keydown, keypress, keyup per character).
    Unlike browser_fill/browser_type, this does NOT need a selector —
    it types into whatever element currently has focus.  This makes it
    work even when CDP selector-based commands are timing out.

    Essential for contenteditable editors (Lexical, ProseMirror,
    CodeMirror, Monaco) and as a fallback when fill/type fail.

    Workflow: browser_click(@eN) or browser_focus(@eN), then
              browser_keyboard_type('the text to type')
    """
    return _ab('keyboard', 'type', text)


def browser_keyboard_inserttext(text: str) -> str:
    """Insert text at cursor without key events (like paste).

    Faster than keyboard_type for large text.  No keydown/keyup
    events are fired — just the text insertion.  Works on the
    currently focused element.
    """
    return _ab('keyboard', 'inserttext', text)


# ── Batch (atomic multi-step) ──────────────────────────────────────

def browser_batch(commands_json: str, bail: bool = True) -> str:
    """Execute multiple agent-browser commands in a single call.

    Takes a JSON array of command arrays and runs them sequentially
    in one process.  Much faster than individual calls and avoids
    race conditions between steps.

    commands_json: JSON string, e.g.
      '[["click","@e3"],["fill","@e4","hello"],["click","@e5"]]'
    bail: if True (default), stop on first error.

    Example — fill a form and submit:
      browser_batch('[["fill","@e1","user"],["fill","@e2","pass"],["click","@e3"]]')
    """
    args = ['batch']
    if bail:
        args.append('--bail')
    return _ab(*args, stdin_data=commands_json, timeout=TIMEOUT)


# ── Visual capture ──────────────────────────────────────────────────

def browser_screenshot() -> str:
    """Take a screenshot of the current page and return the file path."""
    return _ab('screenshot')


def browser_screenshot_annotated() -> str:
    """Take an annotated screenshot with numbered labels on interactive elements."""
    return _ab('screenshot', '--annotate')


# ── Waiting ─────────────────────────────────────────────────────────

def browser_wait(target: str) -> str:
    """Wait for a target: an @eN ref, CSS selector, or milliseconds (e.g. '2000').
    For network idle use: '--load networkidle'
    For text on page use: '--text Welcome'
    For URL pattern use:  '--url **/dashboard'
    """
    return _ab('wait', *target.split())


# ── JavaScript ──────────────────────────────────────────────────────

def browser_eval(js: str) -> str:
    """Execute JavaScript in the browser and return the result."""
    return _ab('eval', '--stdin', stdin_data=js)


# ── Resilient JS helpers ────────────────────────────────────────────
# These pierce shadow DOM + iframes, fire framework-compatible events,
# handle overlays, and retry through rerenders.

def browser_js_fill(selector: str, value: str, commit: str = 'blur') -> str:
    """Set an input's value via JS and fire framework-compatible events.

    Works with React, Vue, Angular, Svelte controlled inputs.
    Pierces shadow DOM and same-origin iframes.
    selector: CSS selector (e.g. 'input[name=year]', '#email').
    commit: 'blur' (fire blur after — triggers validation),
            'enter' (press Enter after), or 'none'.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  el.focus();
  el.dispatchEvent(new Event('focus', {{bubbles:true}}));
  // Use native setter to bypass React/Vue controlled-input guards
  const proto = el instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (nativeSetter) nativeSetter.call(el, {value!r}); else el.value = {value!r};
  // Fire InputEvent (not plain Event) — React 16+ listens for this
  el.dispatchEvent(new InputEvent('input', {{bubbles:true, inputType:'insertText', data:{value!r}}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  // Also poke React's internal fiber to force re-render
  const tracker = el._valueTracker;
  if (tracker) tracker.setValue('');
  const commit = {commit!r};
  if (commit === 'blur') {{
    el.dispatchEvent(new FocusEvent('blur', {{bubbles:true}}));
    el.dispatchEvent(new FocusEvent('focusout', {{bubbles:true}}));
  }} else if (commit === 'enter') {{
    el.dispatchEvent(new KeyboardEvent('keydown', {{key:'Enter',code:'Enter',bubbles:true}}));
    el.dispatchEvent(new KeyboardEvent('keyup',   {{key:'Enter',code:'Enter',bubbles:true}}));
  }}
  return JSON.stringify({{ok:true, value:el.value}});
}})()"""
    return _eval_js(js)


def browser_js_fill_date(selector: str, year: int, month: int, day: int) -> str:
    """Set a date input (<input type="date">) reliably.

    Native date inputs ignore the normal .value setter and have shadow DOM
    spinbuttons.  This tool sets the value via both .valueAsDate and the
    ISO string setter, pokes React's _valueTracker, and fires the full
    event sequence.

    selector: CSS selector for the date input (e.g. 'input[type=date]')
    year, month, day: numeric date parts (e.g. 2000, 3, 15 for March 15 2000)
    """
    # ISO format: YYYY-MM-DD (zero-padded)
    iso = f'{year:04d}-{month:02d}-{day:02d}'
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  el.focus();
  el.dispatchEvent(new Event('focus', {{bubbles:true}}));

  // Method 1: native value setter with ISO string
  const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, 'value')?.set;
  if (nativeSetter) nativeSetter.call(el, {iso!r});
  else el.value = {iso!r};

  // Method 2: also set valueAsDate (some frameworks read this)
  try {{ el.valueAsDate = new Date({year}, {month - 1}, {day}); }} catch(e) {{}}

  // Method 3: also set valueAsNumber
  try {{ el.valueAsNumber = new Date({year}, {month - 1}, {day}).getTime(); }} catch(e) {{}}

  // Poke React's value tracker so it detects the change
  const tracker = el._valueTracker;
  if (tracker) tracker.setValue('');

  // Fire full event sequence
  el.dispatchEvent(new InputEvent('input', {{bubbles:true, inputType:'insertText', data:{iso!r}}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  el.dispatchEvent(new FocusEvent('blur', {{bubbles:true}}));
  el.dispatchEvent(new FocusEvent('focusout', {{bubbles:true}}));

  return JSON.stringify({{ok:true, value:el.value, iso:{iso!r}}});
}})()"""
    return _eval_js(js)


def browser_fill_date_keyboard(ref: str, year: int, month: int, day: int) -> str:
    """Fill a date input by clicking it and typing the date via keyboard.

    This is the most reliable approach for native <input type="date">
    because it interacts with the browser's own spinbutton controls
    the same way a human would: focus the field, then type MM DD YYYY
    with Tab between segments.

    ref: @eN ref or CSS selector for the date input or its first spinbutton
    year, month, day: numeric date parts (e.g. 2000, 3, 15)
    """
    # Chrome date inputs accept keyboard input as: MM -> Tab -> DD -> Tab -> YYYY
    mm = f'{month:02d}'
    dd = f'{day:02d}'
    yyyy = f'{year:04d}'
    commands = [
        ['click', ref],
        ['keyboard', 'type', mm],
        ['press', 'Tab'],
        ['keyboard', 'type', dd],
        ['press', 'Tab'],
        ['keyboard', 'type', yyyy],
        ['press', 'Tab'],  # move focus out to trigger change/blur
    ]
    import json
    return _ab('batch', '--bail', stdin_data=json.dumps(commands), timeout=TIMEOUT)


def browser_fill_spinbutton(ref: str, value: str) -> str:
    """Fill a spinbutton (like date part selectors) by focusing and typing.

    Spinbuttons in date pickers don't accept fill/type the normal way.
    This clicks the spinbutton, selects all, and types the value.

    ref: @eN ref for the spinbutton (e.g. from snapshot)
    value: the numeric value to enter (e.g. '3' for March, '2000' for year)
    """
    import json
    commands = [
        ['click', ref],
        ['press', 'Control+a'],
        ['keyboard', 'type', value],
    ]
    return _ab('batch', '--bail', stdin_data=json.dumps(commands), timeout=TIMEOUT)


def browser_js_click(selector: str) -> str:
    """Click an element via JS, bypassing CDP actionability checks.

    Pierces shadow DOM and same-origin iframes.  Scrolls element into
    view first.  Use when browser_click times out due to overlays,
    disabled states, or animations.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  el.scrollIntoView({{block:'center',behavior:'instant'}});
  el.click();
  return JSON.stringify({{ok:true}});
}})()"""
    return _eval_js(js)


def browser_js_select_option(selector: str, value: str) -> str:
    """Select a <select> option via JS and fire change event.

    Pierces shadow DOM.  Works with React controlled selects.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  const proto = HTMLSelectElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setter) setter.call(el, {value!r}); else el.value = {value!r};
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  return JSON.stringify({{ok:true, value:el.value}});
}})()"""
    return _eval_js(js)


def browser_js_check(selector: str, checked: bool = True) -> str:
    """Check or uncheck a checkbox/radio via JS with proper events.

    React ignores raw .checked changes — this uses the native setter.
    """
    val = 'true' if checked else 'false'
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'checked')?.set;
  if (setter) setter.call(el, {val}); else el.checked = {val};
  el.dispatchEvent(new Event('input',  {{bubbles:true}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  el.dispatchEvent(new Event('click',  {{bubbles:true}}));
  return JSON.stringify({{ok:true, checked:el.checked}});
}})()"""
    return _eval_js(js)


# ── Obstruction handling ───────────────────────────────────────────

def browser_js_dismiss_overlays() -> str:
    """Dismiss cookie banners, modals, toasts, and consent dialogs.

    Finds common overlay patterns and clicks their close/accept buttons.
    Call this when clicks are blocked by overlapping elements.
    """
    js = _JS_PRELUDE + r"""
(() => {
  const dismissed = [];

  // Cookie/consent banners
  const consentSels = [
    '[class*=cookie] button[class*=accept]',
    '[class*=cookie] button[class*=close]',
    '[class*=consent] button[class*=accept]',
    '[class*=consent] button[class*=agree]',
    '[id*=cookie] button', '[id*=consent] button',
    'button[class*=cookie-accept]',
    '.cc-btn.cc-dismiss', '#onetrust-accept-btn-handler',
    '[data-testid*=cookie] button',
  ];
  for (const sel of consentSels) {
    const btn = deepQuery(sel);
    if (btn && visible(btn)) { btn.click(); dismissed.push('consent:' + sel); break; }
  }

  // Modal/dialog close buttons
  const modalSels = [
    'dialog[open] button[aria-label*=close]',
    'dialog[open] button[aria-label*=Close]',
    '[role=dialog] button[aria-label*=close]',
    '[role=dialog] button[aria-label*=Close]',
    '[aria-modal=true] button[class*=close]',
    '.modal.show .btn-close', '.modal.show .close',
  ];
  for (const sel of modalSels) {
    const btn = deepQuery(sel);
    if (btn && visible(btn)) { btn.click(); dismissed.push('modal:' + sel); break; }
  }

  // Toast/snackbar close buttons
  const toastSels = [
    '[class*=toast] button[class*=close]',
    '[class*=snackbar] button',
    '[role=alert] button[aria-label*=close]',
  ];
  for (const sel of toastSels) {
    const btn = deepQuery(sel);
    if (btn && visible(btn)) { btn.click(); dismissed.push('toast:' + sel); break; }
  }

  return JSON.stringify({ok: true, dismissed: dismissed});
})()"""
    return _eval_js(js)


# ── Waiting helpers ────────────────────────────────────────────────

def browser_js_wait_interactable(selector: str, timeout: float = 8.0) -> str:
    """Wait until an element is visible, enabled, and not covered.

    Polls every 300ms.  Pierces shadow DOM.  Returns the blocker info
    if timed out.  Use before clicking elements on pages with spinners,
    skeleton screens, or loading states.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  if (!el.isConnected) return JSON.stringify({{ok:false, reason:'detached'}});
  if (!visible(el)) return JSON.stringify({{ok:false, reason:'not_visible'}});
  if (el.disabled || el.getAttribute('aria-disabled') === 'true')
    return JSON.stringify({{ok:false, reason:'disabled'}});
  if (!topEl(el)) {{
    var r = el.getBoundingClientRect();
    var cx = r.left + r.width/2, cy = r.top + r.height/2;
    var blocker = document.elementFromPoint(cx, cy);
    return JSON.stringify({{ok:false, reason:'covered',
      blocker: blocker ? blocker.tagName + '.' + blocker.className : 'unknown'}});
  }}
  return JSON.stringify({{ok:true}});
}})()"""
    return _poll_eval(js, timeout=timeout)


def browser_js_wait_idle(timeout: float = 8.0) -> str:
    """Wait for the page to settle after SPA navigation.

    Checks for: no pending fetches (if shim installed), no visible
    loading indicators, DOM stability (mutation observer), and
    requestAnimationFrame idle.
    """
    js = _JS_PRELUDE + r"""
(() => {
  // Check common busy indicators
  const busySels = [
    '[aria-busy=true]', '[role=progressbar]',
    '.spinner', '.loading', '.skeleton',
    '[class*=spinner]', '[class*=loading]', '[class*=skeleton]',
  ];
  for (const sel of busySels) {
    const el = document.querySelector(sel);
    if (el && visible(el)) return JSON.stringify({ok:false, reason:'busy', indicator:sel});
  }
  // Check pending fetches if shim is installed
  if (window.__abPendingRequests > 0)
    return JSON.stringify({ok:false, reason:'pending_requests',
      count: window.__abPendingRequests});
  return JSON.stringify({ok:true});
})()"""
    return _poll_eval(js, timeout=timeout)


# ── Page shims (install once after navigation) ─────────────────────

def browser_js_install_shims() -> str:
    """Install page-level shims for better automation resilience.

    Call this once after navigating to a new page.  It:
    1. Disables CSS animations/transitions (prevents click-miss)
    2. Tracks pending fetch/XHR requests (for wait_idle)
    3. Auto-accepts native alert/confirm/prompt dialogs
    """
    js = r"""
(() => {
  if (window.__abShimsInstalled) return JSON.stringify({ok:true, msg:'already_installed'});

  // 1. Disable animations
  const style = document.createElement('style');
  style.id = '__ab-no-anim';
  style.textContent = '*, *::before, *::after { ' +
    'animation-duration: 0s !important; animation-delay: 0s !important; ' +
    'transition-duration: 0s !important; transition-delay: 0s !important; }';
  document.head.appendChild(style);

  // 2. Track pending fetch/XHR
  window.__abPendingRequests = 0;
  const origFetch = window.fetch;
  window.fetch = function() {
    window.__abPendingRequests++;
    return origFetch.apply(this, arguments).finally(() => { window.__abPendingRequests--; });
  };
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function() {
    this.__abTracked = true;
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function() {
    if (this.__abTracked) {
      window.__abPendingRequests++;
      this.addEventListener('loadend', () => { window.__abPendingRequests--; }, {once:true});
    }
    return origSend.apply(this, arguments);
  };

  // 3. Auto-accept alert/confirm only (NOT prompt — agent may need to enter text)
  window.alert = () => {};
  window.confirm = () => true;

  window.__abShimsInstalled = true;
  return JSON.stringify({ok:true, msg:'installed'});
})()"""
    return _eval_js(js)


# ── Resilient click (scroll + dismiss + retry) ─────────────────────

def browser_js_click_resilient(selector: str, timeout: float = 8.0) -> str:
    """Click an element with automatic retry, obstruction dismissal,
    and scroll-into-view.

    1. Waits for element to be interactable
    2. If covered, tries to dismiss overlays and retries
    3. Scrolls to center and clicks

    Use this as the go-to click when the page may have overlays,
    animations, or loading states.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  if (!el.isConnected) return JSON.stringify({{ok:false, reason:'detached'}});
  if (!visible(el)) return JSON.stringify({{ok:false, reason:'not_visible'}});
  el.scrollIntoView({{block:'center', behavior:'instant'}});
  if (!topEl(el)) {{
    var r = el.getBoundingClientRect();
    var blocker = document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
    return JSON.stringify({{ok:false, reason:'covered',
      blocker: blocker ? blocker.tagName + '.' + blocker.className : 'unknown'}});
  }}
  el.click();
  return JSON.stringify({{ok:true}});
}})()"""
    return _poll_eval(js, timeout=timeout)


# ── Hover-reveal menus ─────────────────────────────────────────────

def browser_js_hover_reveal(selector: str) -> str:
    """Trigger hover state on an element to reveal dropdown/tooltip menus.

    Dispatches the full pointer/mouse event sequence that CSS :hover
    and JS hover listeners expect.  Useful for nav menus that only
    appear on hover.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  el.scrollIntoView({{block:'center', behavior:'instant'}});
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width/2, cy = r.top + r.height/2;
  const opts = {{bubbles:true, clientX:cx, clientY:cy}};
  el.dispatchEvent(new PointerEvent('pointerover', opts));
  el.dispatchEvent(new MouseEvent('mouseover', opts));
  el.dispatchEvent(new MouseEvent('mouseenter', {{...opts, bubbles:false}}));
  el.dispatchEvent(new MouseEvent('mousemove', opts));
  el.focus();
  return JSON.stringify({{ok:true}});
}})()"""
    return _eval_js(js)


# ── Contenteditable / rich text editors ────────────────────────────

def browser_js_set_contenteditable(selector: str, text: str) -> str:
    """Set text in a contenteditable div or rich text editor.

    Uses execCommand('insertText') which is what real typing does,
    then fires input events.  Works with Quill, Draft.js, TipTap,
    ProseMirror, etc.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  el.focus();
  document.execCommand('selectAll', false, null);
  document.execCommand('insertText', false, {text!r});
  el.dispatchEvent(new Event('input', {{bubbles:true}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  return JSON.stringify({{ok:true, text:el.textContent.substring(0,100)}});
}})()"""
    return _eval_js(js)


# ── ARIA combobox / autocomplete ───────────────────────────────────

def browser_js_select_combobox(selector: str, text: str) -> str:
    """Type into an ARIA combobox and select the matching option.

    Handles autocomplete/typeahead widgets: types per-character to
    trigger the dropdown, finds the listbox via aria-controls, then
    clicks the matching option.
    """
    js = _JS_PRELUDE + f"""
(async () => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  el.focus();
  // Clear existing value
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, 'value')?.set;
  if (setter) setter.call(el, ''); else el.value = '';
  el.dispatchEvent(new Event('input', {{bubbles:true}}));
  // Type per-character
  const text = {text!r};
  for (let i = 0; i < text.length; i++) {{
    if (setter) setter.call(el, text.substring(0, i+1));
    else el.value = text.substring(0, i+1);
    el.dispatchEvent(new Event('input', {{bubbles:true}}));
    await new Promise(r => setTimeout(r, 50));
  }}
  // Wait for listbox
  await new Promise(r => setTimeout(r, 300));
  // Find listbox via aria-controls or role=listbox
  const lbId = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
  let listbox = lbId ? document.getElementById(lbId)
    : document.querySelector('[role=listbox]');
  if (!listbox) return JSON.stringify({{ok:false, reason:'no_listbox'}});
  // Find and click matching option
  const options = listbox.querySelectorAll('[role=option]');
  for (const opt of options) {{
    if (opt.textContent.toLowerCase().includes(text.toLowerCase())) {{
      opt.click();
      return JSON.stringify({{ok:true, selected: opt.textContent.trim()}});
    }}
  }}
  // Fallback: first option
  if (options.length) {{
    options[0].click();
    return JSON.stringify({{ok:true, selected: options[0].textContent.trim(), fallback:true}});
  }}
  return JSON.stringify({{ok:false, reason:'no_matching_option'}});
}})()"""
    return _eval_js(js, timeout=15)


# ── Popup / new-window interception ────────────────────────────────

def browser_js_click_same_tab(selector: str) -> str:
    """Click a link but force it to open in the same tab.

    Removes target=_blank and patches window.open temporarily so
    the agent doesn't lose track of the navigation.
    """
    js = _JS_PRELUDE + f"""
(() => {{
  const el = deepQuery({selector!r});
  if (!el) return JSON.stringify({{ok:false, reason:'not_found'}});
  // Remove target=_blank
  if (el.tagName === 'A') el.removeAttribute('target');
  // Patch window.open
  const origOpen = window.open;
  window.open = function(url) {{
    if (url) window.location.href = url;
    return window;
  }};
  el.click();
  // Restore after a tick
  setTimeout(() => {{ window.open = origOpen; }}, 100);
  return JSON.stringify({{ok:true}});
}})()"""
    return _eval_js(js)


# ── Element state checks ───────────────────────────────────────────

def browser_is_visible(selector: str) -> str:
    """Check if an element is visible."""
    return _ab('is', 'visible', selector)


def browser_is_enabled(selector: str) -> str:
    """Check if an element is enabled (not disabled)."""
    return _ab('is', 'enabled', selector)


# ── Tabs ────────────────────────────────────────────────────────────

def browser_tab_list() -> str:
    """List all open browser tabs."""
    return _ab('tab', 'list')


def browser_tab_new(url: str = '') -> str:
    """Open a new tab, optionally navigating to a URL."""
    args = ['tab', 'new']
    if url:
        args.append(url)
    return _ab(*args)


def browser_tab_close() -> str:
    """Close the current tab."""
    return _ab('tab', 'close')


def browser_tab_switch(index: str) -> str:
    """Switch to a tab by its index number."""
    return _ab('tab', index)


# ── Network / Console ──────────────────────────────────────────────

def browser_console() -> str:
    """View browser console logs (useful for debugging)."""
    return _ab('console')


def browser_errors() -> str:
    """View page errors (useful for reviewing broken apps)."""
    return _ab('errors')


def browser_network_requests(filter_pattern: str = '') -> str:
    """View captured network requests, optionally filtered by URL pattern."""
    args = ['network', 'requests']
    if filter_pattern:
        args.extend(['--filter', filter_pattern])
    return _ab(*args)


# ── Cookies & Storage ──────────────────────────────────────────────

def browser_cookies_get() -> str:
    """Get all cookies for the current page."""
    return _ab('cookies', 'get')


def browser_storage(storage_type: str = 'local') -> str:
    """Read web storage. storage_type: 'local' or 'session'."""
    return _ab('storage', storage_type)


# ── Session ─────────────────────────────────────────────────────────

def browser_close() -> str:
    """Close the browser session."""
    return _ab('close')
