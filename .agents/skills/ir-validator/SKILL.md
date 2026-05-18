---
name: ir-validator
description: Validate IR discipline in MechDSL, including immutability, layer boundaries, validation completeness, and serialization coverage. Use after editing IR, lowering, or codegen-adjacent pipeline code.
---

# IR Validator

This skill is read-only.

Read:

- `dev/design_docs/01-ARCHITECTURE.md`
- `dev/design_docs/04-MECHANICS-IR.md`
- `dev/design_docs/05-ELEMENT-IR.md`
- `.agents/rules/ir.md`

## Checks

1. Immutability
   Verify `ProblemIR` and `ElementIR` remain frozen dataclasses and look for mutation patterns.
2. Layer bypasses
   Codegen should not import `sympy`, `mechdsl.symbolic`, or frontend modules.
   Lowering should not import codegen.
   Frontend should not reach into later pipeline layers.
3. Construction-time validation
   Compare `__post_init__` validation against the spec and confirm matching tests exist.
4. Serialization
   Confirm `to_dict()` and `from_dict()` round-trips exist and are tested.
5. Supported-subset contract
   Unsupported constructs should reject explicitly with plan-phase references.

## Output

Summarize:

- immutability status
- layer-boundary violations
- validation coverage gaps
- serialization status
- total violations and warnings

