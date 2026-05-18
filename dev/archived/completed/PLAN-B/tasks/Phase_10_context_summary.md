# Phase 10 Context Summary: Full V&V suite

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B9 Full V&V suite

## Conventions

- All benchmarks are marked `@pytest.mark.nightly` and run only in the nightly CI tier. The fast tier does not run any Phase 10 benchmark.
- Benchmark results are compared to **literature references**, not to each other. Each benchmark test names its reference in the docstring with a full citation.
- Regression metrics: wall-clock time, peak RSS memory, Newton iteration count, CG iteration count. Baselines live in `tests/perf/baseline.json`.
- Failure threshold: >10% regression on any metric is a hard failure.

## Key Principles

- **Every Phase 10 benchmark is the final acceptance test for one or more earlier phases.** A benchmark that fails is a regression in the phase it depends on — trace the failure back to the originating phase before debugging the benchmark itself.
- **Tolerances come from the plan**, not from whatever the current implementation can achieve. Cantilever within 5% of EB beam theory; Cook's membrane within 2% of de Souza Neto; Taylor impact within 5% of Johnson & Cook. These are immutable.
- **Mesh density comes from the reference.** Don't re-discretise to "make the test pass" — use the reference's mesh and accept whatever discretisation error that implies.
- **No flaky tests in nightly.** CI runners have variable performance; the regression script uses a median-of-3 run plus a 30-day rolling baseline to suppress noise.
- **Benchmark matrix is cross-phase.** P10-2 cantilever matrix spans Phase 1 (UL), Phase 4 (Neo-Hookean), Phase 5 (Tet10, Hex20). P10-7 Taylor impact spans Phase 1 + 3 + 5 + 7. Plan failure cascades accordingly.

## Pre-resolved Design Decisions

- Phase 10 is entirely **run-and-compare** — no new constitutive models, no new elements, no new backends. Every Phase 10 task uses code from Phases 1-9.
- `pyproject.toml` gains a new pytest marker `nightly` alongside `slow` and `gpu`.
- Benchmark baselines are committed to git and updated quarterly (not per commit) to prevent drift from unrelated optimisations.
- Each benchmark's test file is named `test_benchmarks_<name>_matrix.py` (for parametrised matrices) or `test_<problem>.py` (for single-configuration benchmarks).

## Allowed Deviations

- Hex8 on the plate-with-hole benchmark has 15% tolerance on K_t instead of 5% — Hex8 is a coarse linear element for stress-concentration problems and this is documented expected behaviour.
- Tet4 on the cantilever benchmark may need a finer mesh than Hex8 to hit the 5% tolerance — shear locking at high aspect ratios is a known linear-tet pathology.

## Downstream Impact

- Phase 10 is the terminus of Plan B. Its artifacts (nightly CI workflow, regression baselines, the full benchmark suite) serve as the long-term maintenance infrastructure.
- A future Plan C (if any) would extend Phase 10 by adding its own benchmark parametrisations to the existing matrices.
