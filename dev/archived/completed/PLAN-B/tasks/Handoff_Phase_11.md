# Handoff: Phase 10 → (Project Completion)

**From:** Phase 10 — Full V&V suite (Plan B §B9)
**To:** No subsequent phase — PLAN-B is complete.
**Date:** 2026-04-26
**Phase 10 closure branch:** `SOSOVSKI/plan-b-ph10-exec` (off `main` at `9314abc`).

This file is generated as the project completion summary per ExecPhase Step 9
(final-phase rule). PLAN-B has no Phase 11; the document below is the long-form
handoff to whoever picks up Plan C, ongoing maintenance, or first paper.

---

## Closure scope

The remaining four PLAN-B tasks **P10-1, P10-2, P10-7, P10-10** were delivered
through the `ph10_preq` sub-plan (PRs #121 + #122, merged 2026-04-26 to `main`).
This branch reconciles the PLAN-B tracker, JSONs, gate history, and GitHub issue
map with the existing implementations and re-verifies Gate C against this
working tree.

| Task | Title | Tests | Result | Deliverable surface |
|------|-------|-------|--------|---------------------|
| P10-1 | MMS convergence matrix | 10/10 | done | `mechdsl.verify.mms_matrix` (Hex8/Tet10/Hex20×SVK + Hex8×{J2/Perzyna/Lemaitre} via `elastic_regime_interpolation` policy) |
| P10-2 | Cantilever matrix (12 cells) | 15/15 | done | `run_cantilever_benchmark` + `CantileverParameters.{smoke,nightly}` (12-cell matrix at smoke profile; 40×8×4 mesh preserved on `nightly()`) |
| P10-7 | Taylor impact | 6/6 | done | `run_taylor_impact_benchmark` + `TaylorImpactParameters.smoke()` calibrated steel-like JC profile; frozen-reference (Path A) regression |
| P10-10 | Nightly CI + perf harness | 4/4 | done | `.github/workflows/nightly.yml` (manual-dispatch only per repo policy) + `tests/golden/perf/baseline_smoke.json` + `mechdsl.verify.perf.run_compare` CLI |

Combined targeted tier: **35 passed in 29.5 s.**
Full fast tier: **1377 passed / 80 skipped / 113 deselected.**
`ruff` clean; `mypy packages/mechdsl-core/src/mechdsl/verify/` clean (0 issues, 27 files).

---

## What Plan B as a whole shipped

10 phases / 54 tasks complete. End state delivered:

| Capability | Phase | Public surface |
|------------|-------|----------------|
| Updated Lagrangian formulation | 1 | `% mechanics formulation updated_lagrangian`; `ConfigurationIR`; UL kernels |
| Full convected coordinates (curvilinear reference) | 2 | `mechdsl.symbolic.convected`; metric / Christoffel / covariant derivatives |
| Viscoplasticity (Perzyna + Johnson-Cook) | 3 | `mechdsl.symbolic.models.{perzyna,johnson_cook}` + consistent tangent |
| Advanced hyperelastics (NH / MR / Ogden / HGO) | 4 | `mechdsl.symbolic.models.{neo_hookean,mooney_rivlin,ogden,hgo}` + AD oracle |
| Element zoo (Tet4 / Tet10 / Hex20 / reduced Hex8 + FB hourglass) | 5 | `ElementFactory`; patch tests for all element types |
| Lemaitre damage | 6 | `mechdsl.symbolic.models.lemaitre` + element deletion |
| Explicit dynamics | 7 | Lumped mass + central difference + critical Δt |
| MFEM and MOOSE backend printers | 8 | `mechdsl.codegen.{mfem,moose}_printer` + cross-backend verification |
| Named contraction-family templates | 9 | `mechdsl.codegen.family_registry` + family-aware emission dispatch |
| Full V&V suite | 10 | `mechdsl.verify.benchmarks` (8 runners) + `mechdsl.verify.mms_matrix` + `mechdsl.verify.perf` |

Acceptance test (Plan B header): a Taylor impact problem now runs end-to-end on
the public benchmark surface with frozen-reference regression coverage. Literature
match against Johnson & Cook (1985) on OFHC copper is documented as a
calibration carry-forward; the public runner is profile-tunable to chase that
match later without rewiring the harness.

---

## Carry-forwards

These are documented in `dev/tasks/ph10_preq/Plan_Completion_Summary.md` and
recorded here so a future maintainer picks them up. None block PLAN-B closure.

1. **TaylorImpactParameters.nightly() overruns the JC radial-return budget** on
   the shipped 6×6×20 mesh + dt=5e-8 + n_steps=400. P10-7 ships smoke +
   frozen-reference profile instead. *Fix path:* tune `nightly()` to a
   converging configuration, or split integration into chunks; user has
   indicated JC semantic edits are out-of-scope without explicit confirmation.
2. **PEEQ on long horizons (~16.6 at n_steps=200) is unphysical on the smoke
   mesh.** Suggests JC hardening / thermal softening calibration may need a
   sanity pass. Not in any baseline (Taylor baseline uses smoke profile only),
   so does not currently affect nightly regression.
3. **`@nightly`-marked tests run in the default tier.** Project's
   `pyproject.toml` `addopts` excludes `slow / gpu / e2e` but not `nightly`.
   Impact ~0.18 s; cosmetic. *Fix path:* add `not nightly` to `addopts` if
   strict tier separation becomes desirable.
4. **GitNexus CLI repo-disambiguation** — duplicate-named repos (one in
   `~/Github/Personal/MechDSL`, one in this conductor workspace) make
   `npx gitnexus impact --repo "MechDSL (/path/...)"` reject inputs with
   spaces and parens. Workaround: `Grep` fallback. *Fix path:* GitNexus CLI
   flag handling.
5. **PLAN-B P10-10 stub premise drift** — original stub asserted "all P10
   tests carry @nightly" but the actual Phase 10 test corpus uses
   `@integration` for most files. P9-2 / P10-10 rescoped the assertion to
   "the nightly tier loads what it should" (perf harness + benchmark
   registry). Worth noting in any future plan-vs-reality reconciliation.
6. **CI auto-triggers are policy-disabled.** `ci.yml` `push` / `pull_request`
   and `nightly.yml` `schedule` are kept commented out — only
   `workflow_dispatch` fires. See memory `feedback_ci_manual_dispatch`. The
   original P9-2 commit message asserts `cron + workflow_dispatch trigger` as
   the design intent; the policy can be re-enabled by uncommenting the four
   blocks if the user changes their mind.
7. **§9 spec prose patch (P9-1)** — the registry module is authoritative; the
   `09-EINSUM-OPTIMISER.md` §9 prose was already applied (per Phase 9 close).
   No outstanding patch.

---

## Open branches

`ph10_preq` left nine `work/phase10-e<N>-<slug>` branches in execution order.
Recommended PR order against `main` (each is independent of subsequent
branches): E1 → E4 → E5 → E2 → E3 → E6 → E7 → E8 → E9. After E6 (MMS) and E8
(Taylor) merge, regenerate the perf baseline once on `main` to capture
post-merge wallclocks; the committed baseline at `tests/golden/perf/baseline_smoke.json`
records the source commit (`f539cdf`) in its metadata.

---

## What's next (out of plan)

- Open the nine phase PRs in execution order (or bundle as one mega-PR if the
  reviewer prefers).
- Capture the post-merge perf baseline once the dust settles.
- Address the carry-forwards above as standalone maintenance tasks.
- A future Plan C can build against the now-stable `mechdsl.verify.benchmarks`
  + `mechdsl.verify.perf` + `mechdsl.codegen.family_registry` surfaces.

**PLAN-B is complete.**
