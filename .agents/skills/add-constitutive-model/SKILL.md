---
name: add-constitutive-model
description: Scaffold a new constitutive model in `mechdsl.symbolic`, register it, add tests, and validate it. Use when adding or extending a material model in MechDSL.
---

# Add Constitutive Model

Read these first:

- `dev/design_docs/07-CONVENTIONS.md`
- `dev/design_docs/01-ARCHITECTURE.md`
- `.agents/rules/symbolic.md`

Use `$ARGUMENTS` as the model name.

## Workflow

1. Classify the model as hyperelastic or dissipative.
2. Implement `packages/mechdsl-core/src/mechdsl/symbolic/models/<model_name>.py`.
   Use `svk.py` for hyperelastic patterns and `j2_power_law.py` for dissipative patterns.
3. Register the model in `packages/mechdsl-core/src/mechdsl/symbolic/models/__init__.py`.
4. Update the supported-subset validation only in executable code, not in `dev/design_docs/`.
5. Add `packages/mechdsl-core/tests/test_<model_name>.py`.
   Include symmetry checks, simple deformation-state checks, and either:
   - energy consistency for hyperelastic models, or
   - elastic-predictor recovery for dissipative models.
6. Validate with:
   - `uv run pytest packages/mechdsl-core/tests/test_<model_name>.py -v`
   - `uv run ruff check packages/mechdsl-core/src/mechdsl/symbolic/models/<model_name>.py`

## Constraints

- Produce PK2 stress and the correct tangent form for the model class.
- Use tensorial Voigt ordering with unscaled shears.
- Keep symbolic expressions symbolic.
- If a design doc would need updating, note that explicitly in the final report instead of editing `dev/design_docs/`.

