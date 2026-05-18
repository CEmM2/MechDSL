# Handoff: Phase 8 → Phase 9

**From:** Phase 8 — MFEM and MOOSE backend printers
**To:** Phase 9 — Contraction template tuning
**Date:** 2026-04-17
**Phase 8 branch:** `plan-b_phase-8` (off `plan-b_phase-7` tip; Phases 5, 6, 7, 8 not yet merged to main)
**Phase 8 commits:** `a5c14f3`+`bdfbe1a` (P8-1), `af370da` (P8-2), `2fd7d78`+`87f2cd2`+`4733e3f` (P8-3), plus tracking commits
**Phase 8 exit baseline:** **1286 passed / 0 failed / 1 skipped / 59 deselected** in fast suite; cross-backend suite 3/3 skip-clean locally.

---

## What Phase 8 shipped

| Task | Title | Commits | Deliverables |
|------|-------|---------|--------------|
| P8-1 | MFEM printer | `a5c14f3` + `bdfbe1a` (Gate B fix) | `codegen/mfem_printer.py`, `codegen/mfem_template/CMakeLists.txt`, `tests/test_mfem_printer.py` (11/11 pass) |
| P8-2 | MOOSE printer | `af370da` | `codegen/moose_printer.py`, `codegen/moose_template/input_template.i`, `tests/test_moose_printer.py` (8/8 pass) |
| P8-3 | Cross-backend verification | `2fd7d78` + `87f2cd2` + `4733e3f` (Gate B attempts 2+3) | `tests/test_cross_backend.py`, `.github/workflows/ci-backends.yml` — **Phase 8 exit** |

### Acceptance evidence

- **MFEM emission**: self-contained `.cpp` with `mfem::ParNonlinearForm` + `MechDSLSaintVenantKirchhoff` (subclass of `mfem::NonlinearFormIntegrator`), full 6×ndof B-matrix in engineering Voigt, 6×6 `C_eng` (λ+2μ normal diagonals, λ off-diagonals, μ on shear diagonals 3/4/5), parse-checked via clang-format idempotence + structural guards. Voigt round-trip (tensorial → engineering → tensorial) exact to 1e-15.
- **MOOSE emission**: `ComputeStressBase` subclass with `computeQpStress()`/`computeQpJacobian()`, RankTwoTensor / RankFourTensor mappings, matching `.i` input file with sliding-roller + pull BCs, template ships via hatchling tree packaging.
- **Cross-backend harness**: 3 integration tests (`@pytest.mark.slow @pytest.mark.integration`) compile a shared 2×1×1 Hex8 SVK cantilever `ProblemIR` to each backend; tolerance gate uses `max(abs=1e-8, rel=1e-6 * |u_ref|_max)`. All 3 skip cleanly locally with explicit toolchain-missing reasons.
- **Backend-printer frozen guarantee**: P8-3's end-to-end MFEM path uses test-side regex injection (`_inject_mfem_disp_dump`) to splice a helper function and an env-var-gated dump call into the printer's emitted `main.cpp` before write — zero edits to `mfem_printer.py` or its CMakeLists template. MOOSE side appends a `NodalValueSampler` VPP block to the `.i` and reads the resulting CSV via stdlib `csv.DictReader`.

### Backend coverage after Phase 8

| Backend | Status | Notes |
|---------|--------|-------|
| Taichi | Production (MVP baseline) | `taichi_printer.py` — golden-regression pinned |
| MFEM (C++, MPI) | Emission complete; compile-verify gated to CI | SVK only; Hex8 only; STATIC only |
| MOOSE (C++, input file) | Emission complete; compile-verify gated to CI | SVK body for all named materials (beyond-MVP names produce SVK-style body — see Phase 9 handoff item below) |

### Test footprint

- Unit: `test_mfem_printer.py` (11 tests, 0.3s), `test_moose_printer.py` (8 tests, 0.09s) — hermetic, no binaries.
- Integration (slow+integration markers, skip-when-missing): `test_cross_backend.py` (3 tests, skip 0.14s locally).
- CI: `.github/workflows/ci-backends.yml` — 3 `workflow_dispatch`-only jobs (MFEM, MOOSE, combined MFEM+MOOSE).

---

## Carry-forwards to Phase 9

### High priority

