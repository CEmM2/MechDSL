# Phase 3 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|:-:|:-:|:-:|------------|--------|
| R3.3.1 | Add `__post_init__` to J2PowerLawMaterial | 1 | 1 | 2 | — | R3.5.1, R3.5.3 |
| R3.3.2 | Freeze ReturnMappingResult + comments | 1 | 2 | 3 | — | — |
| R3.3.3 | Add `__post_init__` to SVKMaterial + from_E_nu | 1 | 1 | 2 | — | R3.5.3 |
| R3.3.4 | Add `__post_init__` to HexMesh | 1 | 1 | 2 | — | R3.5.3 |
| R3.3.5 | Add `__post_init__` to QuadratureRule | 1 | 1 | 2 | — | R3.5.3 |
| R3.3.6 | Add `__post_init__` to DirichletBC/NeumannBC | 1 | 1 | 2 | — | R3.5.3 |
| R3.3.7 | HistoryFields error messages + duplicate guard | 1 | 1 | 2 | — | — |

All tasks: complexity ≤ 3, risk ≤ 3, unblocked. All modify different files. Dispatch all 7 in parallel.
