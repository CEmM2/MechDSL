# Phase 9 Context Summary: Performance And Nightly Harness

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E9 Performance And Nightly Harness

## Must Know

- This phase closes P10-10 and must run last.
- Do not invent missing benchmark semantics here; all upstream original-scope benchmark tasks must already be active.
- Add a registry over public benchmark runners, local baselines, and nightly CI wiring.
- Local performance tests must use smoke settings and avoid GPU-only requirements.

## Should Know

- Capture wall time, solver iteration counts where available, and benchmark metrics.
- Baseline comparison should report clear per-benchmark deltas.

## Allowed Deviations

- Nightly may use full settings while local tests use smoke settings.

## Downstream Impact

- This is the terminal prerequisite phase for the Phase 10 completion effort.

