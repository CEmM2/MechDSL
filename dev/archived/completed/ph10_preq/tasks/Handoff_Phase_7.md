# Handoff to Phase 7

Phase 6 completed the generalized MMS matrix prerequisite for P10-1 without
changing the existing Hex8 MMS API.

## Completed Inputs

- P6-1 is done. `mechdsl.verify.mms_matrix` provides `MMSMatrixCase`,
  `MMSConvergenceEntry`, `MMSMatrixResult`, `default_mms_matrix_cases`, and
  `run_mms_convergence_matrix`.
- P6-2 is done. The MMS matrix tests are active for Hex8/Tet10/Hex20 elastic
  entries and Hex8 Neo-Hookean/J2/Perzyna/Lemaitre elastic-regime policy entries.
- Existing `run_mms_convergence(lam, mu, ...)` remains unchanged and
  `test_convergence.py` still passes.

## Evidence

- `uv run pytest packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> 10/10 passed.
- `uv run pytest packages/mechdsl-core/tests/test_convergence.py packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> 30/30 passed.
- `uv run ruff check packages/mechdsl-core/src/mechdsl/verify/mms_matrix.py packages/mechdsl-core/tests/test_mms_convergence_matrix.py` -> clean.
- `uv run mypy packages/mechdsl-core/src/mechdsl/verify/mms_matrix.py` -> clean.

## Phase 7 Notes

- Taylor runtime work should remain independent from MMS and cantilever.
- The final performance harness can include the MMS matrix once P9-1 is reached.
