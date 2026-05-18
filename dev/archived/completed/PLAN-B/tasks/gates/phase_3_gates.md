# Phase 3 Gate History

Generated during ExecPhase execution.
Plan: `dev/design_docs/PLAN-B.md`
Branch: `plan-b_phase-3`

---

## P3-1: Perzyna viscoplasticity with backward Euler return map

**Issue:** #80
**Started:** 2026-04-10
**Completed:** 2026-04-17

### Gate A — Spec Compliance

#### Attempt 1 — PASS

The Perzyna module follows the Plan A `j2_power_law` structure: `PerzynaMaterial`
dataclass with field validation (eta > 0, m > 0), `radial_return` with Newton
iteration on the rate-dependent yield consistency, `ReturnMappingResult`
containing the elastic tangent stub that will be replaced in P3-3. Exposed
through `build_context` as `material_type='perzyna'`. Rate-independent limit
at eta → 0 matches rate-independent J2. Unit tests in
`test_perzyna.py::TestTaskP3_1PerzynaReturnMap` cover all 4 acceptance criteria.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

Module structure mirrors `j2_power_law.py`: validation → radial_return →
ReturnMappingResult. Rate-dependent consistency handled with a Newton loop
using the same `effective_tol = max(tol, tol * stress_ref)` scaling pattern
from Plan A J2. FD tangent safeguard deferred to P3-3 (stub raises NotImplementedError
appropriately). No over-engineering; no extra features beyond scope.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00"}
```

### Gate C — Verification

#### Attempt 1 — PASS

Perzyna verification suite: 21 passed, 2 skipped (P3-3 tangent stubs) — all 4
acceptance criteria green (`test_rate_independent_limit_matches_j2`,
`test_rate_sensitivity_higher_rate_gives_higher_stress`,
`test_quasi_static_limit_matches_j2`, `test_return_mapping_convergence`).

J2 regression suite: 28/28 passed — rate-independent path untouched.

Follow-up commit registers `"perzyna"` in the `_SUPPORTED_MATERIALS` /
`_SUPPORTED_MODELS` frozensets in `frontend/__init__.py`,
`ir/mechanics_ir.py`, `lowering/fe_localise.py`, and improves the Taichi
printer error message to clarify that Perzyna emission is a deferred
integration task. Updates `test_symbolic_ir_interface.py::TestInvalidMaterial`
parametrize list to remove `"perzyna"` from the unsupported set.

Pre-existing failure in `test_phase6_exit.py::TestTaskP6T5::test_no_resolved_todos_or_fixmes_remain`
is from the Phase 3 scaffold commit (dbe2e9a) and tracks scaffold TODOs in
`test_johnson_cook.py` / `test_viscoplastic_acceptance.py`. Not a P3-1
regression — resolves as P3-2 and P3-4 fill their stubs.

Commit: `9e0baa6` (P3-1 module) + follow-up (registration + test fix)

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "test_results": {"passed": 49, "total": 49, "percentage": 100}, "commit": "9e0baa6+followup"}
```

---

## P3-2: Johnson-Cook flow stress + adiabatic temperature evolution

**Issue:** #81
**Started:** 2026-04-17
**Completed:** in progress

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Spec-checker verified against the full task JSON by reading each changed file.
`JohnsonCookMaterial` is a frozen dataclass with all parameters + validation;
JC flow stress `(A + B*alpha^n) * (1 + C*ln(eps_dot_star)) * (1 - T_star^m)`
is correctly implemented with the rate-floor `eps_dot_star = max(..., 1)` and
`T_star` clamped to [0,1]. Coupled 2x2 backward-Euler Newton for (dl, dT) is
present with analytical Jacobian, line-search (keeps dl > 0, T < T_melt_guard),
and a RuntimeError on non-convergence. `state_variables` returns
`("alpha", "T")`. `"johnson_cook"` is registered in
frontend.build_context / ProblemIR / fe_localise. Taichi printer is unchanged
(JC emission is a deferred integration task, consistent with P3-1 wording).
P3-3 tangent stubs are untouched. All 4 `TestTaskP3_2JohnsonCookReturnMap`
acceptance criteria covered with real assertions. T_melt guard raises with
a clear message both at entry and after Newton.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS (with required fix)

Score: 8.5/10, 0 high/critical, 1 medium + 2 minor warnings, all addressed.

Physics verified point-by-point: rate-independent limit at T=T_ref with C=0
yields `sigma_y = A + B*alpha^n` matching J2 exactly (byte-for-byte to 1e-8);
T_star clamp protects against NaN/negative stress; coupled 2x2 Jacobian signs
verified by inspection (all four partials correct); yield-stress structure
is multiplicative with `(1 - T_star^m)`; adiabatic heating `rho_c_p*dT = beta*sy*dl`
has correct sign; line-search enforces both `dl > 0` AND `T_new < T_melt - eps`;
T_melt guard fires both at entry and post-Newton; von Mises near-zero guard
and negative-dl clamp follow 07-CONVENTIONS.md §6.

