# Release Order — MechDSL law compile → NumerixWeave consumption

This is the operational runbook for shipping a `mechdsl-lawgen`-emitted
constitutive law from **MechDSL** (this repo) into **NumerixWeave**
(`ticonstit.generated`). It is the P4-3 deliverable of MFront-mimic Cycle M0
(`dev/plans/mfront_cycleM0.md`, R1).

## Why this doc exists (R1)

`NumerixWeave/tools/check_dependency_graph.py` walks the **workspace** import
graph (`libs/`, `apps/`, `bundles/`) to enforce that `ticonstit` never gains a
runtime dependency on MechDSL or SymPy. It cannot see — and is not meant to
see — the **cross-repo build edge**: a MechDSL CLI process reading a YAML law
spec and writing generated Python files into a NumerixWeave checkout is a
build-time / process dependency, not a Python import, so it never appears as
an edge in either repo's dependency graph.

That invisible edge is real, though: NumerixWeave's `ticonstit.generated`
package depends on MechDSL having produced specific, byte-stable files at
specific paths. The seam that keeps this safe is:

1. **Committed artifacts** — the generated files are checked into
   NumerixWeave, not built at NumerixWeave's install/CI time. NumerixWeave
   never invokes MechDSL as part of its own build.
2. **`source_hash`** — `_manifest.json` pins the SHA-256 of the canonical
   input formula string for each law, so drift between the committed artifact
   and its MechDSL source is detectable without re-running the compiler.
3. **This documented order** — the three steps below, always run in this
   sequence, from the correct venv in each repo.

**MechDSL must never become a NumerixWeave runtime dependency.** The
generated Python under `ticonstit/generated/` imports only Taichi and the
Python standard library — never `mechdsl`, never `sympy`. MechDSL only ever
appears on the NumerixWeave side as an optional, path-pinned **subprocess**
invoked from tests (see `libs/ticonstit/tests/generated/test_swift_voce_equivalence.py`
in NumerixWeave), which is exempt from the runtime-import ban by construction
— it never imports MechDSL/SymPy into the NumerixWeave process.

## The 3-step release sequence

### Step 1 — Compile the law in MechDSL (MechDSL venv)

Run from the **MechDSL** repo root, using MechDSL's own `uv`-managed
environment (R3 — never run this from NumerixWeave's `.venv`):

```bash
cd /Users/shmuelosovski/Github/Personal/MechDSL
uv run mechdsl-lawgen compile laws/plasticity/swift_voce.yaml \
    --target ticonstit \
    --out /Users/shmuelosovski/Github/Personal/NumerixWeave/libs/ticonstit/src/ticonstit/generated/
```

Notes:

- `--out` points at the **generated-level** directory
  (`libs/ticonstit/src/ticonstit/generated/`) — *not*
  `.../generated/plasticity/`. The compiler creates/updates the
  `plasticity/` subdirectory itself; pointing `--out` one level too deep
  double-nests `plasticity/plasticity/`.
- This writes/updates three artifacts under that `--out` directory:
  - `plasticity/swift_voce.py` — the generated Taichi carrier class.
  - `_manifest.json` — the law registry entry, including `source_hash`.
  - `tests/test_swift_voce.py` — a self-contained generated smoke test.
- Output is byte-stable: running this command twice against an unchanged
  `swift_voce.yaml` produces byte-identical `swift_voce.py` and the same
  `source_hash` in `_manifest.json`. For the current `swift_voce.yaml`,
  `source_hash` is
  `7b5af3a8bb79c2e44e0055a7076dd2c9de2ce8c75eb2e262b80bb4e0232d557f`
  (SHA-256 of the canonical input formula string, not of the whole file).

### Step 2 — Commit the generated artifacts into NumerixWeave

Switch to the **NumerixWeave** checkout and commit the files Step 1 wrote (or
overwrote) under `libs/ticonstit/src/ticonstit/generated/`:

```bash
cd /Users/shmuelosovski/Github/Personal/NumerixWeave
git add libs/ticonstit/src/ticonstit/generated/plasticity/swift_voce.py \
        libs/ticonstit/src/ticonstit/generated/_manifest.json \
        libs/ticonstit/src/ticonstit/generated/tests/test_swift_voce.py
git commit -m "chore(ticonstit): regenerate SwiftVoce carrier from MechDSL lawgen"
```

The generated files are **checked into version control**, not produced by
NumerixWeave's own build or CI. Anyone building or testing NumerixWeave gets
the artifacts from git, not from a live MechDSL invocation — this is what
keeps MechDSL out of NumerixWeave's runtime/build dependency graph.

Do not hand-edit files under `generated/` (see NumerixWeave's
`libs/ticonstit/src/ticonstit/generated/GENERATED.md`) — re-run Step 1
instead, so the source of truth stays the MechDSL YAML law spec.

### Step 3 — NumerixWeave CI verifies and gates

NumerixWeave CI (and any local `pytest` run) then:

- Runs the **equivalence gate**,
  `libs/ticonstit/tests/generated/test_swift_voce_equivalence.py`, which
  re-invokes `mechdsl-lawgen compile` as a **subprocess** (via
  `uv run --project <MechDSL checkout> mechdsl-lawgen ...`) against a sibling
  MechDSL checkout, and byte/value-compares the freshly emitted carrier
  against the committed one at `rtol=1e-10`. This test skips cleanly (does
  not fail) if no MechDSL checkout is available at
  `MECHDSL_ROOT` (default `/Users/shmuelosovski/Github/Personal/MechDSL`).
- Confirms the committed `_manifest.json`'s `source_hash` matches the
  pinned/expected value — catching silent drift between the YAML law source
  and the committed generated artifact.
- Runs `tools/check_dependency_graph.py`, which enforces (among other things)
  that nothing under `libs/` or `apps/` imports `mechdsl` or `sympy` at
  runtime. `ticonstit.generated.plasticity.swift_voce` imports only `taichi`.

## Why the order matters

The steps must run in this sequence — compile, then commit, then
verify/consume — because NumerixWeave's own tooling (`check_dependency_graph.py`,
its `pyproject.toml` workspace membership, its CI) has no visibility into
MechDSL at all except through:

- files that already exist in the NumerixWeave git tree (Step 2's commit),
  and
- the one deliberately-isolated subprocess call in the equivalence test
  (Step 3), which runs MechDSL in MechDSL's own venv and never imports it
  into the NumerixWeave process.

If Step 2 is skipped or done out of order (e.g. NumerixWeave CI tries to
regenerate artifacts itself, or a stale artifact is committed without
re-running Step 1 after a law YAML change), the `source_hash` check in Step 3
is what catches the drift — it is the only cross-repo consistency signal that
survives the fact that the build edge itself is invisible to static
dependency analysis.

## See also

- NumerixWeave: `libs/ticonstit/src/ticonstit/generated/GENERATED.md` — the
  consumer-side note on the same seam.
- `dev/plans/mfront_cycleM0.md` (Phase 4, R1) — the plan risk this doc
  mitigates.
- `dev/plans/mfront_cycleM0/Phase_4_context_summary.md` — phase-level
  context for the compile → commit → consume flow.
