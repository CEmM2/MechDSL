# Phase 2 Gate History

Generated during ExecPhase execution.
Plan: `dev/design_docs/PLAN-B.md`
Branch: `plan-b_phase-2`

---

## P2-1: Covariant/contravariant bases + metric tensors

**Issue:** #75
**Started:** 2026-04-16T10:00:00Z
**Completed:** 2026-04-16T11:00:00Z

### Gate A — Spec Compliance

#### Attempt 1 — FAIL

The spec compliance reviewer verified that all five required functions/classes were present with correct formulas (MetricField, compute_reference_metric with G kwarg, compute_convected_metric curvilinear path, invert_metric, covariant_bases, contravariant_bases). All three acceptance criteria had test coverage. However, the non-Cartesian code path of `covariant_bases(F, G_ref_vecs=<non-None>)` at `convected.py:183` had zero test coverage. The spec requires "produce covariant and contravariant base vectors at an arbitrary material point" including curvilinear cases, so this untested branch represents a test gap.

**Failure mode:** `test_gap`
**What failed:** `covariant_bases` curvilinear branch (line 183) — no test exercises `G_ref_vecs != None`
**Why:** Implementer tested all acceptance criteria but missed covering this specific code branch

```json
{"gate": "A", "attempt": 1, "result": "fail", "timestamp": "2026-04-16T10:15:00Z", "failure_mode": "test_gap", "what_failed": "covariant_bases curvilinear branch untested", "why": "implementer covered acceptance criteria but missed non-Cartesian code path"}
```

#### Attempt 2 — PASS

Added `test_covariant_bases_curvilinear` to `test_convected_curvilinear.py` exercising cylindrical reference base vectors G_ref = [[1,0,0],[0,r,0],[0,0,1]] with a shear F. Verifies symbolic g_I = F @ G_I and numerical evaluation at r=2.5 to atol=1e-14. All 5 P2-1 tests pass.

**Resolution:** Added curvilinear covariant_bases test; commit `f852744`

```json
{"gate": "A", "attempt": 2, "result": "pass", "timestamp": "2026-04-16T10:20:00Z", "resolution": "added test_covariant_bases_curvilinear covering G_ref_vecs != None branch"}
```

### Gate B — Domain Quality

#### Attempt 1 — FAIL

The domain quality reviewer found a critical physics bug in `compute_convected_metric`. The formula `g = F^T G_metric F` is mathematically wrong when `F` is the Cartesian deformation gradient (∂x/∂X) and `G_metric` is the reference metric tensor `G_IJ`. The correct derivation from the spec (`g_I = F G_I` where `G_I` are reference base vectors) gives:

`g_IJ = g_I · g_J = (F G_I)^T (F G_J) = G_I^T C G_J`

In matrix form: `g = G_ref_vecs^T @ (F^T F) @ G_ref_vecs`, NOT `F^T @ G_metric @ F`.

These differ for any non-isotropic F with non-Cartesian reference — the existing tests only used `F = λI` (isotropic stretch) which commutes with everything, masking the bug. Additionally:
- `invert_metric` docstring falsely claimed a numerical fallback that doesn't exist
- `MetricField` accepted non-symmetric matrices without validation
- API inconsistency: `compute_convected_metric` took G_metric while `covariant_bases` took G_ref_vecs

**Failure mode:** `physics_error`
**What failed:** `compute_convected_metric` formula F^T G F (convected.py:136) — wrong for non-isotropic Cartesian F
**Why:** Formula treats G as if F were the curvilinear gradient, but codebase uses Cartesian F everywhere

```json
{"gate": "B", "attempt": 1, "result": "fail", "timestamp": "2026-04-16T10:35:00Z", "failure_mode": "physics_error", "what_failed": "compute_convected_metric formula F^T G F wrong for non-isotropic Cartesian F", "why": "formula assumes curvilinear F but codebase uses Cartesian F; tests only used isotropic F masking the bug"}
```

#### Attempt 2 — PASS

Fixed all four issues:
1. Changed `compute_convected_metric(F, G=None)` → `compute_convected_metric(F, G_ref_vecs=None)` with correct formula `G_ref_vecs.T @ (F.T @ F) @ G_ref_vecs`
2. Added symmetry validation to `MetricField.__init__`
3. Corrected `invert_metric` docstring (removed false numerical-fallback claim)
4. Added `test_cylindrical_nonisotropic_f_consistency` that cross-checks `compute_convected_metric` against `covariant_bases` dot products with non-isotropic F — this test would have caught the original bug

All tests updated to pass `G_ref_vecs` (base vectors matrix) instead of `G` (metric matrix). 14 passed, 8 skipped (P2-2/P2-3 stubs).

**Resolution:** Corrected formula, unified API on G_ref_vecs, added symmetry guard and cross-consistency test; commit `4d287ae`

```json
{"gate": "B", "attempt": 2, "result": "pass", "timestamp": "2026-04-16T10:50:00Z", "resolution": "corrected formula to G_ref_vecs^T C G_ref_vecs, unified API, added cross-consistency test"}
```

### Gate C — Verification

#### Attempt 1 — PASS