Conventions verified: module docstring cites Johnson & Cook (1983) + Simo &
Hughes (1998) §3.4; layout mirrors `perzyna.py`; reuses `deviatoric`,
`von_mises`, `elastic_tangent`, `ReturnMappingResult` from `j2_power_law`;
`state_variables = ("alpha", "T")`; no sympy.diff-of-Psi pattern; type hints
and `TYPE_CHECKING`-guarded `NDArray` import present; mypy clean.

**Resolution of medium warning:** en-dash U+2013 at
`test_johnson_cook.py:215` triggered RUF003 (the implementer's ruff-clean
claim was incorrect for this file). Fixed in follow-up commit 3afcc7f —
replaced the en-dash with a hyphen-minus. `uv run ruff check` on the two
files is now clean.

Minor warnings noted but accepted (heterogeneous R1/R2 scaling in Newton
residual norm; line-search exhaustion falls through without raising —
both consistent with Perzyna's defensive posture).

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "score": 8.5, "issues": {"minor": 2, "medium": 1, "high": 0, "critical": 0}, "resolution": "RUF003 en-dash fix in 3afcc7f"}
```

### Gate C — Verification

#### Attempt 1 — PASS

Verification commands (fresh run after Gate B fix):

- `uv run pytest packages/mechdsl-core/tests/test_johnson_cook.py::TestTaskP3_2JohnsonCookReturnMap -v` → 4/4 passed.
- `uv run pytest packages/mechdsl-core/tests/test_j2.py -v` → 28/28 passed.

Full related-suite sweep (`test_j2` + `test_perzyna` + `test_johnson_cook` +
`test_symbolic_ir_interface` + `test_frontend_build_context`): 124 passed,
4 skipped (intentional P3-3 tangent stubs in Perzyna + JC).

`uv run ruff check` on the two P3-2 files: clean. `uv run mypy
packages/mechdsl-core/src/mechdsl/symbolic/models/johnson_cook.py`: clean.

Commit: `5e9efc4` (implementation) + `3afcc7f` (Gate B fix)

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "test_results": {"passed": 124, "total": 124, "percentage": 100}, "commit": "5e9efc4+3afcc7f"}
```

**Completed:** 2026-04-17

---

## P3-3: Consistent viscoplastic algorithmic tangent

**Issue:** #82
**Started:** 2026-04-17
**Completed:** 2026-04-17

### Gate A — Spec Compliance

#### Attempt 1 — PASS

All four acceptance criteria implemented. Perzyna `radial_return` now returns
the full algorithmic consistent tangent (no longer the elastic stub), derived
from linearising the single-scalar Newton residual at convergence:
`denominator = 3*mu + H'(alpha_new) + eta_term`, with
`eta_term = (eta/m) * (1/dt)^(1/m) * dl^(1/m - 1)` — the analytic derivative
of the overstress term evaluated at converged dl. Johnson-Cook `radial_return`
captures the converged 2x2 Newton Jacobian `J_conv`, then uses Schur-complement
reduction to obtain `denominator = -det(J_conv) / J_conv[1,1]`, which is the
effective scalar stiffness after eliminating dT. Both models call a shared
helper `assemble_j2_like_tangent` extracted at module scope in `j2_power_law.py`
(J2's own `radial_return` now routes through the same helper — byte-identical
formula). State-variable contract unchanged (`("alpha",)` for Perzyna,
`("alpha", "T")` for JC). Unit tests in `TestTaskP3_3PerzynaTangent` and
`TestTaskP3_3JohnsonCookTangent` cover all 4 acceptance criteria plus two
sanity checks (Perzyna-at-eta→0 matches J2, elastic branch returns elastic
tangent exactly).

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

Shared `assemble_j2_like_tangent` docstring explicitly documents the three
`denominator` choices (J2 / Perzyna / JC) and references Simo & Hughes §3.4
Box 3.5. No sympy-diff-of-Psi pattern introduced (dissipative models are not
hyperelastic; algorithmic tangent only). No over-engineering: J2's original
inline formula was replaced with a helper call; the refactor is byte-for-byte
equivalent (verified by `test_tangent_fd_plastic` still passing). Perzyna's
eta_term derivation included inline in comments. JC's Schur-complement
derivation also inline, with the sanity note that at the uncoupled limit
(beta=0, C=0, T=T_ref) the off-diagonal Jacobian entries vanish and the
formula reduces byte-for-byte to J2 (verified by a unit test).

Ruff + mypy clean on all five touched files. Gate B clean on first try — no
en-dashes, no dead locals, no extra features beyond scope.

