| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|------------------|------------|----------------|------------|--------|
| P6-1 | Ruff lint and format pass | 1 | 2 | 3 | -- | P6-3 |
| P6-2 | Mypy type checking pass | 2 | 3 | 5 | -- | P6-3 |
| P6-3 | Full test suite zero failures | 3 | 4 | 7 | P6-1, P6-2 | P6-6 |
| P6-4 | JIT budget compliance check | 1 | 2 | 3 | -- | P6-6 |
| P6-5 | Remove dead code, unused imports, resolved TODOs | 2 | 3 | 5 | -- | P6-6 |
| P6-6 | Verify all Sprint 3 exit criteria | 3 | 4 | 7 | P6-3, P6-4, P6-5 | P6-7 |
| P6-7 | Sprint 3 handoff document | 2 | 2 | 4 | P6-6 | -- |

Model assignment from the skill rules:
- P6-1, P6-2, P6-4, P6-5 fit Sonnet-class execution if delegated.
- P6-3 and P6-6 exceed the combined-score threshold of 6 and require Opus-class execution if delegated.
- P6-7 fits Sonnet-class execution if delegated.
