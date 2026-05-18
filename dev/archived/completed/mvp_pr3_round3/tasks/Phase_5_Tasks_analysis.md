# Phase 5 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|:-:|:-:|:-:|------------|--------|
| R3.5.1 | T1-T2: radial_return error paths | 2 | 2 | 4 | R3.2.2, R3.3.1 (done) | — |
| R3.5.2 | T3-T4: degenerate element + invalid face | 1 | 1 | 2 | R3.2.6 (done) | — |
| R3.5.3 | T5: __post_init__ validation tests | 2 | 1 | 3 | R3.3.1-R3.3.6 (done) | — |
| R3.5.4 | G1/G4/G3: tolerances + Dirichlet fix | 2 | 3 | 5 | R3.2.5 (done) | R3.6.1 |

All blockers resolved. R3.5.1-R3.5.3 are complexity ≤ 3 and risk ≤ 3 — dispatch in parallel.
R3.5.4 has risk=3 (Dirichlet functional change) — implement after verifying R3.5.1-R3.5.3.
