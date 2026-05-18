## Follow-up / deferred items surfaced this session

### Code-level gaps (P7 work logged but not addressed)

1. **Boundary-directive flow into emitted code** (P7-2 minor, `test_p7_2.py:142-144`)
   - LaTeX `% mechanics boundary load --type neumann --traction "0 0 -1000"` is placeholder. Numeric `f_ext` injected directly by test.
   - Codegen does not consume Neumann directives → emitted `f_ext` initialization missing.
   - Closing requires P2-1 façade extension or new phase task.

2. **NRPyLaTeX math grammar integration** (P7-6 review residual)
   - Only `% mechanics` directives parsed today. Arbitrary LaTeX tensor math (e.g. `$P_{iJ} = \mu (F_{iJ} - F_{iJ}^{-T}) + \lambda \log(J) F_{iJ}^{-T}$`) does not round-trip through `compile_latex`.
   - `nrpylatex` dependency wired in `pyproject.toml` but never imported under `src/`.
   - Future plan candidate.

3. **Radial-return substitution via algo2code** (P6-4 deferral, plan lines 323-335)
   - Imported J2 radial-return path stays default. Algo2code-generated equivalent deferred until R2/R3 settle.
   - Now eligible since R2/R3 closed. Candidate for next plan.

### Test-layer gaps (informational, non-blocking)

4. **`test_p7_4.py:92` `notes[0]` indexing**
   - `_candidate_note_paths()` matches both `frontend_drift_history.md` and `recovery_status_2026_04.md`. Test 1 inspects only `notes[0]`. Combined invariant via Test 2 still catches accidental deletion.
   - Suggested fix: iterate `notes` for one referenced by plan rather than indexing `[0]` (3-line change).

5. **`test_p7_3.py:50` first-occurrence ordering check**
   - Uses `text.find()` substring offsets. A future contributor could satisfy with prose mention of `compile_latex(` near top while keeping programmatic example as first runnable block.
   - Inherent docs-tier weakness; tighten only if regression occurs.

6. **`test_p7_3.py:117` README path matching**
   - Hardcoded `f"dev/examples/{name}"` substring. Breaks if README adopts `./dev/examples/` or absolute prefix. Low impact.

7. **`dev/examples/README.md` lost `## Inventory` anchor** (P7-3 review)
   - Any external `#inventory` link breaks. No evidence such links exist.

8. **`test_p7_2.py:71` `_import_generated_module` constant name**
   - Uses `name="gen_p7_2"` constant. Would shadow if test parametrized in future. Currently safe (single test).

9. **`test_p7_2.py:142-144` traction-string-gap comment lacks forward pointer**
   - Comment says "placeholder for symbolic binding" but no link to closing phase. Add forward-pointer when item 1 lands.

10. **`test_p7_6.py` length comment**
    - Review is 343 lines; spec hint was 100-250. Could trim 50-80 lines by merging per-pillar evidence sub-bullets. Optional, not required.

### Process / infra items

11. **`test_phase6_exit.py` line-number whitelist** (Phase 5 lesson, carried)
    - `_INTENTIONAL_CLEANUP_MATCHES` hard-codes line numbers in `test_emission_verification.py`. Phase 7 did not break it but the structural fragility persists. Replace with regex/marker matching when next under maintenance.

12. **Helper duplication** (P7-2 Gate B optional improvement)
    - `_import_generated_module` duplicated between `test_p7_2.py` and `test_e2e_taichi.py`. Refactor to `tests/_e2e_helpers.py` once a third caller appears. Family-split rule currently forbids cross-import.

13. **GitNexus index stale**
    - PostToolUse hook reported stale every commit. Run `npx gitnexus analyze` to refresh — needs explicit user authorization since it is not in this session's commit chain.

14. **Test-rules `docs` tier mismatch**
    - `.claude/rules/tests.md` registers only `slow`/`gpu`/`e2e` markers. P7-3..P7-6 task JSONs carry `test_plan.tier: docs` but pytest configuration has `tier:docs` GitHub label only — no `docs` pytest marker. Stubs use `@pytest.mark.integration` as substitute. Reconcile by adding `docs` marker or remapping tier.

15. **`f_ext` boundary-API documentation gap**
    - The pattern "LaTeX directives populate `BoundaryCondition` slots; numeric `f_ext` provided separately by caller" is the current contract but not documented in `compile_latex` docstring. Add a one-paragraph note to `mechdsl/__init__.py:33` `compile_latex` docstring describing the BC handoff.

### Governance items

16. **Plan B execution status**
    - `dev/tasks/PLAN-B/_SUPERSEDED.md` correctly distinguishes "execution source superseded" from "work landed in tree". Plan B benchmarks/code remain runtime-active; planning artifact archived. Future contributor may need clarification on which Plan B sub-deliverables are still live.

17. **`pre-existing 9 failures` discrepancy**
    - Earlier in session, `test_p6_1.py`/`test_p6_2.py`/`test_p6_3.py` reported 9 algo2code-import failures pre-existing on baseline `77e1498`. Post-P7-1, broader smoke shows 0 failures. Likely resolved by `uv sync --all-packages` running between sessions. Worth confirming the algo2code workspace install is now stable in CI.

### Priority ranking

| Priority | Items |
|---|---|
| **High** (close before next plan) | 1 (boundary-directive flow), 14 (test marker mismatch), 15 (BC docstring) |
| **Medium** (next-plan candidates) | 2 (NRPyLaTeX), 3 (radial-return), 4 (test_p7_4 indexing), 11 (line-whitelist refactor) |
| **Low** (informational) | 5, 6, 7, 8, 9, 10, 12, 13, 16, 17 |