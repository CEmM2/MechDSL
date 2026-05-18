# Handoff: Phase 5 → Phase 6

## Phase 5 Summary

**Phase:** Additional element types + integration rules + hourglass control + ElementFactory
**Branch:** `plan-b_phase-5`
**Status:** Complete — all 7 tasks done, exit criterion B5 (patch test for every new element + hourglass suppression) met
**Final suite:** 1201 passed, 1 skipped (P10-1 metric-assign, unrelated), 0 failed (mechdsl-core fast sweep, markers `not slow and not gpu`)
**TODO-cleanup gate (P6T5):** GREEN — Phase 5 leaves the branch in a clean state

### What was built

| Component | Function | Location |
|-----------|----------|----------|
| Tet4 basis + 1-pt quadrature | Linear tetrahedron, Gauss at (1/4,1/4,1/4) with weight 1/6 | `codegen/tet4_tables.py` |
| Tet10 basis + 4-pt Keast rule | Quadratic tet with edge midpoints; symmetric Keast/Zienkiewicz rule | `codegen/tet10_tables.py` |
| Hex20 basis + 27-pt Gauss | 20-node serendipity (8 corners + 12 edge midpoints), 3×3×3 tensor Gauss | `codegen/hex20_tables.py` |
| Hex8 reduced quadrature | 1-point Gauss at the cube centroid with weight 8.0 | `codegen/hex8_reduced_tables.py` |
| Flanagan-Belytschko hourglass | 4 HG vectors, γ-projection (FB 1981 eq. 2.33), force + symmetric stiffness | `codegen/hourglass.py` |
| IntegrationRule enum | FULL / REDUCED axis orthogonal to topology | `ir/mechanics_ir.py` |
| ElementFactory API | Uniform `ElementFactory.create(topology, integration, hourglass, formulation, configuration)` | `ir/element_factory.py` |
| Frontend wiring | `% mechanics cell <topo> --integration <rule> --hourglass <scheme>` parsed; `build_context` routes through factory | `frontend/directives.py`, `frontend/__init__.py` |
| Patch-test parametric harness | Topology-agnostic single-element SVK internal force; runs patch test for any ElementFactory triple | `verify/_patch_test_kernels.py`, `verify/patch_test.py` |

### Key decisions and fixes

1. **Topology vs. integration-rule axis is orthogonal.** `IntegrationRule` is a separate enum; `ElementIR` gained a trailing keyword-default field `integration_rule` so existing callsites were unaffected.
2. **ElementFactory is the single entry point.** `build_context` routes through it and wraps `ValueError` as `UnsupportedError`. The frontend vocabulary is now wider than the lowering layer's — non-hex8 topologies are accepted by the factory but may still be rejected downstream in later phases.
3. **Flanagan-Belytschko γ-projection (FB 1981 eq. 2.33) is required for AC-1 on distorted hexes.** Raw Γ vectors only annihilate linear modes on a regular cube. The projected γ_α is the correct form for the zero-hourglass-force-on-constant-strain guarantee.
4. **FB scalar stiffness: ε = λ_h · μ · V_e^(2/3)** (FB 1981 eq. 4.8 variant). Default λ_h = 0.05. Exposed via `build_context(..., hourglass_coef=0.05)`.
5. **Reduced Hex8 without hourglass is allowed but unstable.** ElementFactory permits the triple (hex8, reduced, None) and returns a valid ElementIR; docstring warns. This is used as the regression guard in the P5-5 and P5-7 hourglass-suppression tests (confirms the zero-energy mode is active without FB).
6. **"Still-unsupported fake" progression.** Guard tests that used the next unsupported element family as a sentinel evolved across tasks: hex8-only → tet10 (after P5-1) → hex20 (after P5-2) → hex27 (after P5-3). P5-6's guard tests now use `tet4 + integration=reduced` as the still-invalid combo.
7. **Patch-test convention: normalised global-equilibrium residual** `||Σ f_int|| / max|f_int|`. All full-integration elements clear 1e-12; reduced Hex8 + FB clears 1e-8 (with both observed at exact zero on the canonical strain diag(0.01,0,0) due to integer-valued basis gradients at the centroid).
8. **`f_int` sign convention in this codebase.** `f_int = ∂E_strain/∂u`, so resistance to a displacement u reads `f_int · u > 0` (same sign as u). This matters for hourglass-suppression assertions.

### Acceptance evidence (P5-7 patch-test table)

Material: SVK at `E=200 GPa, nu=0.3` → `λ≈1.154e11, μ≈7.692e10`. Strain = diag(0.01, 0, 0).

| Triple | normalised error | tol |
|--------|------------------|-----|
| hex8 / full | 1.95e-16 | 1e-12 |
| tet4 / full | 0.00e+00 | 1e-12 |
| tet10 / full | 1.51e-16 | 1e-12 |
| hex20 / full | 1.05e-15 | 1e-12 |
| hex8 / reduced + FB | 0.00e+00 | 1e-8 |

Hourglass suppression (reduced Hex8, u along Γ₁):
- Without FB: `||f_int|| = 0` (zero-energy mode confirmed)
- With FB: `||f_int|| = 3.48e+11`, `f_int·u > 0` (resisting)

## What Phase 6 inherits

Phase 6 is **codegen** per Plan B (the Taichi backend extensions to emit the new element kernels). Phase 5 only built the Python reference kernels for verification; no `@ti.func` / `@ti.kernel` emission happened yet for Tet4/Tet10/Hex20/reduced-Hex8/hourglass. Phase 6 needs to wire all of these through `codegen/taichi_printer.py` while respecting the JIT budget (Hex20 × 27 quadrature points is 540 ops — near the 512-line `@ti.func` ceiling; will need to be split across helpers per CLAUDE.md).

### Open items pointing into Phase 6 / later phases

- **Hex20 JIT-budget split.** `hex20_tables.py` module docstring flags it; codegen must partition the `assemble_hex20` kernel across helpers.
- **FB hourglass codegen.** `mechdsl.codegen.hourglass` is pure Python; the Taichi emission is Phase 6's job.
- **Volumetric locking on Tet4.** Deferred to Plan B phase B5.3 (B-bar / F-bar). Patch test uses ν=0.3 to stay well away from the incompressible limit.
- **Multi-element patch-test harness.** Current P5-7 harness runs single-element residuals (mathematically sufficient for the patch test). A multi-element irregular-mesh harness is a future enhancement — belongs under V&V expansion in Phase 10.
- **Frontend vs. lowering vocabulary gap.** `build_context` accepts tet4/tet10/hex20/reduced-hex8 today, but `fe_localise` still rejects non-hex8 topologies. Phase 6 narrows that gap as each element gains a generated kernel.

## Branching & merge

Branch `plan-b_phase-5` is ready to merge into `main`. Phase 6 branches from `main` after merge. Commits P5-1..P5-7:

- P5-1: `5a248ca`
- P5-2: `3549830`
- P5-3: `37e087c`
- P5-4: `93b9d9d`
- P5-5: `02c575e`
- P5-6: `5b668ca`
- P5-7: `21d0e2b`

Gate history: `dev/tasks/PLAN-B/gates/phase_5_gates.md`.
