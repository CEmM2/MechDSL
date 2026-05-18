# Plan: Post-Recovery Follow-up — Close P7 Deferrals and Surface Next-Plan Candidates

## Context

Recovery Phase 7 (R6) closed but logged 17 follow-up items spanning code-level gaps,
test-layer fragility, infra debt, and governance reconciliation. Three items are
flagged High (must close before next plan): boundary-directive flow into emitted code,
test marker tier mismatch (`docs`), and the missing `compile_latex` docstring note on
the `f_ext` BC handoff contract. Four items are Medium (next-plan candidates), and ten
are Low (informational).

This plan organizes the deferrals into sequential phases. High-priority phases (1-3)
must land before the next major plan starts. Medium phases (4-6) deliver the
next-plan candidates surfaced in the recovery session — NRPyLaTeX math grammar,
algo2code radial-return substitution, and test-layer hardening. Phase 7 sweeps the Low
items together as a single polish/governance pass.

The plan does not introduce new scope: every phase maps directly to one or more of the
17 items in the original follow-up log. Items deemed informational-only (no code
change required) are documented under Out of Scope.

### Original prompt

```markdown
## Follow-up / deferred items surfaced this session

### Code-level gaps (P7 work logged but not addressed)

1. Boundary-directive flow into emitted code (P7-2 minor, test_p7_2.py:142-144)
   - LaTeX `% mechanics boundary load --type neumann --traction "0 0 -1000"` placeholder.
   - Codegen does not consume Neumann directives → emitted f_ext init missing.
   - Closing requires P2-1 façade extension or new phase task.

2. NRPyLaTeX math grammar integration (P7-6 review residual)
   - Only `% mechanics` directives parsed today. Arbitrary LaTeX tensor math
     does not round-trip through compile_latex.
   - nrpylatex dependency wired in pyproject.toml but never imported under src/.

3. Radial-return substitution via algo2code (P6-4 deferral)
   - Imported J2 radial-return path stays default. Algo2code-generated equivalent
     deferred until R2/R3 settle. Now eligible since R2/R3 closed.

### Test-layer gaps (informational, non-blocking)

4. test_p7_4.py:92 notes[0] indexing — iterate notes for one referenced by plan.
5. test_p7_3.py:50 first-occurrence ordering — text.find() offsets fragile.
6. test_p7_3.py:117 README path matching — hardcoded f"dev/examples/{name}".
7. dev/examples/README.md lost ## Inventory anchor.
8. test_p7_2.py:71 _import_generated_module constant name shadow risk.
9. test_p7_2.py:142-144 traction-string-gap comment lacks forward pointer.
10. test_p7_6.py length 343 lines, hint was 100-250.

### Process / infra items

11. test_phase6_exit.py line-number whitelist — replace with regex/marker.
12. Helper duplication — _import_generated_module across test_p7_2.py,
    test_e2e_taichi.py. Refactor when third caller appears.
13. GitNexus index stale — run npx gitnexus analyze.
14. Test-rules docs tier mismatch — .claude/rules/tests.md registers only
    slow/gpu/e2e markers. P7-3..P7-6 task JSONs carry test_plan.tier: docs
    but no docs pytest marker. Stubs use @pytest.mark.integration as substitute.
15. f_ext boundary-API documentation gap — pattern "LaTeX directives populate
    BoundaryCondition slots; numeric f_ext provided separately" undocumented in
    compile_latex docstring.

### Governance items

16. Plan B execution status — _SUPERSEDED.md distinguishes execution-source
    superseded from work-landed-in-tree. May need clarification.
17. pre-existing 9 failures discrepancy — algo2code-import failures pre-existing
    on baseline 77e1498. Post-P7-1 smoke shows 0. Confirm CI stability.

### Priority ranking
| High   | 1, 14, 15            |
| Medium | 2, 3, 4, 11          |
| Low    | 5, 6, 7, 8, 9, 10, 12, 13, 16, 17 |
```

---

## Phase 1: Boundary-directive flow into emitted code

