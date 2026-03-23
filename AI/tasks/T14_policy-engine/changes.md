# Changes T14–T15: Policy Engine + Verdict

- Created `src/sw_reviewer/policy/__init__.py`.
- Created `src/sw_reviewer/policy/schema.py`: 10 policy rules.
- Created `src/sw_reviewer/policy/rules.py`: heuristic rule functions with urlparse-based host validation.
- Created `src/sw_reviewer/policy/evaluator.py`: `evaluate_policies()` + `generate_verdict()`.
- Created `tests/test_policy_engine.py`: 15 unit + integration tests.
- Updated `AI/MASTER_TODO.md` T14–T15 to DONE.
