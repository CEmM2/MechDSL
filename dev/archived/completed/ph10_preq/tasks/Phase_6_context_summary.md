# Phase 6 Context Summary: Generalized MMS Matrix

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E6 Generalized MMS Matrix

## Must Know

- This phase closes P10-1 without breaking the existing Hex8 MMS API.
- Add a matrix-capable MMS API instead of changing `run_mms_convergence(lam, mu, ...)`.
- Do not use `BenchmarkResult`; MMS result structures should remain local to convergence.
- Existing `test_convergence.py` must remain unchanged and passing.

## Should Know

- Use the Phase 1 mesh utilities and existing convergence helpers.
- For dissipative materials, the plan permits a documented elastic-regime MMS policy unless true manufactured dissipative source terms are implemented.

## Allowed Deviations

- Elastic-regime MMS for dissipative models is allowed only if it is explicit in docs/tests and still satisfies the task acceptance gates.

## Downstream Impact

- Completion contributes the MMS prerequisite for the final performance harness.

