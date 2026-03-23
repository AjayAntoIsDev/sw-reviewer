"""Individual policy rule evaluation functions."""

import re
from typing import Tuple, Optional, List

# Domains not allowed for web demo
BLOCKED_DEMO_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0",
    "ngrok.io", "ngrok-free.app", "cloudflared.net",
    "duckdns.org", "render.com",
}

# Minimum README length heuristic
README_MIN_CHARS = 150
README_USAGE_KEYWORDS = {
    "install", "usage", "use", "run", "setup",
    "quick start", "getting started", "how to",
}


def check_repo_url_present(repo_url: Optional[str]) -> Tuple[bool, str]:
    if repo_url and repo_url.strip():
        return True, "Repository URL is present."
    return False, "Repository URL is missing or empty."


def check_project_type_supported(project_type: Optional[str]) -> Tuple[bool, str]:
    if project_type and project_type.lower() in ("web", "cli"):
        return True, f"Project type '{project_type}' is supported."
    return False, f"Project type '{project_type}' is not supported. Must be 'web' or 'cli'."


def check_readme_sufficient(readme_text: Optional[str]) -> Tuple[bool, str]:
    if not readme_text:
        return False, "README text is absent."
    text = readme_text.strip()
    if len(text) < README_MIN_CHARS:
        return False, f"README is too short ({len(text)} chars, minimum {README_MIN_CHARS})."
    lower = text.lower()
    matched = [kw for kw in README_USAGE_KEYWORDS if kw in lower]
    if not matched:
        return False, "README does not contain usage/install keywords."
    return True, f"README is sufficient ({len(text)} chars, keywords: {matched})."


def check_open_source_heuristic(repo_url: Optional[str]) -> Tuple[bool, str]:
    if not repo_url:
        return False, "No repository URL to evaluate."
    url = repo_url.lower()
    if (
        "github.com" in url
        or "gitlab.com" in url
        or "codeberg.org" in url
        or "sourcehut.org" in url
    ):
        return True, "Repository appears to be on a public hosting platform."
    return False, "Repository URL does not appear to be on a standard public platform."


def check_web_demo_url_present(demo_url: Optional[str]) -> Tuple[bool, str]:
    if demo_url and demo_url.strip().startswith(("http://", "https://")):
        return True, "Demo URL is present."
    return False, "Demo URL is missing or not a valid HTTP URL."


def check_web_demo_host_allowed(demo_url: Optional[str]) -> Tuple[bool, str]:
    if not demo_url:
        return False, "Demo URL is missing."
    match = re.match(r"https?://([^/?\s]+)", demo_url.lower())
    if not match:
        return False, "Could not parse hostname from demo URL."
    host = match.group(1).split(":")[0]
    for blocked in BLOCKED_DEMO_HOSTS:
        if host == blocked or host.endswith("." + blocked):
            return False, f"Demo host '{host}' is not allowed (blocked: {blocked})."
    return True, f"Demo host '{host}' passes the allowed-host check."


def check_cli_commands_present(commands: Optional[List[str]]) -> Tuple[bool, str]:
    if commands and len(commands) > 0:
        return True, f"{len(commands)} CLI command(s) documented."
    return False, "No CLI commands or command hints provided."


def check_execution_success(any_success: bool) -> Tuple[bool, str]:
    if any_success:
        return True, "At least one primary flow or command completed successfully."
    return False, "No primary flow or command completed successfully."


def check_no_special_review_account(metadata: Optional[dict]) -> Tuple[bool, str]:
    """Heuristic: look for 'special' or 'review account' indicators in metadata."""
    if metadata:
        notes = (
            str(metadata.get("notes", "")).lower()
            + str(metadata.get("auth_instructions", "")).lower()
        )
        if "special" in notes and "account" in notes:
            return False, "Metadata suggests a special review account may be required."
    return True, "No indication of a required special review account."
