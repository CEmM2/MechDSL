# Task P1-3: Lower Neumann BC to per-node force contributions — Complete

## Implementation Summary

Built `packages/mechdsl-core/src/mechdsl/lowering/boundary.py` — bridges the IR-layer `BoundaryCondition` (extended in P1-1) to the existing per-node-force codegen primitive (`compile_neumann` in `codegen/boundary_codegen.py`). No quadrature logic duplicated; the lowering pass is a thin adapter.

Public API:
- `lower_neumann(bc, mesh, traction_registry=None) -> NeumannBC` — resolves surface tag + traction, delegates to `compile_neumann`.
- `per_node_contributions(...) -> list[NodalForceContribution]` — sparse output list with `zero_tol`.
- `resolve_traction_vector(...)` — traction-symbol resolution helper.
- `NodalForceContribution` — frozen `(node_id, force)` dataclass.

## Gate History

**Gate A:** 1 attempt → Pass. Acceptance criteria #1–4 met directly via the new module.
**Gate B:** 1 attempt → Pass. IR discipline preserved; index partitioning rule honoured. One TC003 (Mapping import) caught and fixed inside the same Gate B pass.
**Gate C:** 9/9 dedicated tests pass; full mechdsl-core fast suite 1691/1691 (up +9 from P1-2's 1682). mypy + ruff clean.

## Failure Patterns

None this task. No matches against earlier P1-1/P1-2 failure modes (P1-1 had `integration_break` from pre-existing fixtures + `style_violation` on TODO markers; both resolved before P1-3 started).

## Files Changed

- `packages/mechdsl-core/src/mechdsl/lowering/boundary.py` — new module (122 LOC)
- `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p1_3.py` — 9 unit tests replacing scaffold stub
- `dev/tasks/post_recovery_plan/json/P1-3.json` — status → done
- `dev/tasks/post_recovery_plan/gates/phase_1_gates.md` — gate history appended
- `dev/tracking/tasks-tracker_post_recovery_plan.md` — row updated

## Test Evidence

```
uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p1_3.py -v
9 passed in 0.45s

uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -q
1691 passed, 95 skipped, 97 deselected, 2 warnings in 55.93s
```

## Commit

`c74538c` — feat(lowering): lower Neumann BoundaryCondition to per-node forces (P1-3)

## Open Questions

- `compile_neumann` derives face area from `face_name[0]` (axis prefix `x|y|z`). A user-defined `surface_tag` not starting with one of those would currently raise from `compile_neumann`. Documented in module docstring; broader sideset support is out of scope for P1-3 and would belong to a Plan B mesh-adapter task.
- Symbolic-string traction registry surface is exposed as a parameter, not yet plumbed through the façade. P1-5 may want to surface it through `compile_latex(..., traction_registry=...)` or rely on the directive-driven numeric form alone — this decision is captured for P1-5's review.

## Downstream Impact

- P1-4 unblocked: codegen Taichi `f_ext` emitter consumes the lowering output (`NeumannBC.force` array) — same shape as `compile_neumann`'s existing return.
- P1-7 (golden test) will exercise the full pipeline through this lowering layer.
