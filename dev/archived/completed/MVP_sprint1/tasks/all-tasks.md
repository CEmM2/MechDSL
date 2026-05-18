# MVP Sprint 1 — Task Index

Plan source: `.claude/plans/serialized-booping-quokka.md`
Original spec: `dev/plans/MVP_sprint1.md`

## Task Table

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-T1 | 1 | Implement ConstitutiveModel ABC | — | P1-T2, P1-T3 | 17–38 |
| P1-T2 | 1 | Add SVKModel wrapper class | P1-T1 | P1-T4, P1-T5 | 42–46 |
| P1-T3 | 1 | Add J2Model wrapper class | P1-T1 | P1-T4, P1-T5 | 48–53 |
| P1-T4 | 1 | Update fe_localise model validation | P1-T2, P1-T3 | — | 55–59 |
| P1-T5 | 1 | Write constitutive ABC tests | P1-T2, P1-T3 | — | 61–68 |
| P2-T1 | 2 | Implement extract_einsum_specs() | — | P2-T2 | 77–89 |
| P2-T2 | 2 | Refactor fe_localise + update exports | P2-T1 | P2-T3, P4-T1 | 91–101 |
| P2-T3 | 2 | Write einsum extraction tests | P2-T2 | — | 104–112 |
| P3-T1 | 3 | Implement newton_solve() with config, BC enforcement, history, exports | — | P3-T2, P3-T3 | 120–184 |
| P3-T2 | 3 | Newton driver unit tests | P3-T1 | P6-T1 | 188–191 |
| P3-T3 | 3 | Newton + load_stepping integration test | P3-T1 | P6-T1 | 192–193 |
| P4-T1 | 4 | Implement compile() function and top-level export | P2-T2 | P4-T2 | 201–226 |
| P4-T2 | 4 | Write compile pipeline tests | P4-T1 | P5-T1 | 228–234 |
| P5-T1 | 5 | Rename emit stub + add emit_postprocess() | P4-T2 | P5-T2 | 242–264 |
| P5-T2 | 5 | Add emit_main() function | P5-T1 | P5-T3 | 249–257 |
| P5-T3 | 5 | Update emit() chain, regenerate golden files, add tests | P5-T2 | P6-T1 | 267–284 |
| P6-T1 | 6 | Create E2E Taichi smoke test | P3-T2, P3-T3, P5-T3 | P6-T2 | 292–313 |
| P6-T2 | 6 | CI integration for slow tests | P6-T1 | — | 315–318 |

## Phase Dependency Graph

```
Phase 1 (ABC)  ──────────┐
                          ├──→ Phase 4 (compile)  ──→ Phase 5 (printer) ──→ Phase 6 (E2E)
Phase 2 (einsum extract) ─┘
Phase 3 (newton.py)  ─────────────────────────────────────────────────────→ Phase 6 (E2E)
```

Phases 1, 2, 3 are parallelisable. Phase 4 gates on Phase 2. Phase 5 gates on Phase 4. Phase 6 gates on Phases 3 + 5.
