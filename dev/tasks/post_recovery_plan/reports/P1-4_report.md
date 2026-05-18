# Task P1-4: Emit f_ext init Taichi kernel — Complete

## Implementation Summary

Added `emit_neumann_f_ext_kernel(ctx, NeumannKernelSpec) -> str` to `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py`. Each Neumann BC produces one `init_f_ext_from_neumann_<bc>` kernel that zeroes `f_ext` globally then writes pre-distributed per-node force on tagged surface nodes.

Public additions:
- `NeumannKernelSpec(bc_name, surface_tag, per_node_force)` frozen dataclass
- `emit_neumann_f_ext_kernel(ctx, spec) -> str` returning the emitted kernel name
- `_sanitize_kernel_suffix` for directive-supplied name → Python identifier

## Plan Deviation

Plan file layout was `codegen/taichi_printer/boundary.py` (subpackage). Repo has `codegen/taichi_printer.py` (single module). Function placed inside the existing module instead of restructuring the codegen layer — noted in JSON / gates.

## Gate History

- **Gate A:** 1 attempt → Pass. Plan acceptance #1–3 met; folder-layout deviation flagged with rationale.
- **Gate B:** 1 attempt → Pass. Index partitioning honoured; JIT budget probe ≤50 lines (vs 2000 cap). One minor (`_fmt_float` int-literal behaviour) noted.
- **Gate C:** 2 attempts. First fail: `test_gap` — assertions expected `-250.0` literal, emitter writes `-250` (deterministic format strips trailing zeros; Taichi coerces). Resolved by aligning assertions; second attempt 8/8.

## Failure Patterns

`test_gap` this task: assertion mismatch with deterministic float format. No prior-phase precedent — this was new.

## Files Changed

- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` — `+105 LOC` (new emitter)
- `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p1_4.py` — 8 tests
- Task JSON, gates, tracker updates

## Test Evidence

```
test_p1_4.py: 8/8 (0.07s)
fast suite:   1699/1699 (53.89s)
mypy + ruff:  clean on changed files
```

## Commit

`6547a8c` — feat(codegen): emit Neumann f_ext init Taichi kernel (P1-4)

## Open Questions

- Multi-BC merging: each BC emits its own kernel that *zeroes* `f_ext` first, so calling kernels back-to-back loses earlier contributions. P1-5 (façade) needs to decide: emit one merged kernel, or emit a no-zero variant to be called after a single zero kernel. Current emission supports the single-BC golden test (P1-7) directly; multi-BC pipeline integration belongs to P1-5.
- Symbolic-traction registry plumbing through `compile_latex` is still open from P1-3.

## Downstream Impact

- P1-5 (#211) unblocked — façade wires the emitted kernel into `compile_latex` return.
- P1-7 (#213) unblocked — golden fixture asserts emitted source for a Neumann BC.
