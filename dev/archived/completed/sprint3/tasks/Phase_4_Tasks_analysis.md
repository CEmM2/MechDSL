# Phase 4 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|------------------|------------|----------------|------------|--------|
| P4-1 | Create `test_full_pipeline.py` exercising all 6 compiler layers | 4 | 4 | 8 | -- | P4-2 |
| P4-2 | Add nightly e2e schedule to CI | 3 | 3 | 6 | P4-1 | P4-3 |
| P4-3 | Implement failure protocol (benchmark regressions create issues) | 2 | 3 | 5 | P4-2 | -- |

## Model Assignment Notes

- Skill-requested Opus/Sonnet tiers are not available in this environment, so the strongest available model `gpt-5.4` is assigned to the high-score implementation/review path for `P4-1`.
- Lower-risk follow-on tasks `P4-2` and `P4-3` can use `gpt-5.4-mini` if delegated, but the execution order remains sequential because of task blockers.
