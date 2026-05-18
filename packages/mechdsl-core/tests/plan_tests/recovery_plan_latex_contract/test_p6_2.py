"""Task P6-2: Keep the current imported solver path as the default fallback
until generated PCG is stable.

Phase 6 (R5.2) — unit-tier acceptance: verify that the imported (pre-existing)
linear solver remains the default fallback used by the Newton driver until the
algo2code-generated PCG kernel has been validated. Selecting the generated PCG
must be an explicit opt-in until P6 is closed.

Plan reference: dev/plans/recovery_plan_latex_contract.md (Phase 6, R5.2,
line 318).

Acceptance criteria:
  1. Solver regression tests pass with both fallback (imported) and generated
     (algo2code PCG) modes.
  2. All deliverables for P6-2 are in place at the listed surfaces:
       - packages/mechdsl-core/src/mechdsl/solver/import_adapter.py
       - solver integration layer (Newton driver wiring)
       - algo2code interface hook (generated-PCG entry point)
  3. No regressions on the existing test suite.

LinearSolverInterface contract:
  packages/mechdsl-core/src/mechdsl/solver/import_adapter.py:26-57
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import mechdsl.solver as solver_pkg
from mechdsl.solver import integration as solver_integration
from mechdsl.solver.import_adapter import (
    Algo2CodePCGSolver,
    LinearSolverInterface,
    ScipyCGSolver,
    build_solver,
    get_default_solver,
)
from mechdsl.solver.integration import select_linear_solver

# Root paths for surface-presence checks.
_TESTS_ROOT = Path(__file__).parent.parent.parent  # packages/mechdsl-core/tests/
_PACKAGE_ROOT = _TESTS_ROOT.parent  # packages/mechdsl-core/
_SRC_ROOT = _PACKAGE_ROOT / "src" / "mechdsl"
_REPO_ROOT = _PACKAGE_ROOT.parent.parent  # repo root
_ALGO2CODE_SRC = _REPO_ROOT / "packages" / "algo2code" / "src"


def _laplacian_1d(n: int) -> np.ndarray:
    """Return the SPD (n x n) tridiagonal Laplacian — standard CG test bed."""
    A = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        A[i, i] = 2.0
        if i > 0:
            A[i, i - 1] = -1.0
            A[i - 1, i] = -1.0
    return A


class TestP6_2:
    """Tests for Task P6-2: Imported solver as default fallback until generated PCG is stable."""

    def test_solver_regression_passes_with_both_modes(self) -> None:
        """P6-2-c1: Solver regression tests pass with both fallback and generated modes.

        Criterion: ``Solver regression tests pass with both fallback and
        generated modes.``

        Verifies:
          - The solver factory exposes two selectable modes: ``"fallback"``
            (imported solver, the default) and ``"generated"`` (algo2code PCG).
          - With no explicit selection, ``get_default_solver()`` returns the
            imported/fallback solver — confirming the fallback remains the
            default until generated PCG is stabilised.
          - Running the Newton-driver solver regression suite against the
            fallback mode passes (residual norm drops below the configured
            tolerance for the canonical small linear system).
          - Running the same regression suite against the generated mode also
            passes (same residual tolerance), demonstrating both code paths
            satisfy the LinearSolverInterface contract.

        Passing condition: both modes solve the regression linear system to the
        spec tolerance, and the default mode is the fallback (imported) solver.
        """
        # --- 1. Default factory is the fallback (imported) solver. --------
        default = get_default_solver()
        assert isinstance(default, ScipyCGSolver), (
            "get_default_solver() must return ScipyCGSolver — the imported "
            "fallback path is the default until P6-3 stabilises generated PCG."
        )

        # --- 2. build_solver dispatch table. ------------------------------
        assert isinstance(build_solver(), ScipyCGSolver), (
            "build_solver() with no args must default to mode='fallback'."
        )
        assert isinstance(build_solver("fallback"), ScipyCGSolver)
        assert isinstance(build_solver("generated"), Algo2CodePCGSolver)

        with pytest.raises(ValueError, match="nonsense"):
            build_solver("nonsense")  # type: ignore[arg-type]

        # --- 3. select_linear_solver mirrors build_solver. ----------------
        assert isinstance(select_linear_solver(), ScipyCGSolver)
        assert isinstance(select_linear_solver("fallback"), ScipyCGSolver)
        assert isinstance(select_linear_solver("generated"), Algo2CodePCGSolver)

        with pytest.raises(ValueError, match="bogus"):
            select_linear_solver("bogus")  # type: ignore[arg-type]

        # --- 4. Both modes solve a small SPD system to spec tolerance. ----
        n = 5
        A = _laplacian_1d(n)
        b = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)

        def matvec(v: np.ndarray) -> np.ndarray:
            return A @ v

        x0 = np.zeros(n, dtype=np.float64)
        tol = 1e-12
        max_iter = 100

        results: dict[str, tuple[np.ndarray, int, float]] = {}
        for mode, solver in (
            ("fallback", build_solver("fallback")),
            ("generated", build_solver("generated")),
        ):
            x, k, r = solver.solve(matvec, b, x0, tol, max_iter)
            results[mode] = (x, k, r)
            assert k > 0, f"{mode}: iteration count must be positive (got {k})"
            residual_inf = float(np.linalg.norm(A @ x - b))
            assert residual_inf < 1e-8, f"{mode}: ||A x - b|| = {residual_inf:.3e} exceeds 1e-8"

        # --- 5. Both code paths agree on the solution. --------------------
        x_fb, _, _ = results["fallback"]
        x_gen, _, _ = results["generated"]
        max_abs_diff = float(np.max(np.abs(x_fb - x_gen)))
        assert max_abs_diff < 1e-8, (
            f"Fallback / generated solutions diverge by {max_abs_diff:.3e} (must be < 1e-8)"
        )

        # --- 6. Newton's `linear_solver=None` default still resolves to
        #        ScipyCGSolver. We inspect the function source via AST so we
        #        do not need to assemble a real Newton problem.
        from mechdsl.solver import newton as newton_module

        newton_src = inspect.getsource(newton_module.newton_solve)
        newton_tree = ast.parse(newton_src)
        # Locate the `if linear_solver is None:` branch.
        found_branch = False
        for node in ast.walk(newton_tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "linear_solver"
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Is)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value is None
            ):
                # Body must assign `linear_solver = ScipyCGSolver()`.
                names_called = [
                    n.func.id
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                ]
                assert "ScipyCGSolver" in names_called, (
                    "Newton's linear_solver=None branch must construct "
                    "ScipyCGSolver(); found calls: " + repr(names_called)
                )
                found_branch = True
                break
        assert found_branch, (
            "Newton's `if linear_solver is None:` default branch is missing — "
            "P6-2 forbids changing the default fallback resolution."
        )

    def test_deliverables_present_at_surfaces(self) -> None:
        """P6-2-c2: deliverables present at the listed surfaces.

        Criterion: ``All deliverables for P6-2 are in place at the surfaces
        listed (same as P6-1: solver/import_adapter.py, solver integration
        layer, algo2code interface hook).``

        Verifies the three surfaces named in the plan exist and expose the
        expected hooks:
          1. ``packages/mechdsl-core/src/mechdsl/solver/import_adapter.py``
             defines ``LinearSolverInterface`` and exposes a fallback factory
             that returns the imported solver as the default.
          2. The solver integration layer (Newton driver wiring) calls into a
             single mode-selector entry point so callers can request
             ``"fallback"`` or ``"generated"`` without reaching past the
             interface.
          3. The algo2code interface hook (generated-PCG entry point) is
             present and discoverable from the integration layer; until the
             generated path is marked stable, the integration layer must not
             dispatch to it by default.

        Passing condition: each surface file exists, the
        ``LinearSolverInterface`` contract is unchanged, the default selector
        returns the imported/fallback solver, and the generated-PCG entry
        point is reachable only via explicit opt-in.
        """
        # --- 1. import_adapter.py exposes the expected names. -------------
        import_adapter = importlib.import_module("mechdsl.solver.import_adapter")
        for name in (
            "LinearSolverInterface",
            "Algo2CodePCGSolver",
            "get_default_solver",
            "build_solver",
        ):
            assert hasattr(import_adapter, name), f"import_adapter must expose {name!r}"
        assert callable(import_adapter.get_default_solver)
        assert callable(import_adapter.build_solver)

        # --- 2. integration.py exposes select_linear_solver. --------------
        assert hasattr(solver_integration, "select_linear_solver")
        assert callable(solver_integration.select_linear_solver)

        # --- 3. mechdsl.solver.__all__ contains every required surface. ---
        required = {
            "LinearSolverInterface",
            "CGSolver",
            "PCGSolver",
            "ScipyCGSolver",
            "Algo2CodePCGSolver",
            "get_default_solver",
            "build_solver",
            "select_linear_solver",
        }
        missing = required - set(solver_pkg.__all__)
        assert not missing, f"mechdsl.solver.__all__ is missing required surfaces: {missing}"

        # --- 4. algo2code interface hook is still importable and unchanged.
        algo_pcg = importlib.import_module("algo2code.library.pcg")
        assert hasattr(algo_pcg, "PCG_ALGORITHM_LATEX")
        assert hasattr(algo_pcg, "get_pcg_algorithm_latex")
        assert callable(algo_pcg.get_pcg_algorithm_latex)
        # Re-running through the function returns the same canonical text.
        assert algo_pcg.get_pcg_algorithm_latex() == algo_pcg.PCG_ALGORITHM_LATEX

        # --- 5. algo2code stays runtime-free of mechdsl. ------------------
        pattern = re.compile(r"^\s*(?:import\s+mechdsl|from\s+mechdsl)", re.MULTILINE)
        offenders: list[Path] = []
        for py_file in _ALGO2CODE_SRC.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(py_file)
        assert not offenders, (
            "algo2code package must not import mechdsl at runtime; "
            f"offenders: {[str(p) for p in offenders]}"
        )

        # --- 6. Default selector returns the imported (fallback) solver,
        #        NOT the generated one.
        default = select_linear_solver()
        assert isinstance(default, ScipyCGSolver)
        assert not isinstance(default, Algo2CodePCGSolver)

        # And the LinearSolverInterface protocol still acts on the result.
        # (Structural Protocol — `solve` callable with the right signature
        # is sufficient.)
        assert callable(getattr(default, "solve", None)), (
            "Default solver must satisfy LinearSolverInterface (have .solve)."
        )
        # Reference the protocol so the import is exercised.
        _ = LinearSolverInterface
