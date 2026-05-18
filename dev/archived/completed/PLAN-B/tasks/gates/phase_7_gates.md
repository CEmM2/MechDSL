# Phase 7 Gate History

Generated during ExecPhase/ExecTask execution.
Plan: `dev/design_docs/PLAN-B.md`
Branch: `plan-b_phase-7` (off `plan-b_phase-6` tip; Phases 5 & 6 not yet merged to main)
Scaffold commit: `d3f3fba`

---

## P7-1 — Lumped mass + central-difference integrator

### Gate A — Spec compliance — PASS

Deliverables + acceptance criteria all satisfied:
- `packages/mechdsl-core/src/mechdsl/solver/lumped_mass.py` (133 lines) — `compute_lumped_mass(coords, conn, rho, element_type)` for Hex8 via 2×2×2 Gauss row-sum; `NotImplementedError` stubs for TET4/TET10/HEX20.
- `DynamicsMode(Enum)` added to `ir/mechanics_ir.py` with `STATIC` / `EXPLICIT`; `ProblemIR.dynamics_mode: DynamicsMode | None = None` auto-infers to `STATIC` in `__post_init__` (same pattern as `configuration`). `to_dict` / `from_dict` updated; legacy dicts without the key auto-infer.
- `emit_explicit_driver` added to `codegen/taichi_printer.py` (+119 lines). When `dynamics_mode == EXPLICIT`, the printer emits `advance_one_step(dt)` implementing `v^{n+1/2} = v^{n-1/2} + dt · M_inv · (f_ext − f_int)` then `u^{n+1} = u^n + dt · v^{n+1/2}`, allocates `v` / `M_lumped` fields, skips `tangent_matvec`/`newton_solve`. STATIC branch byte-identical to pre-P7 output.
- Element-deletion guard honoured via upstream `compute_internal_force` (Phase 6 carry-forward); `advance_one_step` operates on nodal state and inherits deletion implicitly.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "all deliverables present, acceptance criteria satisfied"}
```

### Gate B — Domain quality — PASS

- No Phase 5 integration-break: `test_mechanics_ir*.py` round-trip tests are per-field (not strict-key-set) and accept the new optional field; `test_frontend_build_context.py` strict-key guards target `build_context` not `ProblemIR` → unaffected.
- JIT budget: `advance_one_step` well under 2000 lines; shape functions inlined via `ti.static` over physics indices.
- Voigt / sign / tensor conventions N/A (task has no constitutive contraction).
- `is_deleted` handling correctly delegated to `compute_internal_force`; no new silent emit-time defaults.
- Minor (logged, not blocking): no explicit validation that `dynamics_mode` is not set to a value requiring further enum members — acceptable since enum is closed.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "no integration breaks; budget clean; no new silent defaults"}
```

### Gate C — Fresh-run verification — PASS

Independent re-run after implementer handed off:
- `uv run pytest packages/mechdsl-core/tests/test_explicit_integrator.py -v` → **3 passed in 0.05s**.
- `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -q` → **1216 passed / 1 failed / 4 skipped / 56 deselected** (baseline 1214 passed / 1 failed / 7 skipped). Net +2 passes. The single failure is the pre-existing `test_phase6_exit.py::TestTaskP6T5::test_no_resolved_todos_or_fixmes_remain` scanning scaffold-TODOs in remaining P7-2/P7-3 stub files — strictly shrinking as tasks execute, no regression introduced.
- Slow suite (implementer-run): 1270 passed / 1 failed / 6 skipped — same pre-existing, zero regressions.

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "fresh-run verified: 3/3 task tests pass, +2 net vs baseline, no regressions"}
```

---

## P7-2 — Critical time step computation

### Gate A — Spec compliance — PASS

- `packages/mechdsl-core/src/mechdsl/solver/critical_timestep.py` (162 lines, pure numpy). Signature matches spec: `critical_timestep(coords, conn, lam, mu, rho, element_type, safety=0.9)`.
- Wave speed: `c_d = sqrt((lam + 2*mu) / rho)`. Characteristic length: Hex8 → `V_e^(1/3)` via 2×2×2 Gauss (reuses `lumped_mass.py` Jacobian machinery); Tet4/Tet10 → shortest corner edge; Hex20 → `NotImplementedError` with Plan B post-B7 pointer.
- Per-element `dt_e = L_e / c_d`; global `dt = safety * min(dt_e)`.
- 3/3 acceptance cases pass.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "signature and acceptance criteria match spec"}
```

