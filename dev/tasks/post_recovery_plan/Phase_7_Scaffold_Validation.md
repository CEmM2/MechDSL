# Phase 7 Scaffold Validation

| Task | Title | Action |
|------|-------|--------|
| P7-1 | Restore `## Inventory` anchor in dev/examples/README.md | auto-filled |
| P7-2 | Robustify test_p7_3.py ordering check + path matching | auto-filled |
| P7-3 | Rename gen_p7_2 module-name + remove obsolete comment | auto-filled |
| P7-4 | Trim test_p7_6.py to [100, 250] lines | auto-filled (test_p7_6.py currently 193 lines — already in range; trim is best-effort merge of redundant sub-bullets) |
| P7-5 | Clarify _SUPERSEDED.md runtime-active vs archived | auto-filled |
| P7-6 | Refresh GitNexus index | auto-filled (.gitnexus/meta.json absent — test skips with auth-required note) |
| P7-7 | Add CI baseline-stability smoke job | auto-filled |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 14 |
| Stubs generated | 16 |
| Tasks needing review | 0 |

## Existing Coverage Audit

- `## Inventory` not present in `dev/examples/README.md` — P7-1 must add.
- `test_p7_3.py:53-55` uses `text.find()` directly (P7-2 fix target).
- `test_p7_2.py:135` hardcodes `name="gen_p7_2"` (P7-3 fix target).
- `test_p7_6.py` is 193 lines — within [100, 250]. P7-4 verifies + best-effort merge.
- `dev/tasks/PLAN-B/_SUPERSEDED.md` exists but no runtime-active/archived sub-section yet (P7-5 target).
- `.gitnexus/meta.json` does not exist. GitNexus index uninitialised. P7-6 task documents the refresh command but defers execution to user authorisation.
- `.github/workflows/` has `ci.yml`, `ci-backends.yml`, `nightly.yml` — no baseline-stability job (P7-7 target).

## Execution Order

All P7 tasks parallel-eligible (only P7-3 lists `blocked_by=[P1-6]`, but P1 already merged). Run all in sequence main-thread.