Major-symmetry tests added per task spec (not in original scaffold). FD test
harness aligned with J2's central-difference convention (`dE_sym`,
`/ (2*eps)`) — the earlier draft divided by `eps` producing exactly 2x the
true derivative, triggering a 50% rel err; fixed before commit.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "score": 9.5, "issues": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Verification commands:

- `uv run pytest packages/mechdsl-core/tests/test_perzyna.py::TestTaskP3_3PerzynaTangent -v` → 4/4 passed (FD, symmetry, eta-zero-limit, elastic).
- `uv run pytest packages/mechdsl-core/tests/test_johnson_cook.py::TestTaskP3_3JohnsonCookTangent -v` → 3/3 passed (FD, symmetry, uncoupled-limit).
- `uv run pytest packages/mechdsl-core/tests/test_j2.py -v` → 28/28 passed (J2 refactor is regression-free).

Full Phase 3 related sweep
(`test_j2 + test_perzyna + test_johnson_cook + test_symbolic_ir_interface
+ test_frontend_build_context`): 131 passed, 0 skipped.

Full mechdsl-core fast sweep (excluding known pre-existing
`test_phase6_exit` scaffold-TODO failure, which resolves naturally when
P3-4 fills the remaining stubs): 1110 passed, 6 intentional skips (5 P3-4
stubs + 1 e2e metric propagation stub).

Commit: `8101a14`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "test_results": {"passed": 131, "total": 131, "percentage": 100}, "commit": "8101a14"}
```

**Completed:** 2026-04-17

---

## P3-4: Rate sensitivity + quasi-static limit + thermal softening verification

**Issue:** #83
**Started:** 2026-04-17
**Completed:** 2026-04-17

### Gate A — Spec Compliance

#### Attempt 1 — PASS

All 5 scaffold stubs filled with real assertions covering the three AC bullets:

- **AC-1 (rate sensitivity):** `test_perzyna_rate_sensitivity` and
  `test_jc_rate_sensitivity` both sweep `dt` across 4 orders of magnitude and
  assert strict monotonic stress increase, plus a >=5% end-to-end signal floor
  to guard against a flat curve. JC uses ``dt in [1e-3, 1e-7]`` to keep
  ``dl/dt >> eps_dot_0`` — below that, the ``max(dl/(dt*eps_dot_0), 1)`` clamp
  masks rate dependence (documented in the test docstring).
- **AC-2 (quasi-static limit):** `test_perzyna_quasi_static_limit` uses
  ``eta=1e-12`` and asserts stress + alpha match J2 power-law within ``1e-6``.
  `test_jc_quasi_static_limit` uses ``C=0, beta=0, T=T_ref, dt=1`` and makes
  the same 1e-6 assertion.
- **AC-3 (thermal softening):** `test_jc_thermal_softening` sweeps T from
  ``T_ref`` to ``T_ref + 1200K`` (approaches 80% of ``T_melt - T_ref``) with
  ``C=0`` and ``beta=0`` to isolate the thermal effect, asserts strict
  monotonic stress decrease, plus a >=10% drop floor.

All tests use `radial_return` directly on (E, alpha, T) triples — no Newton
solve, no Taichi — matching the scope bullet "Each test uses the
`radial_return` call directly on a single (E, alpha, T) triple".

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00"}
```

### Gate B — Domain Quality

#### Attempt 1 — PASS

Tests use `deviatoric(stress)` before `von_mises` to isolate the plastic
signal from the volumetric elastic component — the `von_mises` function
expects a deviatoric tensor (documented in its docstring) and returning the
wrong value on the full stress was the original draft's bug. Each test
explicitly clamps plastic activation (`assert res.is_plastic`) so test
failures cannot silently reduce to elastic comparisons. Rate sweeps use
signal floors (>=5% for rate, >=10% for thermal) to catch degenerate
configurations where the curve would be flat but still technically monotone.

Conventions: module docstring present; reference unit system (MPa/mm/s)
documented; shared uniaxial-strain helper reused from the P3-2 pattern.
Ruff + mypy clean on first try.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "score": 9.5, "issues": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Verification commands:

- `uv run pytest packages/mechdsl-core/tests/test_viscoplastic_acceptance.py -v` → 5/5 passed.
- Full mechdsl-core fast sweep (`-m "not slow and not gpu"`): 1115 passed,
  1 intentional skip (e2e metric propagation stub — Plan B P10-1).
- `test_phase6_exit.py::TestTaskP6T5::test_no_resolved_todos_or_fixmes_remain`
  — pre-existing scaffold-TODO failure flagged at P3-1 Gate C — now PASSES,
  since P3-4 removed the last of the "stub — implement after Task P3-X"
  markers.

Commit: `e659d5d`

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00", "test_results": {"passed": 1115, "total": 1115, "percentage": 100}, "commit": "e659d5d"}
```

**Completed:** 2026-04-17

---