### Gate B — Domain quality — PASS

- No IR / codegen / frontend edits — standalone helper, zero blast radius on other layers.
- Characteristic-length convention (`V^(1/3)`) is conservative for non-degenerate hexahedra and documented in the module docstring with §B7.1 pointer.
- Voigt / sign / tensor conventions N/A.
- Module docstring documents the convention and its rationale.
- No silent defaults introduced.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "standalone helper, no layer bypass, convention documented"}
```

### Gate C — Fresh-run verification — PASS

- `uv run pytest packages/mechdsl-core/tests/test_critical_timestep.py -v` → **3 passed in 0.04s**.
- `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -q` → **1219 passed / 1 failed / 1 skipped / 56 deselected**. Net +3 passes vs post-P7-1 baseline (1216). Pre-existing P6-T5 tripwire now scoped to `test_explicit_dynamics_acceptance.py` TODOs only (P7-3 territory). Skips dropped 4→1 — the three `test_critical_timestep` stubs are now real.

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "3/3 task tests pass, +3 net vs post-P7-1 baseline, no regressions"}
```

---

## P7-3 — Free vibration + explicit/implicit cross-check (Phase 7 exit)

### Gate A — Spec compliance — PASS

- `test_free_vibration_first_mode_period_within_1_percent`: free-fixed Hex8 axial bar (20×1×1, L=1, ν=0, E=1, ρ=1 → `c=1`, `f_1 = c/(4L) = 0.25 Hz`). 5 periods, `dt = 0.5·critical_timestep`, FFT peak within 1% of analytical.
- `test_explicit_implicit_quasistatic_equilibrium_matches_within_1e6`: 2×2×2 Hex8 block, ramp Dirichlet `u_x=1e-3` over 4000 steps then 16000 hold steps, mass-scaled ρ·1e6, 2% per-step velocity damping. Explicit vs implicit (Newton) final-displacement max-abs error < 1e-6.
- Both `@pytest.mark.slow @pytest.mark.integration`. Phase 7 exit criterion (Plan B §B7 "within 1%") satisfied.
- All TODO markers removed → P6-T5 tripwire cleared.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "both acceptance criteria satisfied; phase 7 exit met"}
```

### Gate B — Domain quality — PASS

- Test file is self-contained (inline mesh helpers mirroring P6 pattern).
- BC deviation (free-fixed vs the task-JSON-suggested fixed-fixed): documented in test docstring; choice is physically valid and the analytical formula matches the BC. Spec explicitly permits either convention.
- Mass scaling (ρ·1e6) documented per §B7 allowed deviation.
- Added 2% per-step velocity damping so the undamped SVK block's ringing decays in finite wall-clock — documented in docstring. Acceptable: damping is a mesh/integrator concern orthogonal to the physics being verified (quasi-static equilibrium).
- Zero source-layer edits; acceptance-test-only task.

**Carry-forward finding (medium, non-blocking):** The emitted EXPLICIT driver's `allocate_explicit_fields(nn)` must be called before the first `from_numpy` on any existing `x_ref`/`u`/etc. field, otherwise Taichi's materialize raises `RuntimeError: These field(s) are not placed` on `v`/`M_lumped`. The Phase 6 idiom (`allocate_fields(nn, ne)` → load mesh → work) does not match — EXPLICIT modules need `allocate_explicit_fields` *also* called pre-materialise. Test helper works around it; fix should land in Phase 8 or P10-7 prep (merge the two allocators or document call-ordering in the emitted module docstring).

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "acceptance-test-only; deviations (BC, damping, mass-scaling) all documented; latent allocate_explicit_fields ordering gotcha surfaced for Phase 8 carry-forward"}
```

### Gate C — Fresh-run verification — PASS

- `uv run pytest packages/mechdsl-core/tests/test_explicit_dynamics_acceptance.py -v` → **2 passed in 22.00s**.
- `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -q` → **1220 passed / 0 failed / 1 skipped / 56 deselected** — first fully-green fast suite since Phase 7 scaffold. P6-T5 TODO tripwire cleared.
- Phase 7 exit baseline: +6 passes vs pre-phase baseline (1214 → 1220), zero regressions anywhere.

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-17T00:00:00Z", "resolution": "2/2 acceptance pass; fast suite fully green (1220/0/1); Phase 7 exit criterion satisfied"}
```

---
