---
name: convention-checker
description: Audit MechDSL code for domain-convention violations such as Voigt ordering, sign conventions, index usage, and JIT budget risks. Use after editing kernels, constitutive models, or codegen.
---

# Convention Checker

This skill is read-only.

If `$ARGUMENTS` is empty, inspect all Python files under `packages/mechdsl-core/src/mechdsl/`.

Read `dev/design_docs/07-CONVENTIONS.md` and any matching rule files under `.agents/rules/` for the paths being checked.

## Checks

1. Voigt ordering
   Flag hardcoded orderings that are not `[xx, yy, zz, xy, xz, yz]` or `[11, 22, 33, 12, 13, 23]`.
   Flag factor-of-two shear handling that suggests engineering Voigt notation.
2. Sign convention
   Pressure should be compression-positive, so watch for missing negation.
3. Index convention
   Lowercase indices are spatial, uppercase are material, and mixed `F_{iI}` stays two-point.
4. `ti.static` vs runtime loops
   Physics indices stay static; mesh-like indices stay runtime.
5. JIT budget
   Estimate unrolled cost and flag likely violations of the project limits.

## Output

Report findings grouped by category using:

- `Clean`
- `Warning`
- `Violation`

End with a count summary.

