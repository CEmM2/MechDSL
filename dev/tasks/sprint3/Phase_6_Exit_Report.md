# Phase 6 Exit Report

Plan: `dev/plans/sprint3.md`  
Branch: `SOSOVSKI/phase6-exec`  
Date: `2026-04-12`

## Sprint 3 MVP Exit Criteria

- [x] Patch test: constant strain on irregular Hex8, relative error < 1e-12
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_patch_test.py::TestTaskP3T5 -v` -> `2/2` passed.
- [x] Rigid body: zero internal force after 30-degree rotation + translation, norm < 1e-12
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_patch_test.py::TestTaskP3T5 -v` -> rigid-body check included; `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestRigidBodyMotion ... -v` -> `5/5` passed.
- [x] Cantilever: tip displacement within 5% of Euler-Bernoulli (40x8x4 mesh)
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestRigidBodyMotion packages/mechdsl-core/tests/test_benchmarks.py::TestCantilever packages/mechdsl-core/tests/test_benchmarks.py::TestCooksMembrane packages/mechdsl-core/tests/test_benchmarks.py::TestNeckingBar -v` -> `19/19` passed, including all `TestCantilever` cases.
- [x] Cook's membrane: tip displacement within 2% of reference
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestRigidBodyMotion packages/mechdsl-core/tests/test_benchmarks.py::TestCantilever packages/mechdsl-core/tests/test_benchmarks.py::TestCooksMembrane packages/mechdsl-core/tests/test_benchmarks.py::TestNeckingBar -v` -> `19/19` passed, including `TestCooksMembrane::test_reference_comparison`.
- [x] Necking bar: load-displacement curve within 2% of reference
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_benchmarks.py::TestRigidBodyMotion packages/mechdsl-core/tests/test_benchmarks.py::TestCantilever packages/mechdsl-core/tests/test_benchmarks.py::TestCooksMembrane packages/mechdsl-core/tests/test_benchmarks.py::TestNeckingBar -v` -> `19/19` passed, including `TestNeckingBar::test_reference_comparison`.
- [x] MMS convergence: L2 rate >= 2.0, H1 rate >= 1.0 on 4 mesh levels
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_convergence.py -k 4level -v` -> `2/2` passed.
- [x] Full pipeline test exercises all 6 compiler layers
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_full_pipeline.py -v` -> `2/2` passed.
- [x] CI runs 3 tiers: fast (commit), slow (PR), nightly (e2e benchmarks)
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_ci_config.py -v` -> `4/4` passed. CI has 3 tiers and the nightly benchmark failure protocol remains covered.
- [x] README, examples, CHANGELOG, docstrings complete
  Evidence: `uv run pytest packages/mechdsl-core/tests/test_documentation.py -v` -> `25/25` passed.
- [x] `ruff`, `mypy`, full `pytest` all pass cleanly
  Evidence: `uv run ruff check packages/` -> pass; `uv run ruff format --check packages/` -> pass; `uv run mypy packages/mechdsl-core/src/mechdsl/` -> pass; `uv run pytest --tb=short -q` -> `1014/1014` passed.

## Toolchain Evidence

- `uv run ruff check packages/` -> pass
- `uv run ruff format --check packages/` -> pass
- `uv run mypy packages/mechdsl-core/src/mechdsl/` -> pass
- `uv run pytest packages/mechdsl-core/tests/test_einsum.py -k budget -v` -> `9/9` passed
- `uv run pytest --tb=short -q` -> `1014/1014` passed

## Notes

- The Phase 6 full-suite failure mode was a root pytest collection collision between
  `packages/mechdsl-core/tests/conftest.py` and `packages/algo2code/tests/conftest.py`
  under `--import-mode=importlib`. This was resolved by flattening the `algo2code`
  test package and switching the four affected tests to consume the existing
  `pcg_latex` fixture instead of importing `conftest.py` as a module.
- The cleanup scan still reports one intentionally deferred Plan B TODO in
  `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` and two test-only
  assertions in `test_emission_verification.py` that guard against placeholder
  markers. No Phase 6 scaffold stubs remain.
