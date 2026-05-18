# Phase 6 Context Summary — End-to-End Taichi Smoke Test

## Conventions

- `@pytest.mark.slow` for Taichi JIT compilation tests
- `@pytest.mark.e2e` for end-to-end pipeline tests
- Generated vs reference displacement: max diff < 1e-10 (per `08-VERIFICATION.md §3.3`)
- Tests use `tmp_path` fixture for generated files
- Per `.claude/rules/tests.md`: "Keep test data minimal — small meshes, few load steps"

## Key Principles

- This is the **highest-value validation gate** for Sprint 1: prove the generated code actually compiles and runs under Taichi JIT.
- The test uses `compile(problem_ir)` from Phase 4 to get emitted source, writes it to disk, imports it, and runs it.
- Reference data comes from `ref_hex8_elastic.py::solve_elastic` (run in the test itself) or from `tests/golden/elastic_cantilever.npz`.
- The generated code is executed via `importlib.util.spec_from_file_location` — not subprocess.
- Taichi JIT compilation can take several seconds — hence `@pytest.mark.slow`.

## Pre-resolved Design Decisions

- Two tests:
  1. `test_elastic_hex8_matches_reference`: full compile → execute → compare vs reference
  2. `test_newton_converges_one_iteration`: verify linear elastic converges in exactly 1 Newton step
- 1-element Hex8 mesh for both tests (minimal, fast)
- Simple tension BCs (prescribed displacement on one face, fixed on opposite)
- Comparison tolerance: `np.max(np.abs(u_gen - u_ref)) < 1e-10`
- CI: slow tests excluded from fast CI by default (`-m "not slow and not gpu"`), run separately on relevant PRs

## Downstream Impact

- This is the terminal phase — no downstream dependencies
- Success here validates the entire Sprint 1 pipeline end-to-end
- The test becomes a regression guard for all future codegen changes

## Key Files

| File | Current state | Action |
|------|--------------|--------|
| `tests/test_e2e_taichi.py` | Does not exist | New test file |
| `tests/test_e2e.py` | Existing E2E tests (structural) | Read only (reference for patterns) |
| `tests/ref/ref_hex8_elastic.py` | Handwritten reference solver | Read only (ground truth) |
| `tests/golden/elastic_cantilever.npz` | Serialized reference solution | Read only (optional ground truth) |
| `.github/workflows/` | Existing CI | Update for slow test job (P6-T2) |

## Existing E2E test patterns (from test_e2e.py)

The existing `TestGeneratedCodeImport` class already imports generated modules via `importlib` and requires Taichi. The new test extends this to:
1. Actually call `newton_solve()` in the generated module
2. Compare numerical output against the reference solver
3. Assert convergence in the expected number of iterations
