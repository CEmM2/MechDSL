"""Tests for symbolic kinematics (P3.1): F, C, E, J, F_inv, F_invT, g."""

import pytest
import sympy as sp

from mechdsl.symbolic.kinematics import (
    KinematicsResult,
    compute,
    compute_from_displacement_gradient,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_u_symbols(dim: int = 3) -> tuple[list[list[sp.Symbol]], list[sp.Symbol]]:
    """Create standard displacement-gradient symbols for testing.

    Returns (u_symbols, X_symbols) where u_symbols[i][J] = du_i/dX_J.
    """
    X_syms = sp.symbols("X Y Z")[:dim]
    u_syms: list[list[sp.Symbol]] = []
    for i in range(dim):
        row: list[sp.Symbol] = []
        for J in range(dim):
            row.append(sp.Symbol(f"du{i}_dX{J}"))
        u_syms.append(row)
    return u_syms, list(X_syms)


# ---------------------------------------------------------------------------
# 1. Identity deformation (grad_u = 0)
# ---------------------------------------------------------------------------


class TestIdentityDeformation:
    """When grad_u = 0, the body is undeformed."""

    def test_identity_via_compute(self):
        _u_syms, X_syms = _make_u_symbols()
        # Substitute all gradient components to zero
        zero_u = [[sp.Integer(0)] * 3 for _ in range(3)]
        result = compute(dim=3, u_symbols=zero_u, X_symbols=X_syms)

        I3 = sp.eye(3)
        assert result.F == I3
        assert result.C == I3
        assert result.J == 1
        assert sp.zeros(3) == result.E
        assert result.F_inv == I3
        assert result.F_invT == I3
        assert result.g == I3

    def test_identity_via_convenience(self):
        grad_u = sp.zeros(3)
        result = compute_from_displacement_gradient(grad_u)

        I3 = sp.eye(3)
        assert result.F == I3
        assert result.C == I3
        assert result.J == 1
        assert sp.zeros(3) == result.E
        assert result.F_inv == I3
        assert result.g == I3


# ---------------------------------------------------------------------------
# 2. Simple shear
# ---------------------------------------------------------------------------


class TestSimpleShear:
    """F = [[1, gamma, 0], [0, 1, 0], [0, 0, 1]]."""

    @pytest.fixture()
    def shear_result(self) -> KinematicsResult:
        gamma = sp.Symbol("gamma")
        grad_u = sp.Matrix(
            [
                [0, gamma, 0],
                [0, 0, 0],
                [0, 0, 0],
            ]
        )
        return compute_from_displacement_gradient(grad_u)

    @pytest.fixture()
    def gamma(self) -> sp.Symbol:
        return sp.Symbol("gamma")

    def test_C(self, shear_result: KinematicsResult, gamma: sp.Symbol):
        C_expected = sp.Matrix(
            [
                [1, gamma, 0],
                [gamma, 1 + gamma**2, 0],
                [0, 0, 1],
            ]
        )
        assert sp.simplify(shear_result.C - C_expected) == sp.zeros(3)

    def test_E(self, shear_result: KinematicsResult, gamma: sp.Symbol):
        E_expected = sp.Matrix(
            [
                [0, gamma / 2, 0],
                [gamma / 2, gamma**2 / 2, 0],
                [0, 0, 0],
            ]
        )
        assert sp.simplify(shear_result.E - E_expected) == sp.zeros(3)

    def test_J_is_one(self, shear_result: KinematicsResult):
        """Simple shear is isochoric (volume-preserving)."""
        assert sp.simplify(shear_result.J - 1) == 0


# ---------------------------------------------------------------------------
# 3. Uniaxial stretch
# ---------------------------------------------------------------------------


class TestUniaxialStretch:
    """F = diag(lambda, 1, 1)."""

    @pytest.fixture()
    def lam(self) -> sp.Symbol:
        return sp.Symbol("lambda", positive=True)

    @pytest.fixture()
    def stretch_result(self, lam: sp.Symbol) -> KinematicsResult:
        grad_u = sp.Matrix(
            [
                [lam - 1, 0, 0],
                [0, 0, 0],
                [0, 0, 0],
            ]
        )
        return compute_from_displacement_gradient(grad_u)

    def test_C(self, stretch_result: KinematicsResult, lam: sp.Symbol):
        C_expected = sp.diag(lam**2, 1, 1)
        assert sp.simplify(stretch_result.C - C_expected) == sp.zeros(3)

    def test_E(self, stretch_result: KinematicsResult, lam: sp.Symbol):
        E_expected = sp.diag((lam**2 - 1) / 2, 0, 0)
        assert sp.simplify(stretch_result.E - E_expected) == sp.zeros(3)

    def test_J(self, stretch_result: KinematicsResult, lam: sp.Symbol):
        assert sp.simplify(stretch_result.J - lam) == 0


# ---------------------------------------------------------------------------
# 4. General symbolic: F_inv @ F == I
# ---------------------------------------------------------------------------


class TestSymbolicInverse:
    """For a fully symbolic F, verify F_inv @ F simplifies to I."""

    def test_inverse_identity(self):
        u_syms, X_syms = _make_u_symbols()
        result = compute(dim=3, u_symbols=u_syms, X_symbols=X_syms)

        product = sp.simplify(result.F_inv @ result.F)
        assert product == sp.eye(3), f"F_inv @ F != I:\n{product}"


# ---------------------------------------------------------------------------
# 5. Convected metric: g == C always
# ---------------------------------------------------------------------------


class TestConvectedMetric:
    """The convected metric g must always equal C."""

    def test_g_equals_C_zero_deformation(self):
        result = compute_from_displacement_gradient(sp.zeros(3))
        assert result.g == result.C

    def test_g_equals_C_shear(self):
        gamma = sp.Symbol("gamma")
        grad_u = sp.Matrix([[0, gamma, 0], [0, 0, 0], [0, 0, 0]])
        result = compute_from_displacement_gradient(grad_u)
        assert result.g == result.C

    def test_g_equals_C_symbolic(self):
        u_syms, X_syms = _make_u_symbols()
        result = compute(dim=3, u_symbols=u_syms, X_symbols=X_syms)
        assert result.g == result.C


# ---------------------------------------------------------------------------
# 6. dim != 3 should raise (MVP only supports 3D)
# ---------------------------------------------------------------------------


class TestDimensionValidation:
    """MVP only supports dim=3; other values must raise ValueError."""

    def test_dim_2_raises(self):
        u_syms_2d = [[sp.Symbol(f"du{i}_dX{J}") for J in range(2)] for i in range(2)]
        X_syms_2d = list(sp.symbols("X Y"))
        with pytest.raises(ValueError, match="Only dim=3"):
            compute(dim=2, u_symbols=u_syms_2d, X_symbols=X_syms_2d)

    def test_dim_1_raises(self):
        u_syms_1d = [[sp.Symbol("du0_dX0")]]
        X_syms_1d = [sp.Symbol("X")]
        with pytest.raises(ValueError, match="Only dim=3"):
            compute(dim=1, u_symbols=u_syms_1d, X_symbols=X_syms_1d)

    def test_convenience_2d_raises(self):
        with pytest.raises(ValueError, match="3x3"):
            compute_from_displacement_gradient(sp.zeros(2))

    def test_mismatched_u_symbols_raises(self):
        """u_symbols shape doesn't match dim."""
        u_syms_2x2 = [[sp.Symbol(f"du{i}_dX{J}") for J in range(2)] for i in range(2)]
        X_syms = list(sp.symbols("X Y Z"))
        with pytest.raises(ValueError, match="u_symbols must be 3x3"):
            compute(dim=3, u_symbols=u_syms_2x2, X_symbols=X_syms)


# ---------------------------------------------------------------------------
# 7. Result is frozen dataclass
# ---------------------------------------------------------------------------


class TestResultImmutability:
    """KinematicsResult should be immutable (frozen dataclass)."""

    def test_cannot_reassign(self):
        result = compute_from_displacement_gradient(sp.zeros(3))
        with pytest.raises(AttributeError):
            result.F = sp.eye(3)  # type: ignore[misc]
