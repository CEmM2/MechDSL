"""PJ-0 — Tier-1 tensor/kinematics @ti.func helpers."""

import numpy as np
import pytest
import taichi as ti

from ti_runtime import tensor_ti as T

pytestmark = pytest.mark.slow  # executes Taichi kernels (JIT)


def _mat_in(vals: np.ndarray):
    f = ti.Matrix.field(3, 3, ti.f64, shape=())
    f[None] = ti.Matrix(np.ascontiguousarray(vals, dtype=np.float64).tolist())
    return f


def test_det_and_kinematics():
    rng = np.random.default_rng(0)
    Fv = np.eye(3) + 0.1 * rng.standard_normal((3, 3))
    Fin = _mat_in(Fv)
    out = ti.field(ti.f64, shape=4)
    Cout = ti.Matrix.field(3, 3, ti.f64, shape=())
    Eout = ti.Matrix.field(3, 3, ti.f64, shape=())

    @ti.kernel
    def run():
        F = Fin[None]
        out[0] = T.det3(F)
        out[1] = T.jacobian(F)
        Cout[None] = T.right_cauchy_green(F)
        Eout[None] = T.green_lagrange(F)

    run()
    assert out[0] == pytest.approx(np.linalg.det(Fv), rel=1e-12)
    assert out[1] == pytest.approx(np.linalg.det(Fv), rel=1e-12)
    np.testing.assert_allclose(Cout[None].to_numpy(), Fv.T @ Fv, rtol=1e-12)
    np.testing.assert_allclose(
        Eout[None].to_numpy(), 0.5 * (Fv.T @ Fv - np.eye(3)), rtol=1e-12, atol=1e-14
    )


def test_deformation_gradient_from_grad_u():
    gu = np.array([[0.1, 0.0, 0.0], [0.0, -0.05, 0.0], [0.0, 0.0, 0.02]])
    gin = _mat_in(gu)
    Fout = ti.Matrix.field(3, 3, ti.f64, shape=())

    @ti.kernel
    def run():
        Fout[None] = T.deformation_gradient(gin[None])

    run()
    np.testing.assert_allclose(Fout[None].to_numpy(), np.eye(3) + gu, rtol=1e-12)


def test_voigt_roundtrip_and_von_mises():
    s = np.array([[10.0, 4.0, 2.0], [4.0, -5.0, 1.0], [2.0, 1.0, 3.0]])  # symmetric
    sin = _mat_in(s)
    voigt = ti.Vector.field(6, ti.f64, shape=())
    back = ti.Matrix.field(3, 3, ti.f64, shape=())
    vm = ti.field(ti.f64, shape=())

    @ti.kernel
    def run():
        v6 = T.to_voigt(sin[None])
        voigt[None] = v6
        back[None] = T.from_voigt(v6)
        vm[None] = T.von_mises(sin[None])

    run()
    np.testing.assert_allclose(voigt[None].to_numpy(), [10.0, -5.0, 3.0, 4.0, 2.0, 1.0], rtol=1e-12)
    np.testing.assert_allclose(back[None].to_numpy(), s, rtol=1e-12)
    # reference von Mises: sqrt(3/2 dev:dev)
    dev = s - np.trace(s) / 3.0 * np.eye(3)
    ref = np.sqrt(1.5 * np.sum(dev * dev))
    assert vm[None] == pytest.approx(ref, rel=1e-12)
