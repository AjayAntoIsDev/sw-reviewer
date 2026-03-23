"""
Web execution adapter using Playwright for browser automation.
Implements T07 (adapter), T08 (flow validation), T09 (screenshots), T10 (auth checks).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from ..models import WebFlowResult, EvidenceItem

logger = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class WebFlowSpec:
    """Specification for a web flow to execute."""
    flow_id: str
    url: str
    description: str = ""
    steps: List[str] = field(default_factory=list)  # Natural language step descriptions
    is_auth_flow: bool = False


@dataclass
class WebExecutionResult:
    """Raw result from executing a single web flow."""
    flow_id: str
    url: str
    success: bool
    error: Optional[str] = None
    screenshot_paths: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    duration_ms: int = 0


# ── Main adapter class ────────────────────────────────────────────────────────

class WebExecutor:
    """
    Playwright-based executor for running web validation flows.
    Requires `playwright` package and `playwright install chromium`.
    """

    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        headless: bool = True,
        timeout_ms: int = 30_000,
    ):
        self.artifacts_dir = Path(artifacts_dir)
        self.headless = headless
        self.timeout_ms = timeout_ms

    async def execute_flow(
        self,
        review_id: str,
        spec: WebFlowSpec,
    ) -> WebExecutionResult:
        """Execute a single web flow and return the result with screenshots."""
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except ImportError:
            logger.warning("Playwright not installed; web execution will be skipped.")
            return WebExecutionResult(
                flow_id=spec.flow_id,
                url=spec.url,
                success=False,
                error="Playwright not installed.",
            )

        artifacts_dir = self.artifacts_dir / review_id / "screenshots"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        console_errors: List[str] = []
        screenshot_paths: List[str] = []
        start = time.monotonic()
        success = False
        error = None

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

                page.set_default_timeout(self.timeout_ms)

                await page.goto(spec.url, wait_until="networkidle", timeout=self.timeout_ms)

                # Take initial screenshot
                ss_path = str(artifacts_dir / f"{spec.flow_id}_initial.png")
                await page.screenshot(path=ss_path, full_page=True)
                screenshot_paths.append(ss_path)

                # Execute auth flow detection if required
                if spec.is_auth_flow:
                    await self._attempt_auth_detection(page, spec, artifacts_dir, screenshot_paths)

                success = True

                # Take final screenshot
                final_ss = str(artifacts_dir / f"{spec.flow_id}_final.png")
                await page.screenshot(path=final_ss, full_page=True)
                if final_ss not in screenshot_paths:
                    screenshot_paths.append(final_ss)

                await browser.close()

        except Exception as exc:
            error = str(exc)
            logger.error(
                "Web flow '%s' failed for %s: %s",
                spec.flow_id, spec.url, exc,
                exc_info=True,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        return WebExecutionResult(
            flow_id=spec.flow_id,
            url=spec.url,
            success=success,
            error=error,
            screenshot_paths=screenshot_paths,
            console_errors=console_errors[:20],  # Cap console errors
            duration_ms=duration_ms,
        )

    async def _attempt_auth_detection(
        self,
        page,
        spec: WebFlowSpec,
        artifacts_dir: Path,
        screenshot_paths: List[str],
    ) -> None:
        """Attempt to detect and screenshot auth flows (OAuth buttons, sign-in forms)."""
        try:
            # Look for common auth UI patterns
            auth_selectors = [
                "button:has-text('Sign in')",
                "button:has-text('Log in')",
                "button:has-text('Sign up')",
                "a:has-text('Sign in')",
                "a:has-text('Login')",
                "[data-testid='login']",
                "input[type='email']",
            ]
            for selector in auth_selectors:
                element = page.locator(selector).first
                if await element.is_visible():
                    ss_path = str(artifacts_dir / f"{spec.flow_id}_auth_detected.png")
                    await page.screenshot(path=ss_path)
                    screenshot_paths.append(ss_path)
                    logger.info("Auth element detected: %s", selector)
                    break
        except Exception as exc:
            logger.debug("Auth detection skipped: %s", exc)

    async def execute_flows(
        self,
        review_id: str,
        specs: List[WebFlowSpec],
    ) -> List[WebExecutionResult]:
        """Execute multiple web flows sequentially."""
        results = []
        for spec in specs:
            result = await self.execute_flow(review_id, spec)
            results.append(result)
        return results

    def to_web_flow_results(
        self,
        raw_results: List[WebExecutionResult],
        evidence_items: Optional[List[EvidenceItem]] = None,
    ) -> List[WebFlowResult]:
        """Convert raw execution results to typed WebFlowResult models."""
        out = []
        for r in raw_results:
            # Register screenshots as evidence items if provided
            ss_ids = []
            if evidence_items is not None:
                for ss_path in r.screenshot_paths:
                    ev_id = f"screenshot_{r.flow_id}_{len(evidence_items)}"
                    evidence_items.append(EvidenceItem(
                        id=ev_id,
                        type="screenshot",
                        source_stage="web",
                        payload={"path": ss_path},
                    ))
                    ss_ids.append(ev_id)

            out.append(WebFlowResult(
                flow_id=r.flow_id,
                success=r.success,
                url_visited=r.url,
                screenshots=ss_ids,
                console_errors=r.console_errors,
                duration_ms=r.duration_ms,
            ))
        return out
