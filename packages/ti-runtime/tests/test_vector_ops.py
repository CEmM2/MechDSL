"""PJ-0 — vector-primitive kernels."""

import numpy as np
import pytest
import taichi as ti

from ti_runtime import vector_ops as v

pytestmark = pytest.mark.slow  # executes Taichi kernels (JIT)


def _vfield(vals: np.ndarray):
    vals = np.ascontiguousarray(vals, dtype=np.float64)
    f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
    f.from_numpy(vals)
    return f


def test_copy():
    rng = np.random.default_rng(0)
    xv = rng.standard_normal((5, 3))
    x = _vfield(xv)
    y = ti.Vector.field(3, ti.f64, shape=5)
    v.copy(y, x)
    np.testing.assert_allclose(y.to_numpy(), xv, rtol=1e-12)


def test_axpy():
    rng = np.random.default_rng(1)
    xv, yv = rng.standard_normal((4, 3)), rng.standard_normal((4, 3))
    x, y = _vfield(xv), _vfield(yv)
    v.axpy(y, 2.5, x)
    np.testing.assert_allclose(y.to_numpy(), yv + 2.5 * xv, rtol=1e-12)


def test_xpay():
    rng = np.random.default_rng(2)
    xv, yv = rng.standard_normal((4, 3)), rng.standard_normal((4, 3))
    x, y = _vfield(xv), _vfield(yv)
    v.xpay(x, -0.5, y)
    np.testing.assert_allclose(x.to_numpy(), -0.5 * xv + yv, rtol=1e-12)


def test_scal():
    rng = np.random.default_rng(3)
    xv = rng.standard_normal((6, 3))
    x = _vfield(xv)
    v.scal(x, 3.0)
    np.testing.assert_allclose(x.to_numpy(), 3.0 * xv, rtol=1e-12)


def test_dot_and_norm():
    rng = np.random.default_rng(4)
    xv, yv = rng.standard_normal((7, 3)), rng.standard_normal((7, 3))
    x, y = _vfield(xv), _vfield(yv)
    assert v.dot(x, y) == pytest.approx(float((xv * yv).sum()), rel=1e-12)
    assert v.norm2(x) == pytest.approx(float(np.linalg.norm(xv)), rel=1e-12)


def test_vec_add():
    rng = np.random.default_rng(5)
    xv, yv = rng.standard_normal((5, 3)), rng.standard_normal((5, 3))
    x, y = _vfield(xv), _vfield(yv)
    out = ti.Vector.field(3, ti.f64, shape=5)
    a, b = 2.0, -0.5
    v.vec_add(out, a, x, b, y)
    np.testing.assert_allclose(out.to_numpy(), a * xv + b * yv, rtol=1e-12)


def test_zero():
    x = _vfield(np.ones((3, 3)))
    v.zero(x)
    np.testing.assert_allclose(x.to_numpy(), 0.0)
