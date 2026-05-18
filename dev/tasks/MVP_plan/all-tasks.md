# MVP Plan — All Tasks

Generated on: 2026-04-01
Plan source: `dev/plans/MVP_plan.md`

## Task Index (43 tasks, 10 phases)

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P0.1 | 0 | Workspace dependency lock alignment | — | P0.2, P0.4, P0.5 | 9–12 |
| P0.2 | 0 | Core package skeleton completeness | P0.1 | P1.1, P1.2, P2.5, P3.1–P3.5, P4.1–P4.4 | 14–18 |
| P0.3 | 0 | CI workflow baseline | — | P5.3 | 20–24 |
| P0.4 | 0 | Linear solver interface contract | P0.1 | P1.1, P1.2, P7.1 | 26–31 |
| P0.5 | 0 | Tier-1 tensor ops utility | P0.1 | P1.1, P1.2 | 33–36 |
| P1.1 | 1 | Handwritten TL Hex8 elastic reference kernel | P0.2, P0.4, P0.5 | P1.3, P9.2 | 42–46 |
| P1.2 | 1 | Handwritten TL Hex8 J2 plastic reference kernel | P0.2, P0.4, P0.5 | P1.3, P9.2 | 48–52 |
| P1.3 | 1 | Golden artifact serialization fixture | P1.1, P1.2 | P9.2, P9.3 | 54–58 |
| P2.1 | 2 | NRPyLaTeX dependency fork wiring | P0.1 | P2.2, P2.3, P2.4 | 64–68 |
| P2.2 | 2 | Mechanics directive tokenization | P2.1 | P2.3 | 70–74 |
| P2.3 | 2 | Mechanics directive parsing handlers | P2.2 | P2.5 | 76–80 |
| P2.4 | 2 | Two-manifold index typing | P2.1 | P2.5 | 82–86 |
| P2.5 | 2 | Frontend adapter in mechdsl-core | P0.2, P2.3, P2.4 | P4.1 | 88–92 |
| P3.1 | 3 | Kinematics computation module | P0.2 | P3.5, P4.3 | 98–102 |
| P3.2 | 3 | SVK constitutive model | P0.2 | P3.5, P6.3 | 104–108 |
| P3.3 | 3 | J2 power-law symbolic model | P0.2 | P3.5, P8.1 | 110–114 |
| P3.4 | 3 | Voigt/Mandel conversion utilities | P0.2 | P3.5, P4.3 | 116–120 |
| P3.5 | 3 | AD oracle verification module | P3.1, P3.2, P3.3, P3.4 | P9.3 | 122–126 |
| P4.1 | 4 | Mechanics IR schema + validation | P2.5, P0.2 | P4.3, P5.1 | 132–136 |
| P4.2 | 4 | Element IR schema for Hex8 TL | P0.2 | P4.3, P5.1 | 138–142 |
| P4.3 | 4 | FE localization pass | P4.1, P4.2, P3.1, P3.4 | P5.2, P6.2 | 144–148 |
| P4.4 | 4 | Artifact bundle model | P0.2 | P5.2, P6.2 | 150–154 |
| P5.1 | 5 | Einsum optimizer module | P4.1, P4.2 | P5.2, P5.3 | 160–164 |
| P5.2 | 5 | Element IR ↔ optimizer integration | P5.1, P4.3, P4.4 | P6.2 | 166–170 |
| P5.3 | 5 | CI budget regression fixture | P5.1, P0.3 | — | 172–176 |
| P6.1 | 6 | Hex8 static table provider | P0.2 | P6.2, P6.4 | 182–186 |
| P6.2 | 6 | Taichi printer core | P4.3, P4.4, P5.2 | P6.3, P6.4, P6.5 | 188–192 |
| P6.3 | 6 | Elastic constitutive emission | P6.2, P3.2 | P6.4, P9.2 | 194–198 |
| P6.4 | 6 | Internal force kernel emission | P6.1, P6.2, P6.3 | P7.1, P9.2 | 200–204 |
| P6.5 | 6 | Matrix-free tangent matvec emission | P6.2 | P7.1 | 206–210 |
| P7.1 | 7 | Newton-Raphson driver generation | P6.4, P6.5, P0.4 | P7.4, P9.1 | 218–222 |
| P7.2 | 7 | Boundary condition codegen | P0.2 | P7.1, P9.1 | 224–226 |
| P7.3 | 7 | Structured Hex8 mesh I/O | P0.2 | P9.1 | 228–232 |
| P7.4 | 7 | Adaptive load stepping runtime | P7.1 | P9.1 | 234–238 |
| P8.1 | 8 | Plastic constitutive emitter | P3.3, P6.2 | P8.2, P8.4 | 244–248 |
| P8.2 | 8 | Algorithmic tangent emitter | P8.1 | P8.4 | 250–254 |
| P8.3 | 8 | History field lifecycle support | P0.2 | P8.4 | 256–260 |
| P8.4 | 8 | Element kernel switch to elasto-plastic path | P8.1, P8.2, P8.3 | P9.1, P9.3 | 262–266 |
| P9.1 | 9 | Full pipeline e2e test | P7.1, P7.2, P7.3, P7.4, P8.4 | P9.4 | 272–276 |
| P9.2 | 9 | Generated vs handwritten equivalence tests | P1.3, P6.3, P6.4 | P9.4 | 278–280 |
| P9.3 | 9 | Physical benchmark suite hardening | P1.3, P3.5, P8.4 | P9.4 | 282–288 |
| P9.4 | 9 | Compiler-pass coverage closure | P9.1, P9.2, P9.3 | P9.5 | 290–294 |
| P9.5 | 9 | MVP user documentation | P9.4 | — | 296–300 |

## Phase Dependency Summary

```
Phase 0 (Foundation) ──┬──→ Phase 1 (References)  ──────────────→ Phase 8/9 (acceptance)
                       ├──→ Phase 2 (Frontend) ──→ Phase 4 (IR) ──→ Phase 5 (Einsum) ──→ Phase 6 (Codegen)
                       └──→ Phase 3 (Symbolic) ──→ Phase 6 (constitutive) + Phase 8 (plastic)
                                                    Phase 6 + Phase 7 (Solver) ──→ Phase 9 (Integration)
```

## Parallel-safe task groups (within phase)

- **P0:** P0.1 first, then P0.2/P0.3/P0.4/P0.5 in parallel
- **P1:** P1.1 ∥ P1.2, then P1.3
- **P2:** P2.1 first, then P2.2 ∥ P2.4, then P2.3, then P2.5
- **P3:** P3.1 ∥ P3.2 ∥ P3.3 ∥ P3.4, then P3.5
- **P4:** P4.1 ∥ P4.2 ∥ P4.4, then P4.3
- **P5:** P5.1 first, then P5.2 ∥ P5.3
- **P6:** P6.1 early, P6.2 after deps, then P6.3 ∥ P6.5, then P6.4
- **P7:** P7.2 ∥ P7.3 early, P7.1 after P6, then P7.4
- **P8:** P8.1 ∥ P8.3, then P8.2, then P8.4
- **P9:** P9.1 ∥ P9.2 ∥ P9.3, then P9.4, then P9.5
