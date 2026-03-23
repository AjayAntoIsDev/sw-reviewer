# Shipwright Guidelines (Normalized for Automation)

This file translates policy into machine-checkable categories.

## Core acceptance logic (highest priority)

Approve/reject should primarily answer:

1. README is sufficient.
2. Project is open source.
3. Project works end-to-end.

## Universal requirements

- Repo must be public and open source.
- README must explain purpose and usage.
- README depth scales with project complexity (simple sites can be lighter; CLI/docs-heavy projects require detailed install + usage).
- Description should be in English.
- Reviewer proof video must include: repo view, README review, download/setup, and feature testing.

## Explicit rejection conditions

- Shared/special review account is required instead of user creating their own account.
- Project was submitted to another competition/game jam (per provided rule).
- Web app has no valid live demo (local-only instructions, ngrok/cloudflared/duckdns are invalid; Render links currently invalid per guideline).
- AI/ML project hosted only on Hugging Face (per provided rule).

## Project-type checks

### Web apps

- Live demo required on accepted host.
- All visible functionality should work.
- For auth projects: test at least one OAuth option (if present) and standard sign-up/sign-in flow.

### CLI tools

- Must provide executable/binary distribution and clear setup/usage instructions.
- Commands/features should work as documented.

### Executables / desktop / mobile / games / bots / libraries / extensions / userscripts / hardware / esolangs / mods

- Keep as policy references for future scope expansion.
- Initial implementation focus is **web apps + CLI tools**.

## AI declaration

- Include AI declaration checks as metadata check if program requirements demand it.
- Do not reject solely on “vibe coded” or AI-assisted development if core acceptance logic passes.

## Reviewer output standard

Every review must output:

- Final verdict: `approve` / `reject` / `needs-human-review`
- Rule-by-rule checklist
- Evidence links (logs/screenshots/artifacts)
- Reasoning summary
- Suggested feedback for submitter