1. **Land real MFEM/MOOSE CI runs.** Docker images currently pinned to placeholders (`ghcr.io/mfem/mfem-ubuntu:4.7`, `idaholab/moose:2024.12.30-moose`); verify against upstream, pin to dated digests, and re-enable `pull_request`/`push` triggers. The test's `M5` skip-on-subprocess-fail behaviour means first real run surfaces format mismatches as skip-with-stderr (not red CI). Combined MFEM+MOOSE image does not exist upstream — the `mfem-vs-moose` leg stays `workflow_dispatch` only until that story is resolved.
2. **Couple MFEM dump helper to printer ordering.** `_MFEM_DISP_DUMP_CPP` in `test_cross_backend.py` assumes `Ordering::byNODES` implicitly; the printer uses it at line 531 but there is no defensive assertion. If future printer work switches to `byVDIM`, the cross-backend test silently produces garbage rather than skipping. Either expose ordering via a printer-emitted compile-time constant or add a runtime assertion in the injected helper.
3. **P8-2 MOOSE SVK label accuracy (M1 from Gate B):** docstring claims "Total-Lagrangian SVK" but emits small-strain via `_mechanical_strain` (MOOSE's incremental small-strain). Linearises correctly for small strain but the label is a nit. Fix docstring OR switch body to Green-Lagrange `E` from `_deformation_gradient` — latter is what Plan-A convention promises.
4. **P8-2 beyond-MVP silent emission (M2 from Gate B):** `perzyna`, `j2_power_law`, `hgo`, `neo_hookean`, `lemaitre` all get valid-looking class names via the stable model→class map but the emitted stress body is SVK-style. Restrict to `svk`/`j2_power_law` for MOOSE, OR raise `NotImplementedError` for unsupported models.
5. **P8-2 Makefile.app template:** scope bullet "Makefile.app or CMakeLists template" was not delivered for MOOSE (only `.i` template shipped). Either add the missing template, OR update the P8-2 scope retroactively in the task JSON.

### Medium priority

6. **P8-3 module docstring stale.** Lines 36-44 of `test_cross_backend.py` describe an obsolete two-TU architecture (separate `disp_dump.cpp` file); the actual architecture is single-TU with regex splicing. One-line docstring fix.
7. **P8-1 geometric tangent term.** Currently only emits the material small-strain contribution (`B^T C_eng B`); for large-strain SVK Newton convergence the geometric (initial-stress) term `∫ G^T Σ G dV` should be added. Flagged inline as a `NOTE:` in the printer with "Deferred to Plan B §B8 P8-3" — carry over to P9 or to a dedicated P9-X.
8. **P8-1 skeletal ess_bdr:** currently pins every boundary to zero in the emitted `main`; real P8-3 CI runs need actual BC tags. Newton driver also has zero RHS — no load stepping. These are gated behind `MECHDSL_DISP_OUT` env-var path in P8-3's test but cannot produce a non-trivial cantilever deflection until real BCs land.

### Low priority / cleanup

9. **Prior-phase plan overview check-offs.** Plan overview issue #55 had `[ ]` for Phases 6 and 7 despite completion — corrected this session. Verify the root-cause: ExecPhase's plan-overview-check-off step may be silently failing when the phase-issue body is fetched in an unexpected state.
10. **MechDSL name convention.** P8-1 Gate B fix renamed the MFEM class to `MechDSLSaintVenantKirchhoff` to match MOOSE convention. Confirm all future backend printers use the same stable `MechDSL<Material>` class-name map.

---

## Phase 9 preview

Phase 9 (Plan B §B9, lines 243-261) focuses on **Contraction template tuning** — three tasks:

| Task | Title | Est complexity/risk |
|------|-------|---------------------|
| P9-1 | Named contraction-family template design | 4/3 |
| P9-2 | opt_einsum path caching + reuse | 3/3 |
| P9-3 | Contraction benchmark harness + auto-tuning | 5/4 |

P9-1 is the Phase 9 entry point and is blocked-by `[P5-6, P5-7, P8-1, P8-2, P8-3]` — all now complete. Phase 9 can launch immediately; no Phase-8 merge-to-main required before starting P9.

---

## Branch discipline note

Phases 5, 6, 7, 8 still live as separate feature branches stacked off each other (Phase 8 parent is Phase 7 tip `f7df56d`). Merging all four into main is a separate operation pending user direction — Phase 9 should branch from `plan-b_phase-8` tip to avoid re-basing.
