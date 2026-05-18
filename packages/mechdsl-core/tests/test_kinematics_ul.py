"""Tests for Task P1-2: UL kinematics.

Plan: dev/design_docs/PLAN-B.md lines 25-37 (B1.1 UL residual — Jacobian w.r.t.
current coordinates and spatial shape-function gradients).

P1-2 adds two NumPy primitives to ``mechdsl.lib.tensor_ops``
(``current_jacobian`` / ``spatial_shape_gradient``) and a per-quadrature-point
helper ``current_gradient_at_physical`` in ``mechdsl.codegen.hex8_tables``
that mirrors the existing ``reference_gradient_at_physical`` Plan A helper.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.hex8_tables import (
    GRAD_AT_QUAD,
    HEX8_NODE_COORDS,
    current_gradient_at_physical,
    reference_gradient_at_physical,
)
from mechdsl.lib.tensor_ops import current_jacobian, spatial_shape_gradient


def _unit_cube_nodes() -> np.ndarray:
    """Unit cube with corners at 0 and 1 in each axis, nodes ordered like HEX8."""
    return 0.5 * (HEX8_NODE_COORDS + 1.0)  # maps [-1,1]^3 -> [0,1]^3


def _apply_F(X: np.ndarray, F: np.ndarray) -> np.ndarray:
    """Push a (8, 3) node array through a (3, 3) deformation gradient."""
    return X @ F.T


class TestTaskP1_2:
    """
    Tests for Task P1-2: UL kinematics (spatial shape gradients and current Jacobian)

    Acceptance criteria:
      1. At F=I, j equals the reference Jacobian J0 at every quadrature point.
      2. For a known simple shear, j matches the hand calculation j = F @ J0.
      3. For a rigid rotation, spatial shape gradients satisfy dN/dx = R @ (dN/dX).
      4. ElementIR CURRENT geometry slots populated  →  reinterpreted as:
         current_gradient_at_physical returns correctly-shaped (dN/dx, det(j))
         outputs for every Hex8 quadrature point when the element IR is tagged
         configuration='current'.
    """

    @pytest.mark.unit
    def test_current_jacobian_identity_at_f_eq_i(self) -> None:
        """At F=I, the current Jacobian coincides with the reference Jacobian J0.

        Acceptance criterion: "For F = I, j equals the reference Jacobian J0 at
        every quadrature point."
        """
        X_elem = _unit_cube_nodes()
        x_elem = X_elem  # F = I => current coords = reference coords
        for q in range(8):
            dN_dxi = GRAD_AT_QUAD[q]  # (8, 3)
            J0 = X_elem.T @ dN_dxi
            j = current_jacobian(dN_dxi, x_elem)
            assert np.allclose(j, J0, atol=1e-14), f"QP {q}: j != J0 at F = I"

    @pytest.mark.unit
    def test_current_jacobian_simple_shear(self) -> None:
        """Simple shear F = I + gamma e1 ⊗ e2 gives j = F @ J0.

        Acceptance criterion: "For a known simple-shear deformation, j matches
        the hand calculation."
        """
        gamma = 0.25
        F = np.eye(3) + gamma * np.outer([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        X_elem = _unit_cube_nodes()
        x_elem = _apply_F(X_elem, F)
        for q in range(8):
            dN_dxi = GRAD_AT_QUAD[q]
            J0 = X_elem.T @ dN_dxi
            j = current_jacobian(dN_dxi, x_elem)
            j_expected = F @ J0
            assert np.allclose(j, j_expected, atol=1e-12), (
                f"QP {q}: j != F @ J0 for simple shear gamma={gamma}"
            )

    @pytest.mark.unit
    def test_spatial_shape_gradient_rigid_rotation(self) -> None:
        """Rigid body rotation R produces dN/dx = R @ (dN/dX)^T componentwise.

        For a rigid rotation, j = R @ J0, so
            dN/dx = dN/dxi @ j^{-1}
                  = dN/dxi @ (R @ J0)^{-1}
                  = dN/dxi @ J0^{-1} @ R^T
                  = dN/dX @ R^T
        which means each row (dN_a/dx_i) of dN/dx transforms as
            (dN/dx)_a = R @ (dN/dX)_a   (treating the row as a column vector).

        Acceptance criterion: "For a rigid body rotation, the spatial shape
        gradients satisfy dN/dx = R @ (dN/dX)."
        """
        theta = np.pi / 6  # 30 degrees about z
        c, s = np.cos(theta), np.sin(theta)
        R = np.array(
            [
                [c, -s, 0.0],
                [s, c, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        X_elem = _unit_cube_nodes()
        x_elem = _apply_F(X_elem, R)
        for q in range(8):
            dN_dxi = GRAD_AT_QUAD[q]
            J0 = X_elem.T @ dN_dxi
            dN_dX = dN_dxi @ np.linalg.inv(J0)  # reference-config gradients
            j = current_jacobian(dN_dxi, x_elem)
            dN_dx = spatial_shape_gradient(dN_dxi, j)
            # dN/dx = dN/dX @ R^T, i.e. row-wise dN/dx_a = R @ dN/dX_a.
            dN_dx_expected = dN_dX @ R.T
            assert np.allclose(dN_dx, dN_dx_expected, atol=1e-12), (
                f"QP {q}: spatial gradient did not transform rigidly"
            )

    @pytest.mark.unit
    def test_current_gradient_at_physical_mirrors_reference_at_f_eq_i(self) -> None:
        """current_gradient_at_physical(x_elem=X_elem) matches reference_gradient_at_physical.

        Acceptance criterion (interpreted): "Store the computed j and dN/dx on
        ElementIR" — reinterpreted as "provide a per-QP helper that returns
        (dN/dx, det(j)) for the CURRENT configuration, mirroring the
        reference-config helper". This is the on-demand equivalent of the
        storage slot. P1-3 will consume it at emission time.

        At F = I the two helpers must return byte-identical (dN/dx, det) pairs.
        """
        X_elem = _unit_cube_nodes()
        for q in range(8):
            dN_dX_ref, detJ0 = reference_gradient_at_physical(X_elem, q)
            dN_dx_cur, detj = current_gradient_at_physical(X_elem, X_elem, q)
            assert np.allclose(dN_dx_cur, dN_dX_ref, atol=1e-14)
            assert abs(detj - detJ0) < 1e-14
            # Shapes: dN/dx is (8, 3), det is a scalar.
            assert dN_dx_cur.shape == (8, 3)
            assert isinstance(detj, float)
