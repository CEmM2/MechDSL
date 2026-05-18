# Sprint 3 -- All Tasks

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-1 | 1 | Upgrade cantilever to 40x8x4 mesh with 5% EB tolerance | -- | P4-1 | 33-45 |
| P1-2 | 1 | Add 4-level MMS convergence test [2,4,8,16] | -- | P4-1 | 47-51 |
| P1-3 | 1 | Add @pytest.mark.e2e to TestTaskP3T5 in test_patch_test.py | -- | P4-1 | 36 |
| P1-4 | 1 | Add 30-degree finite rotation test to TestRigidBodyMotion | -- | P4-1 | 37 |
| P2-1 | 2 | Implement generate_cook_membrane_mesh() trapezoidal mesh generator | -- | P2-2, P2-3, P5-2 | 77, 81-85 |
| P2-2 | 2 | Test trapezoidal mesh geometry | P2-1 | P2-3 | 78 |
| P2-3 | 2 | Implement Cook's membrane benchmark with J2 and reference comparison | P2-1, P2-2 | P4-1 | 79, 87-95 |
| P3-1 | 3 | Implement necking bar mesh generator with geometric imperfection | -- | P3-2, P3-3, P3-4, P5-2 | 121, 126-130 |
| P3-2 | 3 | Test necking bar mesh geometry and imperfection | P3-1 | P3-4 | 122 |
| P3-3 | 3 | Generate self-converged reference data (fine mesh) | P3-1 | P3-4 | 123, 132-135 |
| P3-4 | 3 | Implement necking bar benchmark with 2% load-displacement comparison | P3-1, P3-2, P3-3 | P4-1 | 124, 137-145 |
| P4-1 | 4 | Create test_full_pipeline.py exercising all 6 compiler layers | P1-1, P1-2, P1-3, P1-4, P2-3, P3-4 | P4-2 | 171, 175-186 |
| P4-2 | 4 | Add nightly e2e schedule to CI | P4-1 | P4-3 | 172, 188-192 |
| P4-3 | 4 | Implement failure protocol (benchmark regressions create issues) | P4-2 | -- | 173, 194-196 |
| P5-1 | 5 | Update README with installation, quickstart, architecture | -- | -- | 221 |
| P5-2 | 5 | Create 5 example Python scripts | P2-1, P3-1 | -- | 222, 227 |
| P5-3 | 5 | Add docstrings to public API functions | -- | -- | 223 |
| P5-4 | 5 | Update CHANGELOG for MVP release | -- | -- | 224 |
| P5-5 | 5 | Review UnsupportedError messages reference correct Plan B phases | -- | -- | 225 |
| P6-1 | 6 | Ruff lint and format pass | -- | P6-3 | 247 |
| P6-2 | 6 | Mypy type checking pass | -- | P6-3 | 248 |
| P6-3 | 6 | Full test suite zero failures | P6-1, P6-2 | P6-6 | 249 |
| P6-4 | 6 | JIT budget compliance check | -- | P6-6 | 250 |
| P6-5 | 6 | Remove dead code, unused imports, resolved TODOs | -- | P6-6 | 251 |
| P6-6 | 6 | Verify all Sprint 3 exit criteria | P6-3, P6-4, P6-5 | P6-7 | 252, 255-265 |
| P6-7 | 6 | Sprint 3 handoff document | P6-6 | -- | 253 |
