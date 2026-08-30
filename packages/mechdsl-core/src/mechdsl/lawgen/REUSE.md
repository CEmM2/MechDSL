# lawgen Reuse Map — MechDSL modules the `ticonstit` target composes

Part of the MechDSL lawgen pipeline. Doc-only, but load-bearing:
Phase 2 (P2-1 lowerer, P2-2 budgets, P2-3 emitter, P2-4 manifest) routes
through the modules named here. AC3: *"No new code duplicates an existing
MechDSL public function."* Where a genuine seam is missing, this doc flags it
as a **gap → P2-\*** rather than inventing a reuse.

All MechDSL paths below are under `packages/mechdsl-core/src/mechdsl/`. The one
exception is the **scaffold sketch**: it lives in the **NumerixWeave repo**
(`CEmM2/NumerixWeave`), *not* MechDSL — it is a read-only reference (gitignored
there), so every scaffold path in this doc is prefixed `NumerixWeave repo:`.

---

## Headline finding — the expression-lowering seam (P2-1)

**There is no reusable, clean scalar SymPy-expression → Taichi-string printer to
route lowering through. P2-1 must add one.**

I read `codegen/taichi_printer.py` (3602 lines) end to end for the seam:

- The file is entirely **`ArtifactBundle`-oriented FEM emission**. Its public
  surface is `emit(bundle) -> str`, the `TaichiCodegenFacade` class, the
  `EmissionContext` (an indent-tracking line buffer with `.emit(line)`), and a
  family of `emit_*(ctx, bundle)` helpers (`emit_constitutive_update`,
  `emit_internal_force_kernel`, `emit_tangent_matvec_kernel`, …).
- The constitutive emitters (`_emit_svk_constitutive`, `_emit_j2_constitutive`,
  `_emit_lemaitre_constitutive`) do **not** print a SymPy expression — they emit
  **hardcoded literal Taichi lines** via `ctx.emit("S = lam * tr_E * I3 + ...")`.
  They are FEM-tensor-field routines (they build `F`, `C`, `E`, run the radial
  return), not scalar-law printers.
- There is **no** `sympy` import, `_print_*` method, `StrPrinter`/`CodePrinter`
  subclass, `ccode`, or `pycode` anywhere in `taichi_printer.py`.

The closest thing that already turns a SymPy expression into a Taichi string
lives in a **different** module: `codegen/energy_emitter.py` (and its siblings
`anisotropic_emitter.py`, `spectral_emitter.py`). Their approach is
`_to_taichi_math(pycode(expr))` — SymPy `pycode` followed by a **regex** that
rewrites `math.*` → `ti.*` (`energy_emitter._to_taichi_math`,
`_MATH_TO_TAICHI`). **This is exactly the scaffold's `sympy_to_taichi.py`
anti-pattern** (`sp.pycode` + `_replace_math_calls` regex) — the very pattern
plan risk **R4** says not to ship: no CSE, no numerical guards, no budget
counting, per-component `pycode` calls, brittle regex.

**Verdict for P2-1:** **gap → P2-1 adds a thin, dedicated scalar-SymPy→Taichi
printer** (whitelist-driven, CSE-first, budget-aware). It should reuse the
*function-name mapping table* concept from `energy_emitter._MATH_TO_TAICHI` /
`_MATH_CALL_RE` (token-boundary regex, fail-loud on unregistered functions — the
one good idea there), but must **not** copy the scaffold's raw `pycode` + broad
regex, and must **not** re-use the FEM `emit_*` functions. Emit through the
existing `EmissionContext` line buffer / `TaichiCodegenFacade` so indentation and
determinism match the rest of MechDSL codegen.

---

## Mapping table

