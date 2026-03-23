# T14–T15 Summary: Policy Engine + Verdict

**Tasks**: T14 (policy check engine), T15 (verdict engine)

Implemented the policy evaluation engine in `src/sw_reviewer/policy/`.
- `schema.py`: 10 `PolicyRule` instances covering docs, licensing, web, CLI, execution, security, and compliance.
- `rules.py`: heuristic rule evaluation functions, each returning `(passed: bool, reasoning: str)`.
  - Blocked demo hosts: localhost, ngrok, cloudflared, duckdns, render.com.
  - README sufficiency: ≥150 chars + usage/install keyword check.
  - Open-source heuristic: URL hostname validation via `urlparse` (secure, no substring matching).
- `evaluator.py`: `evaluate_policies()` applies rules per project type; `generate_verdict()` applies decision logic:
  - REJECT if any REQUIRED check fails
  - NEEDS_HUMAN_REVIEW if MANUAL_ONLY checks are unconfirmed
  - APPROVE otherwise (ADVISORY failures noted but non-blocking)
- 15 tests in `tests/test_policy_engine.py`, all passing.
