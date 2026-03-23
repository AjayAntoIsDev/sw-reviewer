"""
Typst report generation pipeline.
Generates .typ source and optionally compiles to .pdf.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..models import FinalVerdict

logger = logging.getLogger(__name__)

# ── Typst template ────────────────────────────────────────────────────────────

TYPST_TEMPLATE = """\
#set document(
  title: "Shipwright Review Report",
  author: "Shipwright AI Reviewer",
)
#set page(margin: 1.5cm)
#set text(font: "Liberation Serif", size: 11pt)

= Shipwright Review Report

#grid(
  columns: (auto, 1fr),
  gutter: 0.5em,
  [*Review ID:*], [{review_id}],
  [*Repository:*], [{repository_url}],
  [*Generated:*], [{generated_at}],
  [*Verdict:*], [*{verdict_upper}*],
)

---

== Summary

{summary}

---

== Policy Checklist

#table(
  columns: (1fr, auto, 2fr),
  [*Check*], [*Result*], [*Reason*],
  {policy_rows}
)

#if {has_web_results} [
  ---
  == Web Flow Results

  #table(
    columns: (1fr, auto, auto),
    [*Flow*], [*Success*], [*Duration (ms)*],
    {web_rows}
  )
]

#if {has_cli_results} [
  ---
  == CLI Command Results

  #table(
    columns: (2fr, auto, auto),
    [*Command*], [*Exit Code*], [*Duration (ms)*],
    {cli_rows}
  )
]

---

_This report was generated automatically by Shipwright AI Reviewer._
"""


def _escape_typst(text: str) -> str:
    """Escape special Typst characters."""
    return (
        text.replace("\\", "\\\\")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace("#", "\\#")
    )


def render_typst_source(verdict: FinalVerdict, repository_url: str = "") -> str:
    """Fill the Typst template with verdict data and return the .typ source string."""
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Policy rows
    policy_rows_parts = []
    for r in verdict.check_results:
        result_icon = "✅" if r.passed else "❌"
        policy_rows_parts.append(
            f"[{_escape_typst(r.policy.id)}], [{result_icon}], [{_escape_typst(r.reasoning[:100])}],"
        )
    policy_rows = "\n  ".join(policy_rows_parts) if policy_rows_parts else "[No checks], [], [],"

    # Web rows
    web_rows_parts = []
    for w in verdict.web_results:
        icon = "✅" if w.success else "❌"
        web_rows_parts.append(f"[{_escape_typst(w.flow_id)}], [{icon}], [{w.duration_ms}],")
    web_rows = "\n  ".join(web_rows_parts) if web_rows_parts else "[No web results], [], [],"

    # CLI rows
    cli_rows_parts = []
    for c in verdict.cli_results:
        icon = "✅" if c.success else "❌"
        cli_rows_parts.append(f"[{_escape_typst(c.command[:60])}], [{c.exit_code}], [{c.duration_ms}],")
    cli_rows = "\n  ".join(cli_rows_parts) if cli_rows_parts else "[No CLI results], [], [],"

    source = TYPST_TEMPLATE.format(
        review_id=_escape_typst(verdict.review_id),
        repository_url=_escape_typst(repository_url),
        generated_at=generated_at,
        verdict_upper=_escape_typst(verdict.decision.value.upper()),
        summary=_escape_typst(verdict.summary),
        policy_rows=policy_rows,
        has_web_results="true" if verdict.web_results else "false",
        web_rows=web_rows,
        has_cli_results="true" if verdict.cli_results else "false",
        cli_rows=cli_rows,
    )
    return source


async def generate_report(
    verdict: FinalVerdict,
    repository_url: str,
    output_dir: str,
    typst_binary: str = "typst",
    compile_pdf: bool = True,
) -> dict:
    """
    Generate .typ source and optionally compile to .pdf.

    Returns a dict with keys: typ_path, pdf_path (or None), json_path.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Write JSON verdict bundle
    json_path = out / "verdict.json"
    json_path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")

    # 2. Write .typ source
    typ_source = render_typst_source(verdict, repository_url)
    typ_path = out / "report.typ"
    typ_path.write_text(typ_source, encoding="utf-8")

    pdf_path = None

    # 3. Compile to PDF if requested and Typst is available
    if compile_pdf:
        pdf_path_candidate = out / "report.pdf"
        try:
            proc = await asyncio.create_subprocess_exec(
                typst_binary, "compile", str(typ_path), str(pdf_path_candidate),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode == 0:
                pdf_path = str(pdf_path_candidate)
                logger.info("Typst PDF compiled: %s", pdf_path)
            else:
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                logger.warning("Typst compilation failed (exit %d): %s", proc.returncode, stderr)
        except FileNotFoundError:
            logger.info("Typst binary '%s' not found; skipping PDF compilation.", typst_binary)
        except asyncio.TimeoutError:
            logger.warning("Typst compilation timed out.")
        except Exception as exc:
            logger.warning("Typst compilation error: %s", exc)

    return {
        "typ_path": str(typ_path),
        "pdf_path": pdf_path,
        "json_path": str(json_path),
    }
