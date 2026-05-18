# Task P1-5: Extend compile_latex façade — Complete

## Implementation Summary

`compile_latex` now returns an `ArtifactBundle` whose optional `f_ext_kernel` field carries the emitted Taichi `init_f_ext_from_neumann_<bc>` kernel for every Neumann BC with numeric traction. Symbolic-string traction (legacy `t_bar` form) leaves `f_ext_kernel` at `None`, preserving back-compat with 30+ existing fixtures.

Changes:
- `ArtifactBundle.f_ext_kernel: str | None = None` added; `to_dict` / `from_dict` round-trip.
- New sibling emitter `emit_neumann_f_ext_kernel_for_ir(ctx, bc_name, surface_tag, traction)` in `taichi_printer.py` — bakes traction as deterministic float literals, takes `f_factor = face_area / n_face_nodes` as a runtime kernel arg.
- `compile_latex` filters Neumann BCs with tuple traction, emits one kernel per BC, rebuilds bundle via `dataclasses.replace`.

## Plan Deviation

P1-4's literal-baked emitter expects per-node force pre-distributed (mesh-aware). The façade has no mesh at compile time, so a sibling parametric emitter was added. Both forms coexist with explicit docstrings citing which task / use case each one serves.

## Gate History

- **Gate A:** 1 attempt → Pass.
- **Gate B:** 1 attempt → Pass. IR discipline preserved; round-trip verified; index-partitioning rule honoured.
- **Gate C:** 1 attempt → Pass. 5/5 dedicated, 1704/1704 full fast suite (+5 vs P1-4).

## Failure Patterns

None this task. No prior-phase pattern recurrence.

## Files Changed

- `packages/mechdsl-core/src/mechdsl/__init__.py` (+34 LOC: emitter wiring + docstring)
- `packages/mechdsl-core/src/mechdsl/codegen/artifact.py` (+10 LOC: new field + serialization)
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` (+62 LOC: parametric emitter)
- `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p1_5.py` (5 tests, façade integration)
- Task JSON, gates, tracker

## Test Evidence

```
test_p1_5.py: 5/5 (0.47s)
fast suite:   1704/1704 (57.08s)
mypy + ruff:  clean on changed files
```

## Commit

`5db6439` — feat(facade): surface Neumann f_ext kernel through compile_latex (P1-5)

## Open Questions

- Multi-BC emission: `compile_latex` emits one kernel per Neumann BC; each kernel zeroes `f_ext` first, so calling them back-to-back at runtime overwrites. Driver-side pattern: call exactly one Neumann kernel per Newton solve (typical case), or refactor to `init_then_accumulate` form if multi-BC is needed. Not blocking; documentable as a runtime convention.
- Symbolic-traction registry plumbing through `compile_latex` still open (carried from P1-3). Symbolic BCs leave `f_ext_kernel` at `None` — caller still uses the imported numeric-injection path. Resolution belongs to a follow-up task or Plan B once symbolic loads see broader use.

## Downstream Impact

- P1-6 (#212) unblocked — test_p7_2 rewrite to use the directive-only path.
- P3-1 unblocked from cross-phase dep — façade contract is stable; docstring update can land in Phase 3.
- P1-7 (#213) unaffected — uses the literal-baked emitter from P1-4 directly.
