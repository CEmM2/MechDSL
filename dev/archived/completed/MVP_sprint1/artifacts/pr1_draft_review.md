# Review of PR #1: MVP_plan.md vs. PLAN-A and Design Doc Suite

## Context

PR #1 adds `dev/plans/MVP_plan.md` — a granular, phased implementation plan derived from `dev/design_docs/PLAN-A.md`. It breaks work into 10 phases (P0–P9) with task-level file ownership, verification criteria, and parallelism notes. This review checks the plan against PLAN-A (the source) and the full design doc suite (the source of truth).

---

## Findings by Severity

### HIGH — Blocking or could lead to incorrect implementation

#### H1. algo2code package completely missing

MVP_plan.md contains zero references to the `algo2code` package. This contradicts:

- **PLAN-A A1.1** — monorepo tree explicitly includes `algo2code/` as a workspace member
- **11-ALGO2CODE.md §1.1** — specifies two Plan A integration points:
  - A8: Newton driver swaps imported CG/PCG for algo2code-transpiled `solvers/pcg.tex → _pcg_taichi.py`
  - A9: J2 radial-return transpiled from algpseudocode (Algorithm 7.1, de Souza Neto)
- **00-OVERVIEW.md D8** — linear solver is "initially imported, later from algo2code-generated code"

**Required:** Add P0-level task for algo2code skeleton; add integration notes at P7 (Newton driver) and P8 (J2 return mapping).

#### H2. Template-based codegen (.py.j2) introduced without design doc backing

Tasks P6.3, P6.4, P6.5, P7.1, and P8.1 reference Jinja2 template files (e.g., `templates/constitutive_elastic.py.j2`). The design docs specify a `TaichiPrinter` class with programmatic `emit_*` methods (06-CODEGEN.md §1.2):

```python
class TaichiPrinter:
    def generate(self, element_ir, problem_ir) -> str:
        sections = [self.emit_header(...), self.emit_constitutive_kernel(...), ...]
```

This is an architectural divergence. Either:
- Update the design docs to adopt templates, or
- Revise MVP_plan to match the `TaichiPrinter.emit_*()` architecture

#### H3. Missing sequential dependencies in the dependency graph

The dependency section omits two critical gates:

| Missing dependency | Why it matters |
|---|---|
| **Phase 6 → Phase 7** | Newton driver (P7.1) requires element kernel from P6; BC codegen (P7.2) needs TaichiPrinter from P6.2 |
| **Phase 7 → Phase 8** | Plasticity integration (P8.4) swaps the elastic constitutive call in the element kernel, requiring the elastic path from P6–P7 to be working |

---

### MEDIUM — Correctness risk or significant underspecification

#### M1. No phase-level exit criteria (phase gates)

PLAN-A defines explicit phase gates (e.g., "Exit criterion A1: `uv run pytest` passes, CI green, solver import works on a test system"). MVP_plan has only task-level verification — no consolidated gate that all tasks in a phase must pass before the next phase begins. This risks tasks being marked "done" individually while the phase as a whole is not validated.

#### M2. ConvectedCoordinateMapIR not explicitly tasked

04-MECHANICS-IR.md §3 (line 119): "The MVP uses `ConvectedCoordinateMapIR` in its basic form (metric tensors G_IJ, g_IJ)." This named IR entity is not assigned to any task. It should appear in P4.1 or P4.2.

#### M3. Convected coordinate codegen not explicitly tasked

06-CODEGEN.md §8 specifies convected coordinate support in the TaichiPrinter (metric field storage, convected-aware kinematics, `ref_metric`/`cur_metric` fields from §3.4). PLAN-A A7.2 says "Includes convected coordinate infrastructure." No P6 task addresses this.

#### M4. JIT budget thresholds never stated

The specific numbers from 07-CONVENTIONS.md §9 (512 per `@ti.func`, 2000 per `@ti.kernel`, 5000 absolute ceiling) are not referenced anywhere. P5.1 says "budget counting + tier classification" but without the concrete thresholds. PLAN-A A7.4 says "Budget validation before emission" — P6.4 omits this.

#### M5. Cantilever tolerance missing from P7.1

PLAN-A A8 exit criterion: "Tip displacement matches reference within 2%." MVP_plan P7.1 says only "converges on elastic cantilever benchmark." The 2% threshold is lost.

#### M6. Cook's membrane missing from Phase 8

