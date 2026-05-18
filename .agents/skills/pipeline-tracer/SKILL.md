---
name: pipeline-tracer
description: Trace a MechDSL input through ProblemIR, ElementIR, einsum planning, and Taichi code emission. Use when debugging pipeline behavior or understanding what a configuration produces.
---

# Pipeline Tracer

This skill is diagnostic and read-only.

If `$ARGUMENTS` is empty, trace both default elastic and plastic configurations.

## Workflow

1. Build a `ProblemIR` for the requested configuration.
2. Dump the serialized `ProblemIR`.
3. Run FE localization and inspect the resulting `ElementIR`.
4. Optimize each extracted einsum contraction and capture FLOPs, line counts, tier classification, and budget status.
5. Emit code and summarize the generated source: line count, major functions, content hash, and static-vs-runtime loop choices.
6. Check what reference solvers and golden files exist for that configuration.
7. Cross-check consistency between layers.

Use `uv run python -c "..."` for inline tracing commands.

## Output

Provide a layer-by-layer trace with clear failures, plus any cross-layer mismatches you find.