Full test suite run: 1038 passed, 13 skipped (P2-2..P2-5 stubs), 1 failed (pre-existing `test_phase6_exit.py::test_no_resolved_todos_or_fixmes_remain` — flags TODO markers in P2-4/P2-5 scaffold files, unrelated to P2-1). Pass rate: 99.9% (excluding pre-existing).
Commit: `4d287ae`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T10:55:00Z", "test_results": {"passed": 1038, "total": 1052, "skipped": 13, "failed": 1, "percentage": 99.9, "note": "1 failure is pre-existing test_phase6_exit TODO check"}, "commit": "4d287ae"}
```

---

## P2-2: Christoffel symbols from metric

**Issue:** #76
**Started:** 2026-04-16T11:05:00Z
**Completed:** 2026-04-16T11:30:00Z

### Gate A — Spec Compliance

#### Attempt 1 — PASS

All spec requirements verified by code inspection:
- Function signature `christoffel_symbols(g, theta) -> MutableDenseNDimArray(3,3,3)` matches spec
- Formula Γ^K_{IJ} = (1/2) g^{KL} (∂g_{IL}/∂θ^J + ∂g_{JL}/∂θ^I − ∂g_{IJ}/∂θ^L) implemented correctly
- Fast path returns zeros when metric has no coordinate dependence (Cartesian)
- Metric derivatives precomputed once before triple loop (caching)
- All 3 acceptance criteria have real tests (no stubs): Cartesian zero, cylindrical closed form, < 5s performance
- Cylindrical reference values verified: Γ^r_{θθ}=-r, Γ^θ_{rθ}=Γ^θ_{θr}=1/r
- One bonus test (spherical) beyond spec — correct and harmless

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T11:20:00Z"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

Score: 9/10. Formula verified term-by-term against the textbook definition. Index placement gamma[K,I,J] = Γ^K_{IJ} is correct. All bracket terms use correct index assignments. Reference values for both cylindrical and spherical independently derived and confirmed. Two minor non-blocking observations: (1) fast-path zero check uses structural equality rather than simplify — safe for all practical inputs; (2) no explicit symmetry assertion in tests, though spherical test verifies it implicitly. No medium, high, or critical issues.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T11:25:00Z", "score": 9, "issues": {"minor": 2, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Full test suite: 1042 passed, 9 skipped (P2-3..P2-5 stubs), 1 failed (pre-existing test_phase6_exit). Pass rate: 99.9%.
Commit: `d41f70d`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T11:30:00Z", "test_results": {"passed": 1042, "total": 1052, "skipped": 9, "failed": 1, "percentage": 99.9}, "commit": "d41f70d"}
```

---

## P2-3: Covariant derivatives (vectors and tensors)

**Issue:** #77
**Started:** 2026-04-16T11:35:00Z
**Completed:** 2026-04-16T12:10:00Z

### Gate A — Spec Compliance

#### Attempt 1 — PASS

All 3 functions exist with correct signatures: `covariant_derivative_contravariant`, `covariant_derivative_covariant`, `covariant_derivative_tensor2`. All 4 test stubs replaced with real implementations covering both acceptance criteria (cylindrical radial field, Cartesian reduction). No scope creep.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T12:00:00Z"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

Score: 10/10. All three formulas verified term-by-term against the `gamma[K,I,J] = Γ^K_{IJ}` convention: contravariant uses `gamma[J,I,K]`, covariant uses `gamma[K,I,J]`, tensor2 uses `gamma[J,I,L]` and `gamma[K,I,L]`. All hand-calculated reference values independently verified for cylindrical (v=(r²,0,0), w=(r,0,0), T=diag(r,0,0)). Code follows existing patterns.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T12:05:00Z", "score": 10, "issues": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Full test suite: 1052 passed, 1 skipped (e2e metric propagation), 1 failed (pre-existing test_phase6_exit). Pass rate: 99.9%.
Commit: `c469c7c`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T12:10:00Z", "test_results": {"passed": 1052, "total": 1054, "skipped": 1, "failed": 1, "percentage": 99.9}, "commit": "c469c7c"}
```

---

## P2-4: NRPyLaTeX metric-assignment directives

**Issue:** #78
**Started:** 2026-04-16T11:35:00Z
**Completed:** 2026-04-16T12:10:00Z

### Gate A — Spec Compliance

#### Attempt 1 — PASS

`_mech_assign` handler added and registered in HANDLERS. Validates exactly one of `--metric_current`/`--metric_reference`. Stores tensor name in `accum["metric_current"]` or `accum["metric_reference"]`. Parser.py propagates both keys to returned context. All 5 test stubs filled (e2e skipped with Plan B B2.5 pointer). `test_assign_is_not_deferred` added to parser tests. No scope creep.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T12:00:00Z"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

Score: 9/10. Handler follows existing patterns exactly (same as `_mech_material`). Error messages include tensor name and line number. Parser correctly propagates metric keys only when present. Test coverage thorough: both flags individually, both together, malformed, both-flags-error, structural contract test. One minor cosmetic note: option values are ignored but docstring explains this adequately.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T12:05:00Z", "score": 9, "issues": {"minor": 1, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Full test suite: 1052 passed, 1 skipped, 1 failed (pre-existing). Pass rate: 99.9%.
Commit: `edaf84c`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T12:10:00Z", "test_results": {"passed": 1052, "total": 1054, "skipped": 1, "failed": 1, "percentage": 99.9}, "commit": "edaf84c"}
```

