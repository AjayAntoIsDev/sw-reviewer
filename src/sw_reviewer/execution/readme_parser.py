"""Extract install/run commands and flow steps from README text."""

import re
from typing import List, Optional, Tuple


# Regex patterns for extracting shell commands from markdown code blocks
_CODE_BLOCK_PATTERN = re.compile(r"```(?:bash|sh|shell|console|zsh)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_INLINE_CODE_PATTERN = re.compile(r"`([^`\n]{3,80})`")
_SECTION_HEADER_PATTERN = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def extract_shell_commands(readme_text: str) -> List[str]:
    """
    Extract shell commands from README markdown code blocks and inline code.
    
    Returns a list of command strings (deduplicated, in order of appearance).
    """
    commands: List[str] = []
    seen: set = set()

    # Prefer fenced code blocks first
    for match in _CODE_BLOCK_PATTERN.finditer(readme_text):
        block = match.group(1)
        for line in block.splitlines():
            line = line.strip()
            # Filter out comments and empty lines
            if line and not line.startswith("#") and not line.startswith("//"):
                # Skip lines that look like output (no command-like prefix patterns)
                if _looks_like_command(line) and line not in seen:
                    commands.append(line)
                    seen.add(line)

    # Fall back to inline code if no block commands found
    if not commands:
        for match in _INLINE_CODE_PATTERN.finditer(readme_text):
            cmd = match.group(1).strip()
            if _looks_like_command(cmd) and cmd not in seen:
                commands.append(cmd)
                seen.add(cmd)

    return commands


def _looks_like_command(line: str) -> bool:
    """Heuristic: does this line look like a shell command?"""
    command_starters = (
        "pip", "python", "npm", "npx", "node", "yarn", "pnpm",
        "cargo", "rustup", "go", "docker", "kubectl",
        "make", "cmake", "gcc", "g++", "clang",
        "brew", "apt", "apt-get", "yum", "dnf", "pacman",
        "git", "curl", "wget", "chmod", "export",
        "./", "/", "~",
    )
    lower = line.lower().lstrip()
    return any(lower.startswith(prefix) for prefix in command_starters)


def extract_web_flows(readme_text: str) -> List[str]:
    """
    Extract named web flows / features from README sections.
    
    Returns a list of feature/flow names inferred from headings and bullet lists.
    """
    flows: List[str] = []
    sections = _SECTION_HEADER_PATTERN.findall(readme_text)
    
    FEATURE_KEYWORDS = {"feature", "flow", "demo", "usage", "how to", "tutorial", "walk", "guide", "example"}
    for section in sections:
        lower = section.lower()
        if any(kw in lower for kw in FEATURE_KEYWORDS):
            flows.append(section.strip())

    # Also grab bullet point items under feature-like headings (simple heuristic)
    bullet_pattern = re.compile(r"^\s*[-*+]\s+(.{5,80})$", re.MULTILINE)
    for match in bullet_pattern.finditer(readme_text):
        item = match.group(1).strip()
        if len(item) > 10:
            flows.append(item)

    return flows[:20]  # Cap at 20 flows for MVP


def categorise_commands(commands: List[str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Categorise a list of shell commands into install, build, and run phases.
    
    Returns: (install_cmds, build_cmds, run_cmds)
    """
    install_cmds: List[str] = []
    build_cmds: List[str] = []
    run_cmds: List[str] = []

    INSTALL_KEYWORDS = ("pip install", "npm install", "yarn install", "pnpm install", "cargo build", "go install", "apt install", "brew install", "apt-get install")
    BUILD_KEYWORDS = ("npm run build", "cargo build", "make", "cmake", "go build", "tsc", "webpack")
    RUN_KEYWORDS = ("python ", "node ", "npm start", "cargo run", "./", "uvicorn", "gunicorn", "flask", "django", "npm run dev", "npm run start")

    for cmd in commands:
        lower = cmd.lower()
        if any(kw in lower for kw in INSTALL_KEYWORDS):
            install_cmds.append(cmd)
        elif any(kw in lower for kw in BUILD_KEYWORDS):
            build_cmds.append(cmd)
        elif any(kw in lower for kw in RUN_KEYWORDS):
            run_cmds.append(cmd)
        else:
            run_cmds.append(cmd)  # Default to run phase

    return install_cmds, build_cmds, run_cmds
