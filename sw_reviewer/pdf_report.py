"""Generate a Hack Club-themed PDF review report using Typst."""

import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timezone

TEMPLATE_PATH = Path(__file__).parent / "templates" / "review_report.typ"


def generate_review_pdf(
    verdict: str,
    project_type: str,
    checks: list[dict],  # list of {"name": str, "status": str, "details": str}
    reasoning: str,
    repo_url: str = "",
    demo_url: str = "",
    project_name: str = "",
    project_desc: str = "",
    project_url: str = "",
    required_fixes: list[str] | None = None,
    feedback: list[str] | None = None,
    special_flags: list[str] | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """Generate a PDF review report and return the output path."""

    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".pdf"))
    else:
        output_path = Path(output_path)

    # Write structured data to a temp JSON file
    data = {
        "checks": checks,
        "required_fixes": required_fixes or [],
        "feedback": feedback or [],
        "special_flags": special_flags or [],
    }

    data_file = Path(tempfile.mktemp(suffix=".json"))
    data_file.write_text(json.dumps(data))

    review_date = datetime.now(timezone.utc).strftime("%-m/%-d/%y %-H:%M UTC")

    try:
        result = subprocess.run(
            [
                "typst", "compile",
                "--root", "/",
                "--input", f"verdict={verdict}",
                "--input", f"project_type={project_type}",
                "--input", f"reasoning={reasoning}",
                "--input", f"repo_url={repo_url}",
                "--input", f"demo_url={demo_url}",
                "--input", f"project_name={project_name}",
                "--input", f"project_desc={project_desc}",
                "--input", f"project_url={project_url}",
                "--input", f"review_date={review_date}",
                "--input", f"data_file={data_file}",
                str(TEMPLATE_PATH),
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Typst compilation failed: {result.stderr}")
    finally:
        data_file.unlink(missing_ok=True)

    return output_path
