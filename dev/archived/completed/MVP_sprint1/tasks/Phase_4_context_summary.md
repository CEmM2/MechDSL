# Phase 4 Context Summary — Pipeline Wiring (`compile()`)

## Conventions

- All information flows through explicit IRs: **Mechanics IR → Element IR → Einsum IR**
- IRs are immutable dataclasses, validated at construction
- `ArtifactBundle` stores all pipeline intermediates for debugging and regression testing
- Per CLAUDE.md: "Never bypass an IR layer"

## Key Principles

- The `compile()` function extracts the `_run_full_pipeline()` pattern already used in `test_e2e.py` (lines 74-88) into a proper public API.
- The pipeline is: `localise_and_optimize(problem_ir)` → `ArtifactBundle.from_pipeline()` → `emit(bundle)` → return bundle with emitted_source.
- `compile()` is a pure function: same input → same output (deterministic).
- The function goes in `codegen/__init__.py` and is re-exported from `mechdsl.__init__.py`.

## Pre-resolved Design Decisions

- `compile(problem_ir: ProblemIR) -> ArtifactBundle` — single function, single return
- The returned `ArtifactBundle` contains: `problem_ir_dict`, `element_ir_summary`, `contraction_plans`, `emitted_source`, `metadata`
- To include `emitted_source`, the bundle must be reconstructed (ArtifactBundle is frozen) — create new instance with source field populated
- No configuration parameters for MVP — the compile function uses defaults from each pipeline stage

## Downstream Impact

- Phase 5 modifies the emitter — after P5-T3, `compile()` will produce different output (with main block + postprocess)
- Phase 6 E2E test uses `compile()` as the entry point: `compile(problem_ir).emitted_source` → write to file → execute
- Golden-file tests that use `compile()` will need golden file regeneration after Phase 5

## Key Files

| File | Current state | Action |
|------|--------------|--------|
| `src/mechdsl/codegen/__init__.py` | 1-line docstring | Add compile() function (~25 lines) |
| `src/mechdsl/__init__.py` | Version string only | Add `from mechdsl.codegen import compile` |
| `src/mechdsl/lowering/fe_localise.py` | Read only | Called by compile() via localise_and_optimize |
| `src/mechdsl/codegen/taichi_printer.py` | Read only | Called by compile() via emit() |
| `src/mechdsl/codegen/artifact.py` | Read only | ArtifactBundle.from_pipeline() |
| `tests/test_e2e.py` | Existing pipeline tests | Read only (reference for _run_full_pipeline pattern) |
| `tests/test_compile_pipeline.py` | Does not exist | New test file |