PLAN-A A9 exit criterion: "Single-element uniaxial tension reproduces exact hardening curve. **Cook's membrane matches reference.**" MVP_plan defers Cook's membrane entirely to P9.3, losing the Phase 8 verification gate.

#### M7. P1.2 missing uniaxial tension past yield check

PLAN-A A2.3 specifies three verification tests for the plastic reference: (1) uniaxial tension past yield — check σ = σ_y + H·ε_p, (2) elastic below yield = elastic reference, (3) return mapping to machine precision. P1.2 mentions only (2) and (3).

---

### LOW — Editorial, style, or minor gaps

#### L1. No P-to-A phase mapping table
P0 = A1, P1 = A2, ..., P9 = A10. The off-by-one is consistent but never documented. A mapping table would eliminate ambiguity.

#### L2. Duration estimates removed without explanation
PLAN-A provides per-phase durations (3–4 days to 1–2 weeks) and a 10–14 week total. Removing these loses scheduling context.

#### L3. Documentation missing from Definition of Done
PLAN-A A10.5 specifies README + example LaTeX + rendered output comparison. The DoD lists 4 criteria but omits documentation delivery.

#### L4. CI tiers not referenced
08-VERIFICATION.md §5.1 defines Fast (<2 min, every commit), Medium (<10 min, every PR), Nightly (<60 min). P0.3 doesn't reference this tiered structure.

#### L5. `uv run` not used in P0.2 verification
P0.2 says `python -c "import mechdsl"`. Per CLAUDE.md: "Never invoke `python` directly — use `uv run python`."

#### L6. SymPDE integration not mentioned
00-OVERVIEW.md D1 and 05-ELEMENT-IR.md establish SymPDE as the variational forms library. MVP_plan does not mention it anywhere. The SymPDE adapter (for variational form expansion → einsum string extraction) should appear in P4 (IR/Lowering).

#### L7. AD oracle backend and sample count unspecified
PLAN-A A4.5: "Lambdify to PyTorch/Taichi autodiff, N=100 random states." 00-OVERVIEW.md D4: "Implement for PyTorch and Taichi autodiff, not JAX." P3.5 says "compare symbolic stress/tangent to autodiff-derived reference" without specifying backend or N.

#### L8. Mandel conversion missing from P3.4
PLAN-A A4.4 explicitly lists `mandel_from_voigt()`. P3.4 mentions "tensor↔Voigt and 4th-order tangent mappings" but omits Mandel.

#### L9. Test ID categories listed without counts
P9.4 lists "P/S/M/E/N/T/B/A/C test IDs" but not specific counts (P1–P6, S1–S9, M1–M6, E1–E6, N1–N5, T1–T4, B1–B5, A1–A3, C1–C3 = 43 tests total). A developer could miss IDs.

#### L10. Specific test IDs not cross-referenced to tasks
PLAN-A cross-references specific test IDs to phases (e.g., "Test S9 from 08-VERIFICATION.md applies here" in A4.1; "Test P6 from 08-VERIFICATION.md applies here" in A5.2). MVP_plan does not carry these references forward.

#### L11. Numerical safeguards underspecified in P6.3
06-CODEGEN.md §4.3 enumerates: J > 10⁻¹⁵, det(F) > 10⁻¹⁵, σ_eq > 10⁻¹² · σ_y, Δλ ≥ −10⁻¹⁵. P6.3 says "CSE and runtime guards" — vague.

---

## Positive Findings

1. **Package naming correct** — MVP_plan uses `mechdsl.*` file paths throughout, correctly avoiding PLAN-A's stale `compmech.*` naming.
2. **Task granularity is good** — Each task has clear file ownership and verification criteria.
3. **Parallelism notes are mostly accurate** — P3.1/P3.2/P3.4, P4.1/P4.2, P7.2/P7.3/P7.4 are correctly identified as parallelizable.
4. **Physical benchmark coverage is complete** — All 5 benchmarks from PLAN-A A10.3 are named in P9.3.
5. **All 10 PLAN-A phases are represented** — No phase was dropped.

---

## Recommended Actions

1. **Request changes** for H1 (algo2code), H2 (template vs emit_* architecture), H3 (missing dependencies)
2. **Request additions** for M1–M7 (phase gates, convected coverage, tolerances)
3. **Suggest improvements** for L1–L11 as non-blocking comments