---

## P2-5: Curvilinear patch test + Cartesian equivalence

**Issue:** #79
**Started:** 2026-04-16T17:00:00Z
**Completed:** 2026-04-16T17:35:00Z

### Gate A — Spec Compliance

#### Attempt 1 — FAIL

Gate A reviewer raised concerns about the test scope: the spec says "mesh" and "displacement fields" but the implementation tests at the constitutive level (SVK stress through convected pathway) rather than through a full FEM solve. However, the plan spec (B2.5) only requires "uniform strain → exact stress" and "identical results within 1e-12" — the element assembly doesn't support curvilinear meshes (that's downstream codegen). The reviewer also correctly identified `@pytest.mark.slow` misuse (no Taichi JIT in these tests).

**Failure mode:** `misunderstanding`
**What failed:** Reviewer expected full FEM pipeline solve; actual scope is constitutive-level testing of Phase 2 symbolic infrastructure
**Why:** Task JSON aspirational language vs. plan spec actual requirements

```json
{"gate": "A", "attempt": 1, "result": "fail", "timestamp": "2026-04-16T17:10:00Z", "failure_mode": "misunderstanding", "what_failed": "reviewer expected FEM solve but plan spec B2.5 only requires constitutive-level stress verification", "why": "task JSON aspirational vs plan spec actual scope"}
```

#### Attempt 2 — PASS (override)

Gate A findings triaged: (1) FEM solve concern is out of scope — plan spec B2.5 says "exact stress" and "identical results within 1e-12", no mesh/solver infrastructure exists for curvilinear domains yet. (2) `@pytest.mark.slow` removed — valid finding, fixed. (3) Displacement vs stress — stress equivalence is the achievable verification at the symbolic layer. Both acceptance criteria are covered by real tests with correct tolerances.

**Resolution:** Removed `@pytest.mark.slow` markers; FEM solve concern documented as out-of-scope per plan spec B2.5.

```json
{"gate": "A", "attempt": 2, "result": "pass", "timestamp": "2026-04-16T17:15:00Z", "resolution": "slow markers removed; FEM solve out of scope per plan spec B2.5"}
```

### Gate B — Domain Quality

#### Attempt 1 — FAIL

Gate B reviewer found a critical gap: the patch test only evaluated at theta=0 where G_ref is diagonal, so off-diagonal curvilinear coupling was never exercised. At theta=0, cylindrical base vectors are axis-aligned — effectively testing a scale factor, not true curvilinear geometry. Also flagged: `@pytest.mark.slow` misuse (same as Gate A), and inconsistent tolerances (1e-14 for E, 1e-12 for S).

Reviewer incorrectly claimed the analytical formula comment was wrong — verified that `(1.5λ+μ)(λ²-1)` equals `(3λ+2μ)·0.5·(s²-1)`.

**Failure mode:** `test_gap`
**What failed:** Patch test only at theta=0 — diagonal G_ref never exercises off-diagonal terms
**Why:** Implementer chose theta=0 "for simplicity", missing that the curvilinear coupling terms are the core value of the test

```json
{"gate": "B", "attempt": 1, "result": "fail", "timestamp": "2026-04-16T17:15:00Z", "failure_mode": "test_gap", "what_failed": "patch test only at theta=0 — diagonal G_ref misses off-diagonal curvilinear coupling", "why": "implementer simplified away the key test dimension", "score": 5}
```

#### Attempt 2 — PASS

Fixed all actionable issues:
1. Added theta sweep [0, pi/8, pi/4] at each r value — G_ref now has full off-diagonal terms from cylindrical tangent vectors at arbitrary angles. Test evaluates 15 (r,theta) points total.
2. Removed `@pytest.mark.slow` from both tests (no Taichi JIT).
3. Unified equivalence tolerances to 1e-13 for E, S, and sigma.
4. Clarified analytical formula comment with full derivation chain.

All 15 evaluation points produce identical Cauchy stress to machine precision, confirming the convected pathway handles true curvilinear geometry correctly.

**Resolution:** Added theta variation, removed slow markers, unified tolerances; commit `d2a4bf9`

```json
{"gate": "B", "attempt": 2, "result": "pass", "timestamp": "2026-04-16T17:25:00Z", "resolution": "added theta=[0,pi/8,pi/4] sweep, removed slow markers, unified tolerances to 1e-13", "score": 9, "issues": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Full test suite (fast): 1055 passed, 1 skipped (pre-existing e2e metric propagation stub), 0 failed. Pass rate: 100%.
Commit: `d2a4bf9`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-16T17:35:00Z", "test_results": {"passed": 1055, "total": 1056, "skipped": 1, "failed": 0, "percentage": 100.0, "note": "1 skip is pre-existing e2e metric propagation stub (Plan B B2.5)"}, "commit": "d2a4bf9"}
```

