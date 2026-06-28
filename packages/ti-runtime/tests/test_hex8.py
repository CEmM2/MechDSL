"""PJ-0 — Hex8 shape functions, gradients, quadrature."""

import numpy as np
import pytest
import taichi as ti

from ti_runtime import hex8

pytestmark = pytest.mark.slow  # executes Taichi kernels (JIT)


def test_quadrature_tables():
    assert hex8.N_QP == 8
    assert len(hex8.QUAD_POINTS) == 8
    assert hex8.QUAD_WEIGHTS == (1.0,) * 8
    # 2x2x2 Gauss weights sum to the reference cube volume (2^3 = 8).
    assert sum(hex8.QUAD_WEIGHTS) == pytest.approx(8.0)


def test_partition_of_unity_and_gradient_sum():
    N = ti.Vector.field(8, ti.f64, shape=())
    dN = ti.Matrix.field(8, 3, ti.f64, shape=())

    @ti.kernel
    def run(xi: ti.f64, eta: ti.f64, zeta: ti.f64):
        N[None] = hex8.shape(xi, eta, zeta)
        dN[None] = hex8.shape_grad_natural(xi, eta, zeta)

    run(0.3, -0.6, 0.2)
    # Shape functions partition unity; natural gradients sum to zero per direction.
    assert N[None].to_numpy().sum() == pytest.approx(1.0, rel=1e-12)
    np.testing.assert_allclose(dN[None].to_numpy().sum(axis=0), 0.0, atol=1e-12)


def test_shape_is_nodal_delta_at_corners():
    N = ti.Vector.field(8, ti.f64, shape=())

    @ti.kernel
    def run(xi: ti.f64, eta: ti.f64, zeta: ti.f64):
        N[None] = hex8.shape(xi, eta, zeta)

    for a, (sx, sy, sz) in enumerate(hex8._CORNERS):
        run(float(sx), float(sy), float(sz))
        expected = np.zeros(8)
        expected[a] = 1.0
        np.testing.assert_allclose(N[None].to_numpy(), expected, atol=1e-12)