| lawgen concern | existing MechDSL module + symbol | reuse verdict |
|---|---|---|
| Expression lowering (SymPy → Taichi) | `codegen/taichi_printer.py` — none; closest is `codegen/energy_emitter.py::_to_taichi_math` / `_MATH_TO_TAICHI` (`pycode`+regex, = R4 anti-pattern) | **gap → P2-1** adds a dedicated scalar printer; may reuse the `_MATH_TO_TAICHI` mapping + fail-loud style, not the raw `pycode` path |
| Line buffering / indentation / determinism | `codegen/taichi_printer.py::EmissionContext`, `TaichiCodegenFacade`, `EmissionContext.emit` | **reuse** — emit law `@ti.func`s through `EmissionContext` so output style/determinism match core codegen |
| Deterministic CSE | *none in codebase* (`grep sp.cse` → 0 hits; scaffold uses `sp.cse(order="canonical")`) | **gap → P2-1** wires `sympy.cse` directly (SymPy is a core dep); no MechDSL wrapper exists to reuse |
| Numerical-guard injection (clamp / near-zero / `ti.max`) | `codegen/taichi_printer.py` — guards are **inlined literals** inside FEM emitters (e.g. `ti.max(...)`, near-zero deviatoric guard, NaN-sentinel), no reusable guard util | **gap → P2-\* (P2-1/P2-3)** must add scalar-law guards; the FEM guard idioms are a **pattern to mirror**, not a callable to import |
| Budget / JIT line counting | `codegen/einsum_optimizer.py::estimate_unrolled_lines`, `classify_tier`, `check_kernel_budget`, `check_absolute_budget`, `BudgetExceededError` | **extend** — the counter and `BudgetExceededError` are reusable, but they count **einsum-string + operand-shape** lines, not scalar-expression ops / `cse` temps. **P2-2** adds a scalar-expression budget over the six `TiconstitTarget` knobs; reuse `BudgetExceededError` and the fail-loud style |
| Artifact / manifest writing | `codegen/artifact.py::ArtifactBundle` (`to_json`/`from_json`/`to_dict`/`content_hash`), `ContractionPlan` | **extend** — reuse the JSON-serialisation + content-hash **pattern** for the P2-4 law manifest; the `ArtifactBundle` *shape* is FEM-specific (`problem_ir_dict`, `element_ir_dict`, `contraction_plans`), so P2-4 writes a lawgen manifest rather than an `ArtifactBundle` |
| Emitter dispatch | `codegen/taichi_printer.py::emit` (top-level orchestrator), `TaichiCodegenFacade` (step-wise façade), `_dispatch_family` | **extend** — mirror the `emit()`/façade orchestration shape for the law module; the FEM dispatch (material-model / dynamics-mode / family branches) does not apply to scalar carriers |
| FE localisation passes | `lowering/fe_localise.py::localise`, `localise_and_optimize`, `LocalisationResult`, `EinsumSpec` | **does NOT apply** — these lower a `ProblemIR` to a per-element `ElementIR` (basis functions, quadrature, formulation). A plasticity carrier is a **scalar law** with no element/mesh, so no localisation pass runs on it |
| Einsum extraction / optimisation | `lowering/einsum_extract.py::extract_einsum_specs`, `tangent_matvec_apply_spec`, `build_tangent_matvec_plan` | **does NOT apply** — extracts einsum contraction strings from an `ElementIR`. Scalar R/H/Q expressions have no tensor contractions to extract |
| Boundary lowering | `lowering/boundary.py` | **does NOT apply** — FE boundary-condition lowering, irrelevant to a scalar carrier law |

---

## The four required modules (named explicitly for the audit)

1. **`taichi_printer`** (`codegen/taichi_printer.py`) — FEM `ArtifactBundle`
   emitter. **Reuse** `EmissionContext` / `TaichiCodegenFacade` for the line
   buffer and orchestration shape. **Do not reuse** the `emit_*` FEM helpers and
   **do not** expect a scalar SymPy→Taichi printer here — it does not exist
   (headline gap → P2-1).
2. **`artifact`** (`codegen/artifact.py`) — `ArtifactBundle` /
   `ContractionPlan`. **Extend** the JSON + `content_hash` serialisation
   *pattern* for the P2-4 law manifest; the bundle *shape* is FEM-specific.
3. **`lowering`** (`lowering/`: `fe_localise.py`, `einsum_extract.py`,
   `boundary.py`) — FE-localisation and einsum passes. **None apply** to scalar
   law expressions: there is no element, mesh, quadrature, or tensor contraction
   in a plasticity carrier. Documented honestly as *out of scope*, not a gap.
4. **Scaffold `sympy_to_taichi`** (`mechdsl_lawgen`) — the read-only scaffold in
   the **NumerixWeave repo** (not MechDSL):
   `NumerixWeave repo: dev/plans/mfront_add/mfront_mimic/src/mechdsl_lawgen/sympy_to_taichi.py`.
   Its `lower_expr` (`sp.pycode` + `_replace_math_calls` regex) and `lower_many`
   (`sp.cse` + `check_budget`) are the **R4 anti-pattern not to ship**: broad
   regex over `pycode` output, no numerical guards, no whitelist enforcement at
   the printer boundary. P2-1 replaces it with a proper printer; the only reusable
   *ideas* are the CSE-first structuring and the budget-gate call sequence.

---

## Gaps flagged for Phase 2

- **P2-1** — Add a dedicated scalar SymPy→Taichi expression printer
  (whitelist/fail-loud like `energy_emitter._MATH_TO_TAICHI`, CSE-first, emitting
  through `EmissionContext`). Replaces both the scaffold `sympy_to_taichi.py` and
  the `pycode`+regex `energy_emitter` path for law expressions. **This is the
  single dependency the rest of Phase 2 stands on.**
- **P2-1** — Wire `sympy.cse(order="canonical")` for deterministic common-
  subexpression elimination. No MechDSL CSE wrapper exists to reuse.
- **P2-1 / P2-3** — Add numerical-guard injection for scalar laws (near-zero /
  clamp / `ti.max`). The FEM guard idioms in `taichi_printer.py` are a pattern to
  mirror, not an importable helper.
- **P2-2** — Add a scalar-expression budget checker over the six
  `TiconstitTarget` knobs (`max_expr_ops`, `max_cse_temps_per_func`,
  `max_func_lines`, `max_total_generated_lines_per_class`,
  `max_piecewise_branches`, `max_pow_with_symbolic_exponent`). **Reuse**
  `einsum_optimizer.BudgetExceededError` and its fail-loud style; the existing
  `estimate_unrolled_lines` counts einsum lines, not scalar-expression ops, so it
  cannot be called directly.
- **P2-4** — Write the law module + manifest by **extending** the
  `artifact.py` JSON/`content_hash` serialisation pattern; do not force the
  FEM-shaped `ArtifactBundle`.
