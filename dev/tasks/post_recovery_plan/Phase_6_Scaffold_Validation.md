# Phase 6 Scaffold Validation

| Task ID | Title | Missing fields | Action |
|---------|-------|----------------|--------|
| P6-1 | Extract `_e2e_helpers.py` | vc/ta empty; cases short | auto-filled |
| P6-2 | Swap helper consumers | vc/ta empty | auto-filled |
| P6-3 | Robustify `test_p7_4.py` notes iteration | vc/ta empty | auto-filled |
| P6-4 | Replace `_INTENTIONAL_CLEANUP_MATCHES` whitelist with marker scan | vc/ta empty | auto-filled |

## Existing Coverage Audit

- `_import_generated_module` defined in 4 files: `test_e2e_taichi.py`, `test_e2e_plastic.py`, `test_explicit_dynamics_acceptance.py`, `recovery_plan_latex_contract/test_p7_2.py`. Plan scope (P6-2) only touches the first and last; `test_e2e_plastic.py` and `test_explicit_dynamics_acceptance.py` keep their copies (not plan scope).
- `test_p7_4.py:92` uses `notes[0]` — confirmed as the fragile pattern.
- `test_phase6_exit.py:38–41` hardcodes `_INTENTIONAL_CLEANUP_MATCHES` with two line numbers (`test_emission_verification.py`, lines 747 + 750).

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 4 |
| Test cases assessed | 12 |
| Stubs generated | 11 |
| Tasks needing review | 0 |

## Execution Order
1. P6-1 (no blockers).
2. P6-2 (blocked by P6-1).
3. P6-3 + P6-4 (no blockers, parallel-eligible).
