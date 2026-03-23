# T11–T13 Summary: CLI Sandbox Runner

**Tasks**: T11 (Docker sandbox), T12 (README command extraction + phases), T13 (evidence capture)

Implemented a Docker-based CLI sandbox runner in `src/sw_reviewer/execution/cli.py`.
- `CLISandboxRunner` executes commands inside an ephemeral Docker container with:
  - `--rm`, `--memory 512m`, `--cpus 1`, `--user nobody`, `--read-only`, `--tmpfs /tmp`
  - Per-command and per-job timeouts
  - Graceful fallback to subprocess when Docker is unavailable
- Secret redaction applied to all stdout/stderr output before storage.
- Output truncated at 64 KB per command to prevent memory abuse.
- `CommandPhase` groups commands into `install`, `build`, `smoke/run` phases.
- `to_cli_results_with_evidence()` saves stdout/stderr to artifact files and builds `EvidenceItem` references.
- README parser (`readme_parser.py`) extracts shell commands from fenced code blocks and categorises them.
