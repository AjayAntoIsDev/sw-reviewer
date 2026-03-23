"""
CLI sandbox runner using Docker for isolated command execution.
Implements T11 (sandbox), T12 (command phases), T13 (evidence capture).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models import CLICommandResult, EvidenceItem

logger = logging.getLogger(__name__)

# ── Secret redaction ────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(ghp_[A-Za-z0-9]{36,})", re.IGNORECASE),
    re.compile(r"(AKIA[0-9A-Z]{16})", re.IGNORECASE),
    re.compile(r"(xox[baprs]-[A-Za-z0-9-]{10,})", re.IGNORECASE),  # Slack tokens
]
MAX_OUTPUT_BYTES = 1024 * 64  # 64 KB per command output


def redact_secrets(text: str) -> str:
    """Replace likely secret patterns with [REDACTED]."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class CommandPhase:
    """A named phase containing shell commands to execute."""
    name: str  # "install", "build", "run", "smoke"
    commands: List[str]


@dataclass
class RawCommandResult:
    """Raw result from a single executed command."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    success: bool
    timed_out: bool = False


# ── Docker runner ─────────────────────────────────────────────────────────────

class CLISandboxRunner:
    """
    Runs CLI commands in an ephemeral Docker container with resource limits.
    Falls back to direct subprocess execution when Docker is unavailable.
    """

    def __init__(
        self,
        docker_enabled: bool = True,
        docker_image: str = "python:3.12-slim",
        timeout_seconds: int = 120,
        artifacts_dir: str = "artifacts",
    ):
        self.docker_enabled = docker_enabled
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds
        self.artifacts_dir = Path(artifacts_dir)

    async def _docker_available(self) -> bool:
        """Check if Docker is available on the host."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    async def run_command(
        self,
        command: str,
        repo_path: Optional[str] = None,
        use_docker: Optional[bool] = None,
    ) -> RawCommandResult:
        """
        Run a single shell command with a timeout, capturing stdout/stderr.
        
        If Docker is enabled and available, runs inside a container.
        Otherwise, falls back to subprocess.
        """
        if use_docker is None:
            use_docker = self.docker_enabled

        if use_docker and await self._docker_available():
            result = await self._run_in_docker(command, repo_path)
        else:
            result = await self._run_subprocess(command, repo_path)

        return result

    async def _run_in_docker(
        self,
        command: str,
        repo_path: Optional[str] = None,
    ) -> RawCommandResult:
        """Run command inside an ephemeral Docker container."""
        start = time.monotonic()
        timed_out = False

        docker_cmd = [
            "docker", "run",
            "--rm",                          # Remove container after exit
            "--network", "host",             # Allow network (restricted per policy)
            "--memory", "512m",
            "--cpus", "1",
            "--user", "nobody",
            "--read-only",
            "--tmpfs", "/tmp",
        ]

        if repo_path:
            docker_cmd.extend(["-v", f"{repo_path}:/workspace:ro", "-w", "/workspace"])

        docker_cmd.extend([self.docker_image, "sh", "-c", command])

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                timed_out = True
                stdout_bytes, stderr_bytes = b"", b"[TIMEOUT]".encode()

            exit_code = proc.returncode or 1
        except Exception as exc:
            logger.error("Docker execution failed for command '%s': %s", command, exc)
            duration_ms = int((time.monotonic() - start) * 1000)
            return RawCommandResult(
                command=command, exit_code=1,
                stdout="", stderr=str(exc),
                duration_ms=duration_ms, success=False,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        stdout = redact_secrets(stdout_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"))
        stderr = redact_secrets(stderr_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"))
        success = exit_code == 0 and not timed_out
        return RawCommandResult(
            command=command, exit_code=exit_code,
            stdout=stdout, stderr=stderr,
            duration_ms=duration_ms, success=success,
            timed_out=timed_out,
        )

    async def _run_subprocess(
        self,
        command: str,
        cwd: Optional[str] = None,
    ) -> RawCommandResult:
        """Run command directly via subprocess (no Docker isolation)."""
        start = time.monotonic()
        timed_out = False

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                timed_out = True
                stdout_bytes, stderr_bytes = b"", b"[TIMEOUT]".encode()

            exit_code = proc.returncode or 1
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return RawCommandResult(
                command=command, exit_code=1,
                stdout="", stderr=str(exc),
                duration_ms=duration_ms, success=False,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        stdout = redact_secrets(stdout_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"))
        stderr = redact_secrets(stderr_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"))
        success = exit_code == 0 and not timed_out
        return RawCommandResult(
            command=command, exit_code=exit_code,
            stdout=stdout, stderr=stderr,
            duration_ms=duration_ms, success=success,
            timed_out=timed_out,
        )

    async def run_phases(
        self,
        review_id: str,
        phases: List[CommandPhase],
        repo_path: Optional[str] = None,
    ) -> List[RawCommandResult]:
        """
        Execute command phases sequentially, stopping on required-phase failure.
        Returns all results for evidence capture.
        """
        all_results: List[RawCommandResult] = []
        for phase in phases:
            logger.info("Running CLI phase '%s' for review %s", phase.name, review_id)
            for cmd in phase.commands:
                result = await self.run_command(cmd, repo_path=repo_path)
                all_results.append(result)
                if not result.success and phase.name in ("install", "build"):
                    logger.warning(
                        "Required phase '%s' failed at command '%s'; aborting further phases.",
                        phase.name, cmd,
                    )
                    return all_results
        return all_results

    def to_cli_results_with_evidence(
        self,
        raw_results: List[RawCommandResult],
        review_id: str,
    ) -> Tuple[List[CLICommandResult], List[EvidenceItem]]:
        """
        Convert raw command results into typed CLICommandResult + EvidenceItem pairs.
        Saves stdout/stderr to artifact files and creates evidence references.
        """
        artifacts_dir = self.artifacts_dir / review_id / "cli"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        cli_results: List[CLICommandResult] = []
        evidence_items: List[EvidenceItem] = []

        for idx, raw in enumerate(raw_results):
            safe_cmd = re.sub(r"[^\w]", "_", raw.command[:40])
            stdout_path = artifacts_dir / f"cmd_{idx:02d}_{safe_cmd}_stdout.txt"
            stderr_path = artifacts_dir / f"cmd_{idx:02d}_{safe_cmd}_stderr.txt"

            stdout_path.write_text(raw.stdout, encoding="utf-8")
            stderr_path.write_text(raw.stderr, encoding="utf-8")

            stdout_ev_id = f"cli_stdout_{idx}"
            stderr_ev_id = f"cli_stderr_{idx}"

            evidence_items.append(EvidenceItem(
                id=stdout_ev_id,
                type="cli_stdout",
                source_stage="cli",
                payload={"path": str(stdout_path), "command": raw.command},
            ))
            evidence_items.append(EvidenceItem(
                id=stderr_ev_id,
                type="cli_stderr",
                source_stage="cli",
                payload={"path": str(stderr_path), "command": raw.command},
            ))

            cli_results.append(CLICommandResult(
                command=raw.command,
                exit_code=raw.exit_code,
                stdout_ref=stdout_ev_id,
                stderr_ref=stderr_ev_id,
                duration_ms=raw.duration_ms,
                success=raw.success,
            ))

        return cli_results, evidence_items
