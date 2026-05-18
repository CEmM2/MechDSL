# Phase 5 Gate History

Plan: `dev/plans/post_recovery_plan.md`
Branch: `post-recovery-plan_phase-5` (off `post-recovery-plan_phase-4`)
Started: 2026-05-01

## Pre-execution scan of prior phase gates

P3-1 and P4-5 each recorded an `integration_break` (P2-2 docs allowlist needed widening). Pattern recurs in Phase 5 once `test_p5_5.py` joins the docs tier — flagged in P5-5 Gate B as a third occurrence and tagged as a Phase 6 cleanup candidate.

algo2code parser limitations also surfaced during pre-execution probing (`/` dropped in some assignment LHS contexts; multi-letter scratch identifiers tokenised as products). These pre-date Phase 5 and are documented in `algo2code.library.pcg`'s parser deferral note. Phase 5 mirrors that pattern: ships the algpseudocode source as a specification artifact, hand-translates the runtime body, asserts parity.

---

## P5-1 — dev/algorithms/radial_return_j2.tex

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-5`
**Issue:** #228

### Gate A — Spec Compliance (attempt 1, pass)

- New `dev/algorithms/radial_return_j2.tex` lands the J2 radial-return algorithm with full power-law hardening argument set (E, a, m, L, K, n, y) plus Newton bounds (t, M).
- New `packages/algo2code/src/algo2code/library/radial_return_j2.py` exposes `RADIAL_RETURN_J2_LATEX` and `get_radial_return_j2_latex()`, mirroring the `library.pcg` consumption pattern. Single-source-of-truth: the Python module reads the LaTeX file at import time rather than duplicating the body.
- Algorithm body uses single-letter scratch identifiers throughout to stay within the algo2code parser's working subset.

```json
{"task": "P5-1", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "4/4 task tests pass; algo_parser smoke parses the source"}
```

### Gate B — Domain Quality (attempt 1, pass)

- LaTeX header documents the parser deferral surface explicitly so future contributors know why the algpseudocode is structurally simpler than the imported reference.
- `algo2code.library.radial_return_j2` reads the canonical file rather than duplicating it; identical pattern to `library.pcg`.
- Power-law hardening exposed via the K and n args per plan line 237-239.

```json
{"task": "P5-1", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_1.py -v
4 passed in 0.03s
```

```json
{"task": "P5-1", "gate": "C", "attempt": 1, "result": "pass", "evidence": "4/4 task tests pass"}
```

**Completed:** 2026-05-01

---

## P5-2 — algo2code radial-return codegen test

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-5`
**Issue:** #229

### Gate A — Spec Compliance (attempt 1, pass)

- New `packages/algo2code/tests/test_radial_return_codegen.py` (5 tests) exercises the algo2code import chain on `RADIAL_RETURN_J2_LATEX`: parse, transpile, AST-validity, entry-point declaration, JIT budget.
- JIT budget probe asserts ≤ 512 lines (07-CONVENTIONS.md §9). Module-level proxy used today; tightens to per-`@ti.func` once parser supports inner-kernel emission.
- Power-law arg-set assertion (E, a, m, L, K, n, y) re-asserted on the algo2code side so the package owns its own parser-readiness contract.

```json
{"task": "P5-2", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "5/5 codegen + 5/5 meta-spec tests pass"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Parser-deferral surface documented inside the test module so the contract is greppable from both sides.
- Coarse JIT-budget probe pins the 512 number directly in the test source (no constant lookup elsewhere) — drift-resistant.
- AST-parse validation guards against any future Taichi-codegen output that emits non-Python syntax.

```json
{"task": "P5-2", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/algo2code/tests/test_radial_return_codegen.py packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_2.py -v
10 passed in 0.04s
```

```json
{"task": "P5-2", "gate": "C", "attempt": 1, "result": "pass", "evidence": "5/5 codegen + 5/5 meta-spec tests"}
```

**Completed:** 2026-05-01

---

## P5-3 — lib/plasticity.py dispatcher + feature flag

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-5`
**Issue:** #230

### Gate A — Spec Compliance (attempt 1, pass)

- New `packages/mechdsl-core/src/mechdsl/lib/plasticity.py`:
  - `radial_return(mat, E_strain, alpha_old, tol, max_iter)` dispatcher with signature identical to the imported reference.
  - `_radial_return_algo2code` body — verbatim Python translation of the algpseudocode (today structurally identical to the imported implementation; will diverge only after the algo2code parser fix).
  - `active_path_name()` — returns `"algo2code"` or `"imported"`; re-evaluates env on every call.
  - `FEATURE_FLAG_ENV = "MECHDSL_USE_IMPORTED_RR"` single source of truth.
  - Truthy-set `{"1", "true", "yes", "on"}` (case-insensitive) flips the active path.
- Re-exports `ReturnMappingResult` so callers do not need to import from the imported module directly.

```json
{"task": "P5-3", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "5/5 task tests pass; signature-equality assertion holds"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Dispatcher has no module-level cache of the active path — env-var check is per-call so toggles work mid-session without a re-import dance.
- `_imported_path_active()` private helper centralises the env-var truthy logic; tests exercise the truthy set explicitly.
- `_radial_return_algo2code` documents the parser-deferral relationship in its docstring; future replacement with `algo2code.transpile` is a single-function change.

```json
{"task": "P5-3", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_3.py -v
5 passed in 2.05s
```

Bit-equality dispatcher-vs-direct under the flag confirmed (`test_dispatch_preserves_imported_results_under_flag`).

```json
{"task": "P5-3", "gate": "C", "attempt": 1, "result": "pass", "evidence": "5/5 task tests pass"}
```

**Completed:** 2026-05-01

---

## P5-4 — imported vs algo2code parity test

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-5`
**Issue:** #231

### Gate A — Spec Compliance (attempt 1, pass)

- New `packages/mechdsl-core/tests/test_j2_radial_return_parity.py` (4 tests) exercises elastic / elastoplastic / unloading load steps plus a tolerance-contract guard.
- `BASELINE_TOL = 1e-12` derives from imported-path Newton tolerance per plan line 267-268.
- Each parity case asserts agreement on stress, alpha_new, delta_lambda, is_plastic, tangent — full ReturnMappingResult coverage.

```json
{"task": "P5-4", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "4/4 parity + 5/5 meta-spec tests pass"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Pre-test sanity assertions confirm each load step actually triggers the regime it claims (elastic case asserts `is_plastic is False` on the imported path; elastoplastic asserts `True`; unloading asserts `False` after raised yield surface).
- BASELINE_TOL is bounded above zero AND ≤ 1e-9 — protects against either drift toward absolute equality (which would silently re-tighten the parity contract) or runaway slack.
- `_assert_parity` helper prevents per-test-case copy-paste drift.

```json
{"task": "P5-4", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/test_j2_radial_return_parity.py packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_4.py -v
9 passed in 0.22s
```

```json
{"task": "P5-4", "gate": "C", "attempt": 1, "result": "pass", "evidence": "4/4 parity + 5/5 meta-spec tests"}
```

**Completed:** 2026-05-01

---

## Mid-phase amendment — algo2code parser fixes (no longer deferred)

The original P5-1..P5-5 execution shipped the radial-return runtime path as a verbatim Python translation pinned by parity tests, mirroring the `library.pcg` pattern. The user directed (post-Phase-5 close) that the algo2code parser bugs **must not be deferred** and that the radial-return path must consume `algo2code.transpile` directly. This amendment landed the following in the same Phase 5 branch:

### Parser fixes in `packages/algo2code/src/algo2code/expr_parser.py`

1. **Multi-letter scratch identifiers** — `LETTER` regex changed from `[a-zA-Z]` to `[a-zA-Z][a-zA-Z0-9]*`. Multi-letter scratch names (`pq`, `sn`, `sy`, `ap`, `Hp`) now tokenise as a single `Var` instead of an implicit product of single LETTERs.
2. **Binary `/` in expressions** — added `SLASH` branch to `parse_term`. Previously `parse_term` only handled `\cdot` and implicit-mul; division silently terminated the expression. Now `a + b / c` parses as `a + (b / c)`.

### Codegen fix in `packages/algo2code/src/algo2code/backends/taichi_codegen.py`

3. **Scalar-only algorithms** — driver previously emitted `n = b.shape[0]` unconditionally, breaking algorithms with no vector argument (radial-return is scalar-only). The line is now omitted when no vector arg is present and no local vector storage is needed; otherwise a marker is written so the failure is visible if reached.

### Verification

- All 52 existing `algo2code` tests continue to pass.
- `algo2code.library.pcg.PCG_ALGORITHM_LATEX` now transpiles cleanly (it had been documented as parser-deferred since landing).
- `algo2code.library.radial_return_j2.transpile_radial_return_j2()` returns valid Python; `mechdsl.lib.plasticity` execs the result at module-load and consumes the resulting `radial_return_j2(sigma_eq, alpha, mu, K, n, sigy0, tol, max_iter)` callable inside the dispatcher.

### Algorithm rewrite (P5-1) and dispatcher rewire (P5-3)

- `dev/algorithms/radial_return_j2.tex` rewritten as a scalar Newton inner loop (multi-letter scratch identifiers used freely; division required for `dl = dl + res / denom`; `If/Else` guard on `ap < tol` to avoid `0**(n-1)` divergence at the first iteration when `alpha_old = 0`).
- `mechdsl.lib.plasticity._radial_return_algo2code` now performs tensor-side preprocessing (deviatoric, von Mises, near-zero guard) using imported helpers, calls the transpiled scalar Newton, then performs tensor-side postprocessing (stress reconstruction, algorithmic tangent). Bit-equality with the imported reference at `BASELINE_TOL = 1e-12` survives the rewire (parity test still passes for elastic, elastoplastic, and unloading load steps).

### Test updates

- `test_radial_return_codegen.py::test_specification_artifact_documented_deferral` replaced with `test_library_wrapper_exposes_transpile_helper` (the deferral surface is gone; the contract is now "transpile and exec").
- Codegen test arg-set assertion updated to scalar Newton signature (`sigma_eq, alpha, mu, K, n, sigy0, tol, max_iter`).
- `test_p5_1.py` power-law arg check updated (`y` → `sigy0`).
- `test_p5_2.py` meta-spec replaced parser-deferral grep with `transpile_radial_return_j2` + `callable(...)` grep.

### Failure-mode tag

```json
{"phase": 5, "amendment": "parser-fix", "result": "pass", "failure_modes": ["deferral_lifted"], "evidence": "31/31 P5 tests + 52/52 algo2code tests + 1835/1835 fast suite; bit-equality parity holds at 1e-12"}
```

---

## P5-5 — design-doc note

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-5`
**Issue:** #232

### Gate A — Spec Compliance (attempt 1, pass)

- Appended new section `## 11 J2 radial-return: algo2code substitution` to `dev/design_docs/07-CONVENTIONS.md` (`06-PLASTICITY.md` does not exist; plan line 252-256 permits either).
- Section names `MECHDSL_USE_IMPORTED_RR`, cross-links `dev/algorithms/radial_return_j2.tex`, describes default-vs-fallback dispatch roles, parity contract with `1e-12` tolerance, and stability-soak retention plan.

```json
{"task": "P5-5", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "3/3 task tests pass"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Section uses absolute path conventions consistent with the rest of the design-doc tree (relative links from `07-CONVENTIONS.md` reach `dev/algorithms/` and `packages/mechdsl-core/tests/`).
- Cross-task: P2-2 docs-collection allowlist widened a third time to admit `test_p5_*.py`. Pattern flagged in handoff and in the P2-2 stub comment as a Phase 6 cleanup candidate (`integration_break` recurrence: third occurrence after P3-1, P4-5).

```json
{"task": "P5-5", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_5.py -v
3 passed in 0.20s

$ uv run pytest -m "not slow and not gpu" --tb=line -q
1835 passed, 82 skipped, 96 deselected, 2 warnings in 49.33s
```

```json
{"task": "P5-5", "gate": "C", "attempt": 1, "result": "pass", "failure_modes": ["integration_break (P2-2 allowlist widened, third occurrence)"], "evidence": "3/3 task tests pass; 1835/1835 fast suite"}
```

**Completed:** 2026-05-01

---
