# Phase 5 Handoff

> **From**: Phase 4 agent
> **To**: Phase 5 agent
> **Date**: 2026-05-01
> **Branch**: `post-recovery-plan_phase-4` (off `post-recovery-plan_phase-3`)
> **Plan**: `dev/plans/post_recovery_plan.md`

---

## Skills to Load Before Starting

- `Aut_Faciam`
- `taichi-gpu-sim` (Phase 5 substitutes the imported J2 radial-return implementation with an algo2code-generated equivalent — Taichi `@ti.func` JIT budget rules apply)
- `pymc-bayesian-modeling` not relevant; `sympy` light (algorithmic expressions in algpseudocode).

---

## Phase 4 Completion Summary

| Task ID | Title | Tests (pass/total) | Failing Tests |
|---------|-------|--------------------|---------------|
| P4-1 | frontend/math_parser.py wrapping nrpylatex | 4/4 (test_p4_1) | none |
| P4-2 | symbolic/bridge.py adapter | 6/6 (test_p4_2) | none |
| P4-3 | Wire math parser into frontend pipeline | 5/5 (test_p4_3) + 56/56 existing frontend | none |
| P4-4 | test_nrpylatex_round_trip.py round-trip suite | 4/4 deliverable + 4/4 meta-spec | none |
| P4-5 | dev/examples/svk_latex_math.tex + README inventory | 3/3 (test_p4_5) | none |

**Overall**: 26 task-dedicated tests pass; 1804/1804 fast suite green; `pytest -m docs` collects 24 nodeids (8 P7-3..6 + 6 P3 + 4 round-trip + 6 meta-spec / Phase-3 stubs). 0 failures.

---

## Architecture and State After Phase 4

### New modules

- `packages/mechdsl-core/src/mechdsl/frontend/math_parser.py` — wraps `nrpylatex.parse_latex`; defines `parse_math`, `MathParseError`, `MathParseResult`, `IndexClassification`, `enforce_index_convention`. Sole nrpylatex consumer outside the bridge.
- `packages/mechdsl-core/src/mechdsl/symbolic/bridge.py` — `convert(name, indexed_symbol, classification) -> SymbolicNode` plus bulk `convert_namespace`. Read-only against `mechdsl.symbolic.{kinematics,constitutive,convected}` (verified by attribute snapshot test).

### Modified modules

- `packages/mechdsl-core/src/mechdsl/frontend/__init__.py` — adds `parse_with_math`, `has_math_block`, `has_math_block_in_source`, `_extract_math_blocks`. Directive-only inputs return `parse(source)` unchanged (verified by equality assertion).
- `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_2.py` — docs allowlist widened to admit `tests/test_compile_latex_docstring.py` and `tests/test_nrpylatex_round_trip.py` as legitimate doc-tier homes (second occurrence of `integration_break` pattern from P3-1).

### New tests / examples

- `packages/mechdsl-core/tests/test_nrpylatex_round_trip.py` — 4 `@pytest.mark.docs @pytest.mark.integration` tests (SVK PK1 surrogate, J2 yield norm contraction, two-point F^{iI}, full frontend pipeline). Permanent regression guard (lives at canonical tests/ root, not under plan_tests/).
- `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_*.py` — 16 stubs across 5 files, all converted from skip-stubs to real assertions during exec.
- `dev/examples/svk_latex_math.tex` — example exercising the math grammar end-to-end through `parse_with_math`. README listed.

### Public APIs added

```python
from mechdsl.frontend import parse_with_math, has_math_block
from mechdsl.frontend.math_parser import parse_math, MathParseError, IndexClassification
from mechdsl.symbolic.bridge import convert, convert_namespace, SymbolicNode, BridgeError
```

`parse_with_math(source)` returns `parse(source)` augmented (when math present) with::

    context["math"] = {
        "blocks": [<raw block text>, ...],
        "tensors": {<name>: SymbolicNode, ...},      # bridge output
        "namespace": {<name>: nrpylatex IndexedSymbol|Constant, ...},
        "classifications": {<name>: IndexClassification, ...},
    }

---

## Assumptions & Deferrals

| Decision | Where it applies | Rationale | Risk if wrong |
|----------|-----------------|-----------|---------------|
| Closed-form SVK PK1 / J2 yield round trip is **deferred** | test_nrpylatex_round_trip.py | nrpylatex 1.4.0 does not register `\det` / `\log{}`; `\sqrt(s:s)` over a deviator is not parseable. The plan's stronger acceptance criterion ("emitted Taichi residual matches handwritten reference within tolerance") cannot land at this layer without a nrpylatex grammar extension. The deliverable instead pins the **import-chain round trip** with documented surrogates. | Low at this stage; the plan permits in-scope extension and the import chain is the necessary prerequisite. A future phase can replace surrogates once `\det` / `\log{}` are registered. |
| Tensor rank encoded via U/D suffix in declared symbol name (`FUU` ↔ rank-2 F) | math_parser docstring + tests | Forced by nrpylatex 1.4.0 grammar; `--rank N` does not exist. Documented in module docstring + supported-subset table. | Low — exposed contract; users get `MathParseError` Phase-4 on misuse. |
| `% declare` directives prepended to every `$...$` block | parse_with_math | nrpylatex requires declarations in the same parse as the using expression. mechdsl uses `% mechanics`, no namespace clash. | Low — current model treats each $...$ block as independent; multi-block scenarios with shared declarations work because declarations are prepended unconditionally. |
| Math-block regex skips `%`-comment lines | _extract_math_blocks | Caught during P4-5 example integration: comment text legitimately mentions `$...$` syntax in prose. Without the skip, prose `$...$` instances tripped the parser. | Low — clear line-based rule; fast suite confirms no regression. |

---

## Recurring failure mode flagged

The P2-2 docs-collection invariant has tripped twice now (P3-1, P4-5) when a phase introduces a new doc-tier home outside `recovery_plan_latex_contract/test_p7_*`. The allowlist widens cleanly, but if a future phase adds another doc-tier home, the same fix recurs. Consider replacing the explicit prefix list with a registry pattern (e.g. read allowed prefixes from a tracker file or marker plugin). Not addressed in Phase 4 — flagged here for Phase 6 cleanup work.

---

## Next Phase Direction (Phase 5 — algo2code radial-return substitution)

Plan §lines 230+:

- New `dev/algorithms/radial_return_j2.tex` — algpseudocode source for J2 radial-return with power-law hardening.
- algo2code emits a Taichi `@ti.func` for radial-return; budget gate ≤ 512 unrolled lines per `@ti.func` (07-CONVENTIONS).
- Default `lib/plasticity.py` switches to the algo2code-generated path; `MECHDSL_USE_IMPORTED_RR=1` reverts to imported.
- Parity test: imported vs algo2code, identical stress/internal-variable updates within tolerance for elastic / elastoplastic / unloading load steps.
- Design-doc note in `06-PLASTICITY.md` (or `07-CONVENTIONS.md`) documenting the substitution + fallback.

Higher complexity than Phase 4. Sonnet/Opus subagent dispatch is expected at exec time.

---

## Open Items / Follow-ups

- None blocking Phase 5.
- Post-merge of the Phase 4 PR: `pytest -m docs` will collect 24 nodeids (was 17 after Phase 3); the new dedicated `docs-tests` CI job (Phase 2 P2-3) will pick them up.
- Track the recurring P2-2 allowlist widening pattern as a Phase 6 cleanup candidate.
