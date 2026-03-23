# Changes T11–T13: CLI Sandbox

- Created `src/sw_reviewer/execution/cli.py`: `CLISandboxRunner` with Docker isolation, secret redaction, evidence capture.
- Created `src/sw_reviewer/execution/readme_parser.py`: `extract_shell_commands()`, `extract_web_flows()`, `categorise_commands()`.
- Created `tests/test_orchestrator.py` (covers CLI pipeline end-to-end).
- Updated `AI/MASTER_TODO.md` T11–T13 to DONE.