**Goal** — Wire `% mechanics boundary load --type neumann --traction "..."` directives
through to generated Taichi `f_ext` initialization so end-to-end LaTeX → solver runs
without a numeric injection helper.

**Files**
- `packages/mechdsl-core/src/mechdsl/frontend/directives.py` — extend Neumann
  directive parser to capture traction vector + tagged surface set
- `packages/mechdsl-core/src/mechdsl/ir/problem.py` — ensure `BoundaryCondition`
  slot carries traction vector and surface tag (extend if missing)
- `packages/mechdsl-core/src/mechdsl/lowering/boundary.py` — new (or extended)
  module: lower Neumann BC to per-node force contributions on tagged surface
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer/boundary.py` — emit
  `f_ext` initialization Taichi kernel from lowered Neumann BC
- `packages/mechdsl-core/src/mechdsl/__init__.py` — façade `compile_latex`
  surfaces emitted `f_ext` init alongside residual/tangent kernels (P2-1 extension)
- `packages/mechdsl-core/tests/test_p7_2.py` — replace numeric `f_ext` injection
  at lines 142-144 with directive-only path; remove placeholder comment
- `packages/mechdsl-core/tests/test_boundary_neumann.py` — new test: golden
  reference for emitted `f_ext` Taichi kernel from Neumann directive

**Acceptance criteria**
- `compile_latex` consuming a `% mechanics boundary load --type neumann` directive
  emits a Taichi kernel that initializes `f_ext` matching numeric reference within
  default tolerance.
- `test_p7_2.py:142-144` no longer constructs `f_ext` directly; pipeline output is
  the sole source of `f_ext` values.
- New `test_boundary_neumann.py` golden test passes for traction
  `"0 0 -1000"` on a tagged hex8 face set.
- `test_p7_2.py` placeholder comment removed (closes follow-up item 9).

**Risks**
- BC IR slot may not currently carry surface-tag information — mitigation: extend
  `BoundaryCondition` schema as part of this phase, validate in IR construction.
- Façade signature change risks breaking existing callers — mitigation: keep
  current return shape as default; add new `f_ext_kernel` field as optional.

---

## Phase 2: Test marker tier reconciliation (`docs`)

**Goal** — Resolve mismatch between `test_plan.tier: docs` in P7-3..P7-6 task JSONs
and the absence of a `docs` pytest marker, so tier-routed selection works without
the `@pytest.mark.integration` substitute.

**Files**
- `.claude/rules/tests.md` — register `docs` marker alongside `slow`, `gpu`, `e2e`
- `pyproject.toml` (root or `packages/mechdsl-core/pyproject.toml`) — declare
  `docs` marker under `[tool.pytest.ini_options].markers`
- `packages/mechdsl-core/tests/test_p7_3.py` — replace
  `@pytest.mark.integration` with `@pytest.mark.docs`
- `packages/mechdsl-core/tests/test_p7_4.py` — same swap
- `packages/mechdsl-core/tests/test_p7_5.py` — same swap (if present)
- `packages/mechdsl-core/tests/test_p7_6.py` — same swap
- `.github/workflows/*.yml` — confirm `tier:docs` GitHub label maps to a
  selector running `pytest -m docs` (add or correct as needed)

**Acceptance criteria**
- `uv run pytest -m docs` selects exactly the P7-3..P7-6 doc-tier tests and no
  others.
- `uv run pytest --markers` lists `docs` alongside `slow`, `gpu`, `e2e`.
- No `@pytest.mark.integration` decorators remain on doc-tier tests in
  `test_p7_*` files.
- CI tier-docs job (or label-routed selector) executes the renamed marker.

**Risks**
- Existing GitHub Actions selector may rely on `integration` marker — mitigation:
  audit workflow files and update selector before deleting marker references.

> AMBIGUITY: Could alternatively remap `tier: docs` task-JSON value to
> `integration` marker rather than introducing a new marker. Plan adopts
> add-marker route since `tests.md` lists tiers explicitly; remap is reversible
> if the marker proliferation becomes a concern.

---

## Phase 3: `compile_latex` boundary-condition handoff docstring

**Goal** — Document the contract "LaTeX directives populate `BoundaryCondition`
slots; numeric `f_ext` is supplied separately by caller" inside the public
`compile_latex` docstring so callers do not have to read tests to discover it.

**Files**
- `packages/mechdsl-core/src/mechdsl/__init__.py` — add a paragraph to
  `compile_latex` docstring (around line 33) covering BC handoff, current
  Dirichlet/Neumann support level, and the `f_ext` provisioning expectation
- `packages/mechdsl-core/tests/test_compile_latex_docstring.py` — new (or
  extended) docstring-presence test asserting the BC handoff paragraph exists
  and references `BoundaryCondition`

**Acceptance criteria**
- `compile_latex.__doc__` contains a paragraph mentioning `BoundaryCondition`
  and the `f_ext` caller-provisioning contract.
- Docstring test asserts the paragraph remains present (regression guard).
- `uv run pydocstyle` (or existing docstring linter) passes on the modified
  module.

**Risks**
- Docstring may be regenerated from a template — mitigation: edit the source
  template if one exists; otherwise edit the module directly.
- Phase 1 may change the contract (if BC flow lands first) — mitigation:
  sequence Phase 3 after Phase 1, or write the docstring against the
  post-Phase-1 contract from the start.

---

## Phase 4: NRPyLaTeX math grammar integration

**Goal** — Allow arbitrary LaTeX tensor math (e.g. `$P_{iJ} = \mu (F_{iJ} - F_{iJ}^{-T}) +
\lambda \log(J) F_{iJ}^{-T}$`) to round-trip through `compile_latex` by importing the
already-declared `nrpylatex` dependency in the frontend layer.

**Files**
- `packages/mechdsl-core/src/mechdsl/frontend/math_parser.py` — new module:
  wrap `nrpylatex` parser, normalize index conventions (lowercase spatial,
  uppercase material), emit symbolic expressions consumable by
  `mechdsl.symbolic`
- `packages/mechdsl-core/src/mechdsl/frontend/__init__.py` — wire math parser
  into the top-level frontend pipeline so `$...$` blocks reach symbolic
- `packages/mechdsl-core/src/mechdsl/symbolic/bridge.py` — adapter from
  nrpylatex AST to mechdsl symbolic expression types (extend if exists)
- `packages/mechdsl-core/tests/test_nrpylatex_round_trip.py` — new test
  covering at minimum: SVK first-PK stress expression, J2 yield function,
  two-point tensor `F_{iI}`
- `dev/examples/svk_latex_math.tex` — new example exercising math grammar
- `dev/examples/README.md` — list new example under inventory

**Acceptance criteria**
- A LaTeX file containing a math-only constitutive expression compiles via
  `compile_latex` without `% mechanics constitutive` directive.
- Round-trip test verifies emitted Taichi residual matches handwritten
  reference within tolerance.
- Index convention enforcement holds: mixed `F_{iI}` produces correct
  spatial/material distinction at lowering time.
- New example in `dev/examples/` runs via the documented path.

**Risks**
- `nrpylatex` may emit AST shapes incompatible with mechdsl symbolic types
  — mitigation: bridge module isolates conversion; failure cases raise with
  explicit "unsupported NRPyLaTeX node" error pointing at this phase.
- Index convention conflict (NRPyLaTeX defaults vs 07-CONVENTIONS) —
  mitigation: post-process AST to enforce mechdsl convention before symbolic
  ingestion; document mapping table in module docstring.
- Performance regression on parse path — mitigation: only invoke math parser
  for `$...$` blocks; directive-only files skip it.

---

## Phase 5: Algo2code radial-return substitution

**Goal** — Replace the imported J2 radial-return implementation with an
algo2code-generated equivalent now that R2/R3 have closed and the substitution
gate is open.

**Files**
- `dev/algorithms/radial_return_j2.tex` — new algpseudocode source for the
  J2 radial-return algorithm with power-law hardening
- `packages/algo2code/tests/test_radial_return_codegen.py` — new test:
  algo2code emits Taichi function matching reference behavior
- `packages/mechdsl-core/src/mechdsl/lib/plasticity.py` — switch default
  radial-return path to algo2code-generated function; keep imported version
  as fallback under a feature flag `MECHDSL_USE_IMPORTED_RR`
- `packages/mechdsl-core/tests/test_j2_radial_return_parity.py` — new
  parity test: imported vs algo2code paths produce identical stress and
  internal-variable updates within tolerance for representative load steps
- `dev/design_docs/07-CONVENTIONS.md` or `dev/design_docs/06-PLASTICITY.md`
  — add note describing the substitution and the feature-flag fallback

**Acceptance criteria**
- Algo2code emits a Taichi `@ti.func` for radial-return that compiles within
  JIT budget (≤ 512 unrolled lines per `@ti.func`).
- Parity test passes for at least one elastic, one elastoplastic, and one
  unloading load step against the imported path.
- Default solver run (no flag set) uses algo2code-generated path; integration
  test confirms.
- Setting `MECHDSL_USE_IMPORTED_RR=1` reverts to imported path without
  recompilation.

**Risks**
- Algo2code may not yet support all algpseudocode constructs needed for
  radial-return — mitigation: identify missing constructs early; either
  extend algo2code (in-scope if minor) or split into a sub-phase.
- JIT budget overflow on the generated function — mitigation: budget probe
  test runs before parity test; failure surfaces with the per-`@ti.func`
  line count.
- Convergence regression — mitigation: parity test uses tolerance derived
  from imported-path baseline, not absolute zero.

---

## Phase 6: Test-layer hardening

**Goal** — Replace fragile patterns in P7 tests (line-number whitelists,
substring-position checks, helper duplication, fixed-index assertions) with
robust matchers, paying down the structural debt called out in items 4, 11,
12.

**Files**
- `packages/mechdsl-core/tests/_e2e_helpers.py` — new shared helper module
  housing `_import_generated_module` and other helpers duplicated across
  e2e tests (item 12)
- `packages/mechdsl-core/tests/test_p7_2.py` — import helper from
  `_e2e_helpers`; remove local copy
- `packages/mechdsl-core/tests/test_e2e_taichi.py` — same swap
- `packages/mechdsl-core/tests/test_p7_4.py` — replace `notes[0]`
  (line ~92) with iteration over `notes` filtering by plan-referenced
  filename (item 4)
- `packages/mechdsl-core/tests/test_phase6_exit.py` — replace
  `_INTENTIONAL_CLEANUP_MATCHES` line-number whitelist with regex/marker
  comment matching in `test_emission_verification.py` (item 11)
- `packages/mechdsl-core/tests/test_emission_verification.py` — add
  in-source markers (e.g. `# intentional-cleanup-site`) at the lines the
  whitelist used to track

**Acceptance criteria**
- No e2e test file contains a local copy of `_import_generated_module`;
  helper is imported from `_e2e_helpers`.
- `test_p7_4.py` passes when the order of files in `notes` is reversed
  (regression check via test fixture).
- `test_phase6_exit.py` passes after the cleanup-site lines are renumbered
  (insert a blank line above the markers and re-run to confirm).
- All affected tests still pass via `uv run pytest -m "not slow and not gpu"`.

**Risks**
- Family-split rule may currently forbid the cross-import — mitigation:
  rule explicitly allows once a third caller exists; phase introduces no
  new caller, so verify family-split policy permits the helper module
  before refactor (escalate to user if it does not).
- In-source markers may be noisy — mitigation: keep markers terse
  (single-line comments); document their meaning in a module-level
  docstring inside `test_emission_verification.py`.

---

## Phase 7: Documentation polish + governance reconciliation

**Goal** — Sweep the Low-priority items (5, 6, 7, 8, 9, 10, 13, 16, 17) into a
single polish pass: docs anchor restoration, test ordering hardening, README
path tolerance, comment forward-pointers, review-length trim, GitNexus index
refresh, Plan B status note, CI baseline confirmation.

**Files**
- `dev/examples/README.md` — restore `## Inventory` anchor (item 7)
- `packages/mechdsl-core/tests/test_p7_3.py` — replace `text.find()`
  ordering check (line ~50) with first-runnable-code-block detector;
  loosen path matching (line ~117) to accept `dev/examples/`,
  `./dev/examples/`, absolute prefixes (items 5, 6)
- `packages/mechdsl-core/tests/test_p7_2.py` — rename
  `_import_generated_module` constant from `gen_p7_2` to a
  fixture-derived unique value (item 8); add forward pointer in
  traction-string-gap comment to Phase 1 closure (item 9 — superseded if
  Phase 1 lands first; in that case remove the comment)
- `packages/mechdsl-core/tests/test_p7_6.py` — trim 50-80 lines by merging
  per-pillar evidence sub-bullets (item 10)
- `dev/tasks/PLAN-B/_SUPERSEDED.md` — clarify which Plan B sub-deliverables
  remain runtime-active vs which planning artifacts are archived (item 16)
- `.gitnexus/meta.json` — refresh by running `npx gitnexus analyze`
  (item 13; requires explicit user authorization at execution time)
- `.github/workflows/ci.yml` (or equivalent) — add a baseline-stability
  smoke job confirming algo2code workspace install yields 0 import
  failures, locking in the post-P7-1 state (item 17)

**Acceptance criteria**
- `dev/examples/README.md` contains an `## Inventory` heading; any internal
  `#inventory` link resolves.
- `test_p7_3.py` ordering check passes when a prose mention of
  `compile_latex(` is added near the top of the README (regression check).
- `test_p7_3.py` README path matching passes for all three path prefix
  variants.
- `test_p7_2.py` no longer hardcodes `gen_p7_2`; fixture derives unique
  module name per test invocation.
- `test_p7_6.py` length is between 100 and 250 lines.
- `_SUPERSEDED.md` contains a runtime-active vs archived sub-section.
- GitNexus `meta.json` `lastIndexed` timestamp postdates this phase's
  start.
- CI baseline-stability job passes on a clean checkout from `main`.

**Risks**
- GitNexus refresh requires user authorization — mitigation: phase emits
  the command but blocks on confirmation; does not auto-run.
- Trimming `test_p7_6.py` may drop content the reviewer expects —
  mitigation: trim only by merging redundant sub-bullets, never by
  deleting unique evidence claims.

---

## Out of Scope

- Item 9 (forward pointer in traction-string-gap comment) becomes obsolete
  once Phase 1 lands — Phase 7 includes it as a fallback only if Phase 1 is
  deferred.
- Cross-language frontend work beyond NRPyLaTeX (e.g. UFL, FEniCS DSL) —
  user did not request, defer entirely.
- Replacing the imported linear solver — out-of-scope per MVP boundary in
  `.claude/CLAUDE.md`.
- Adding new Plan B sub-deliverables; Phase 7 only documents existing
  status (item 16).
- Promoting any Low item to a standalone plan — they are bundled under
  Phase 7 deliberately.

## Reuse

- `mechdsl.frontend.directives` parser scaffolding — extend, do not rewrite,
  for Phase 1 Neumann handling.
- `BoundaryCondition` IR dataclass in `mechdsl.ir.problem` — extend slots
  rather than introducing a parallel BC type.
- `nrpylatex` is already declared in `pyproject.toml` for Phase 4 — no
  dependency-management work required, just import wiring.
- `algo2code` Taichi backend (`packages/algo2code/src/algo2code/backends/taichi_codegen`)
  — Phase 5 generation target; do not re-implement codegen.
- Existing golden-file infrastructure under `packages/mechdsl-core/tests/golden/`
  — Phases 1, 4, 5 should add golden fixtures here, not invent new locations.
- `_import_generated_module` helper currently in `test_p7_2.py` and
  `test_e2e_taichi.py` — Phase 6 promotes to `_e2e_helpers.py`; Phases 1, 4, 5
  should consume the shared version when adding new e2e tests.
