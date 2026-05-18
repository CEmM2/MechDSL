# PR #3 Review Resolution — All Tasks

Generated on: 2026-04-02
Plan source: `dev/plans/mvp_pr3_round3.md`

## Task Index (29 tasks, 6 phases)

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| R3.1.1 | 1 | Fix J2 Newton `ti.static` → runtime (C1) | — | R3.6.1 | 15–20 |
| R3.1.2 | 1 | Fix quadrature loop to `ti.static` for Python list access (C2) | — | R3.1.5, R3.6.1 | 22–31 |
| R3.1.3 | 1 | Emit `raise RuntimeError` on Newton non-convergence (C4) | — | R3.6.1 | 33–50 |
| R3.1.4 | 1 | Add NaN/Inf guard in emitted Newton driver (C4b) | R3.1.8 | R3.6.1 | 52–61 |
| R3.1.5 | 1 | Change node loops to runtime (C5) | R3.1.2 | R3.6.1 | 63–73 |
| R3.1.6 | 1 | Add material model validation in `emit()` (H9) | — | R3.6.1 | 75–86 |
| R3.1.7 | 1 | Add emitted J2 convergence check after Newton loop (H1) | — | R3.1.4, R3.6.1 | 88–97 |
| R3.1.8 | 1 | Add emitted J2 negative delta_lambda guard (H2) | R3.1.7 | R3.1.4, R3.6.1 | 99–103 |
| R3.1.9 | 1 | Fix comments CM3, CM4, CM5, CM7 in taichi_printer | — | R3.6.1 | 105–109 |
| R3.1.10 | 1 | Update convention docs for C2 carve-out | R3.1.2 | — | 113–116 |
| R3.2.1 | 2 | Add CG/PCG breakdown warning (C3) | — | — | 122–140 |
| R3.2.2 | 2 | Fix J2 radial_return stall guard (H3) | — | R3.5.1, R3.5.2 | 142–156 |
| R3.2.3 | 2 | Add emitted CG failure counter (H4) | — | R3.6.1 | 158–179 |
| R3.2.4 | 2 | Fix einsum FLOPS fallback to sentinel (H5) | — | — | 181–193 |
| R3.2.5 | 2 | Add Newton non-convergence to ref elastic solver (H6) | — | R3.6.1 | 195–204 |
| R3.2.6 | 2 | Add boundary codegen zero-area and axis guards (H7+H8) | — | R3.5.4 | 206–233 |
| R3.3.1 | 3 | Add `__post_init__` to J2PowerLawMaterial | — | R3.5.1, R3.5.3 | 239–254 |
| R3.3.2 | 3 | Freeze ReturnMappingResult + fix comments (H11, H12, H13) | — | — | 256–261 |
| R3.3.3 | 3 | Add `__post_init__` to SVKMaterial + `from_E_nu` validation | — | R3.5.3 | 263–277 |
| R3.3.4 | 3 | Add `__post_init__` to HexMesh | — | R3.5.3 | 279–296 |
| R3.3.5 | 3 | Add `__post_init__` to QuadratureRule | — | R3.5.3 | 298–311 |
| R3.3.6 | 3 | Add `__post_init__` to DirichletBC/NeumannBC | — | R3.5.3 | 313–330 |
| R3.3.7 | 3 | Improve HistoryFields error messages + duplicate guard | — | — | 332–353 |
| R3.4.1 | 4 | Fix CI `uv sync` flags (H10) | — | — | 359–364 |
| R3.5.1 | 5 | Add tests T1-T2: radial_return error paths | R3.2.2, R3.3.1 | — | 370–409 |
| R3.5.2 | 5 | Add tests T3-T4: degenerate element + invalid face | R3.2.6 | — | 411–433 |
| R3.5.3 | 5 | Add tests T5: `__post_init__` validation tests | R3.3.1–R3.3.6 | — | 435–440 |
| R3.5.4 | 5 | Tighten test tolerances (G1, G4) + ref solver Dirichlet fix (G3) | R3.2.5 | R3.6.1 | 442–454 |
| R3.6.1 | 6 | Regenerate golden files + full verification | R3.1.1–R3.1.9, R3.2.3, R3.2.5, R3.5.4 | — | 458–483 |
