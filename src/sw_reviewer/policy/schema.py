"""Policy schema definitions for the Shipwright review pipeline."""

from typing import List
from ..models import PolicyCheck, PolicyLevel

# ── Baseline rules for MVP ─────────────────────────────────────────────────

POLICY_RULES: List[PolicyCheck] = [
    PolicyCheck(
        id="repo_url_present",
        category="docs",
        level=PolicyLevel.REQUIRED,
        description="Repository URL must be present and non-empty.",
    ),
    PolicyCheck(
        id="project_type_supported",
        category="docs",
        level=PolicyLevel.REQUIRED,
        description="Project type must be 'web' or 'cli'.",
    ),
    PolicyCheck(
        id="readme_sufficient",
        category="docs",
        level=PolicyLevel.REQUIRED,
        description="README must explain purpose and basic usage (heuristic: ≥150 chars, contains usage/install keywords).",
    ),
    PolicyCheck(
        id="open_source_heuristic",
        category="licensing",
        level=PolicyLevel.ADVISORY,
        description="Repository should be public and open-source (heuristic based on URL).",
    ),
    PolicyCheck(
        id="web_demo_url_present",
        category="web",
        level=PolicyLevel.REQUIRED,
        description="Web projects must have a live demo URL on an accepted hosting platform.",
    ),
    PolicyCheck(
        id="web_demo_host_allowed",
        category="web",
        level=PolicyLevel.REQUIRED,
        description="Demo URL must not use local/tunnel hosts (localhost, ngrok, cloudflared, duckdns, render.com are invalid).",
    ),
    PolicyCheck(
        id="cli_commands_present",
        category="cli",
        level=PolicyLevel.REQUIRED,
        description="CLI projects must provide documented commands or command hints.",
    ),
    PolicyCheck(
        id="execution_success",
        category="execution",
        level=PolicyLevel.REQUIRED,
        description="At least one primary flow or command must complete successfully.",
    ),
    PolicyCheck(
        id="no_special_review_account",
        category="security",
        level=PolicyLevel.REQUIRED,
        description="Project must not require a shared special review account.",
    ),
    PolicyCheck(
        id="not_previously_submitted",
        category="compliance",
        level=PolicyLevel.MANUAL_ONLY,
        description="Project must not have been submitted to another competition (manual confirmation required).",
    ),
]

POLICY_RULE_MAP = {rule.id: rule for rule in POLICY_RULES}
