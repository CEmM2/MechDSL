# Post-Recovery Plan — All Tasks

Plan source: `dev/plans/post_recovery_plan.md`
Generated: 2026-04-30

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-1 | 1 | Extend `BoundaryCondition` IR slot (traction vector + surface tag) | — | P1-2, P1-3 | 91-92, 113-115 |
| P1-2 | 1 | Extend Neumann directive parser to capture traction + surface set | P1-1 | P1-3 | 88-90 |
| P1-3 | 1 | Lower Neumann BC to per-node force contributions on tagged surface | P1-1, P1-2 | P1-4 | 92-94 |
| P1-4 | 1 | Emit `f_ext` init Taichi kernel from lowered Neumann BC | P1-3 | P1-5, P1-7 | 94-96 |
| P1-5 | 1 | Extend `compile_latex` façade to surface emitted `f_ext` kernel | P1-4 | P1-6, P3-1 | 96-98, 116-117 |
| P1-6 | 1 | Replace numeric `f_ext` injection in `test_p7_2.py:142-144` with directive-only path | P1-5 | — | 98-100, 109-111 |
| P1-7 | 1 | New golden test `test_boundary_neumann.py` for emitted `f_ext` kernel | P1-4 | — | 100-102, 109-111 |
| P2-1 | 2 | Register `docs` pytest marker (`pyproject.toml` + `.claude/rules/tests.md`) | — | P2-2, P2-3 | 128-131 |
| P2-2 | 2 | Swap `@pytest.mark.integration` → `@pytest.mark.docs` in `test_p7_3..6.py` | P2-1 | P2-3 | 131-135 |
| P2-3 | 2 | Audit and update CI workflow `tier:docs` selector | P2-1 | — | 135-138 |
| P3-1 | 3 | Add BC handoff paragraph to `compile_latex` docstring | P1-5 | P3-2 | 165-168 |
| P3-2 | 3 | New docstring-presence test `test_compile_latex_docstring.py` | P3-1 | — | 168-171 |
| P4-1 | 4 | New `frontend/math_parser.py` wrapping `nrpylatex` | — | P4-3 | 195-199 |
| P4-2 | 4 | `symbolic/bridge.py` adapter — nrpylatex AST → mechdsl symbolic | — | P4-3 | 200-202 |
| P4-3 | 4 | Wire math parser into `frontend/__init__.py` pipeline | P4-1, P4-2 | P4-4, P4-5 | 199-200 |
| P4-4 | 4 | New `test_nrpylatex_round_trip.py` (SVK PK1, J2 yield, two-point tensor) | P4-3 | — | 203-206 |
| P4-5 | 4 | Add `dev/examples/svk_latex_math.tex` + README inventory entry | P4-3 | — | 206-208 |
| P5-1 | 5 | Author `dev/algorithms/radial_return_j2.tex` algpseudocode source | — | P5-2 | 237-239 |
| P5-2 | 5 | New `packages/algo2code/tests/test_radial_return_codegen.py` | P5-1 | P5-3 | 239-242 |
| P5-3 | 5 | Switch `lib/plasticity.py` default to algo2code path; feature-flag fallback | P5-2 | P5-4, P5-5 | 242-246 |
| P5-4 | 5 | New `test_j2_radial_return_parity.py` (imported vs algo2code parity) | P5-3 | — | 246-250 |
| P5-5 | 5 | Add design-doc note to `06-PLASTICITY.md` or `07-CONVENTIONS.md` | P5-3 | — | 250-252 |
| P6-1 | 6 | Extract `_e2e_helpers.py` shared module (housing `_import_generated_module`) | — | P6-2 | 282-284 |
| P6-2 | 6 | Update `test_p7_2.py` + `test_e2e_taichi.py` to import helper from `_e2e_helpers` | P6-1 | — | 284-287 |
| P6-3 | 6 | Robustify `test_p7_4.py:92` — iterate `notes` filtering by plan-referenced filename | — | — | 287-290 |
| P6-4 | 6 | Replace `test_phase6_exit.py` line-number whitelist with regex/marker; add markers to `test_emission_verification.py` | — | — | 290-294 |
| P7-1 | 7 | Restore `## Inventory` anchor in `dev/examples/README.md` (item 7) | — | — | 326 |
| P7-2 | 7 | Robustify `test_p7_3.py` ordering check + README path matching (items 5, 6) | — | — | 327-330 |
| P7-3 | 7 | Rename `_import_generated_module` constant in `test_p7_2.py`; remove traction-string-gap comment if Phase 1 landed (items 8, 9) | P1-6 | — | 330-336 |
| P7-4 | 7 | Trim `test_p7_6.py` to 100-250 lines by merging redundant sub-bullets (item 10) | — | — | 334-336 |
| P7-5 | 7 | Clarify `dev/tasks/PLAN-B/_SUPERSEDED.md` runtime-active vs archived (item 16) | — | — | 336-338 |
| P7-6 | 7 | Refresh GitNexus index via `npx gitnexus analyze` (item 13; user-authorized) | — | — | 338-340 |
| P7-7 | 7 | Add CI baseline-stability smoke job (algo2code workspace install, 0 import failures) (item 17) | — | — | 340-343 |

## Dependency notes

- **No cycles.** Phase 3 sequenced after Phase 1 per plan risk note (line 184).
- **Cross-phase edge:** P3-1 ← P1-5 (façade contract must land before docstring). Plan lines 184-185 call this out.
- **Cross-phase edge:** P7-3 ← P1-6 (item 9 obsolete once Phase 1 closes per plan line 372-374).
- **Phase 4 internal call graph:** `frontend/__init__` invokes `math_parser` which delegates to `symbolic/bridge`. Both prerequisites must land before wiring.
- **Phase 5 sequential chain:** algpseudocode source → codegen test → switch default → parity test → docs.
