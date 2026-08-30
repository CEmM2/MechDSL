# MechDSL lawgen — scope and prior-art statement

MechDSL lawgen is an **independent implementation**. It does **not** implement
or accept MFront/TFEL DSL syntax, and it does **not** parse, translate, or
reproduce TFEL/MFront source code. MFront is acknowledged only as prior art
that informed the general idea of authoring constitutive laws in a compact
form and emitting runtime code from them.

## What lawgen actually is

The lawgen pipeline turns a small, self-contained YAML law spec into a Taichi
carrier for the NumerixWeave `ticonstit` library:

- **Own YAML law schema.** A law declares `name`, `parameters` (material
  constants), `variables` (free-variable bindings such as `p`, `edot`, `T`),
  and `expressions` with the three required roles `R`/`H`/`Q`. See
  `../../../../laws/plasticity/swift_voce.yaml` for a worked example.
- **Restricted SymPy expression parser.** Each `R`/`H`/`Q` string is parsed
  against the declared symbols with a non-eval parser and a restricted math
  allow-list — never `sympify`/`eval` on untrusted YAML (`cli.py`).
- **Deterministic SymPy → Taichi lowering.** A bespoke printer with
  deterministic common-subexpression elimination and injected numerical guards
  turns each scalar `sympy.Expr` into Taichi source
  (`sympy_to_taichi.py`, `guard_transforms.py`), gated by pre-emission JIT
  budgets (`budgets.py`).
- **ticonstit-specific carrier contract.** The emitted `@ti.func` carrier
  class, generated tests, and provenance manifest target the frozen
  `ticonstit` contract (`contracts.py`, `carrier_emitter.py`, `manifest.py`),
  stamped `mechdsl-lawgen/<version>`.

The only `--target` the CLI accepts is `ticonstit`; there is no MFront target
or MFront input path anywhere in the pipeline.
