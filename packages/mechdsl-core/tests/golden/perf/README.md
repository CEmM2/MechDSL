# Phase 10 Smoke Performance Baseline

Owner: Phase 9 P9-1 — `mechdsl.verify.perf`.

## Files

- `baseline_smoke.json` — committed local smoke baseline. Loaded by
  `mechdsl.verify.perf.load_smoke_baseline()` and consumed by the
  per-benchmark delta reporter `compare_to_baseline()`.

Schema:

```json
{
  "generated_on": "YYYY-MM-DD",
  "commit": "<git sha at time of regen>",
  "tolerance_pct_default": 10.0,
  "tasks": {
    "P10-1": {"wallclock_s": 7.46, "l2_rate_..._svk_...": 1.84, ...},
    "P10-2": {"wallclock_s": 0.001, "tip_displacement": 0.002, ...},
    ...
    "P10-9": {"wallclock_s": 0.03, "P_axial_fem": 90.22, ...}
  }
}
```

## Regenerating the baseline

The baseline is a golden artifact: regen requires explicit intent.

The smoke registry exercises P10-4 (thick cylinder), P10-8 (notched bar),
and P10-9 (HGO uniaxial) which all need the `tests.ref.*` reference solvers
on `sys.path`. The simplest reliable invocation is via `uv run python -m`
with the test tree pre-pended:

```bash
PYTHONPATH=packages/mechdsl-core:packages/mechdsl-core/tests \
  uv run python -m mechdsl.verify.perf.regenerate_baseline \
  > packages/mechdsl-core/tests/golden/perf/baseline_smoke.json
```

The dominant cost (~50 s) is the Taichi JIT compile inside the P10-8
notched-bar runner. The remaining benchmarks finish in O(seconds).

After regeneration, **review the diff against the committed baseline
before staging**. Drift is expected only when an upstream runner's smoke
profile or metric semantics changes intentionally; in that case the JSON
diff and the originating change should land together.

## Carry-forward constraints honoured by the registry

- **P10-7 Taylor**: `TaylorImpactParameters.smoke()` only — not `nightly()`.
  Per P8-2 carry-forward, the nightly profile overruns the JC
  `radial_return` 50-iteration budget on the shipped 6x6x20 mesh, and
  long-horizon PEEQ (~16.6 at n_steps=200) is unphysical.
- **P10-1 MMS**: smoke restricts the matrix to the cheap Hex8/SVK case at
  three coarse mesh levels (3, 4, 5) so the smoke run is O(seconds). The
  baseline records measured L2 + H1 convergence rates per case.
- **P10-8 Notched bar**: smallest viable mesh (4x2x1) + 2 load steps to cap
  the Taichi compile + solve cost.
