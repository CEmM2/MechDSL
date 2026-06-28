"""Vector-primitive ``@ti.kernel`` operations (PlanJune14 PJ-0).

Layout-agnostic primitives over Taichi *vector* fields (``ti.Vector.field(d)``),
the shape FEM degrees-of-freedom use. Generated solvers call these instead of
re-emitting their own (PlanJune14 PJ-2).

The scalar coefficient ``a`` is a **runtime ``float`` argument**, not
``ti.template()`` — annotating a Python scalar as ``ti.template()`` bakes the
value into the compiled kernel, triggering a fresh JIT per distinct value
(observed as 100k+ kernel variants in tight Krylov loops). Harvested from
NumerixWeave ``tisolvers``.
"""

import taichi as ti


@ti.kernel
def copy(dst: ti.template(), src: ti.template()):
    """``dst <- src`` (elementwise)."""
    for I in ti.grouped(src):
        dst[I] = src[I]


@ti.kernel
def axpy(y: ti.template(), a: float, x: ti.template()):
    """``y <- y + a*x``."""
    for I in ti.grouped(y):
        y[I] += a * x[I]


@ti.kernel
def xpay(x: ti.template(), a: float, y: ti.template()):
    """``x <- a*x + y`` (the CG search-direction update)."""
    for I in ti.grouped(x):
        x[I] = a * x[I] + y[I]


@ti.kernel
def scal(x: ti.template(), a: float):
    """``x <- a*x``."""
    for I in ti.grouped(x):
        x[I] = a * x[I]


@ti.kernel
def _dot(x: ti.template(), y: ti.template()) -> ti.f64:
    s = 0.0
    for I in ti.grouped(x):
        s += x[I].dot(y[I])
    return s


def dot(x, y) -> float:
    """Euclidean inner product ``x . y`` over a vector field (returns a float)."""
    return float(_dot(x, y))


def norm2(x) -> float:
    """Euclidean 2-norm ``||x||_2``."""
    return float(_dot(x, x)) ** 0.5


@ti.kernel
def vec_add(out: ti.template(), a: float, x: ti.template(), b: float, y: ti.template()):
    """``out[I] = a*x[I] + b*y[I]`` (AXPBY, elementwise over any field shape)."""
    for I in ti.grouped(out):
        out[I] = a * x[I] + b * y[I]


def zero(x) -> None:
    """Zero a field in place."""
    x.fill(0.0)


@ti.kernel
def ediv(z: ti.template(), r: ti.template(), d: ti.template(), eps: float):
    """Elementwise guarded divide: ``z[I] = r[I] / max(d[I], eps)``.

    Point-Jacobi preconditioner kernel (PlanJune14 P4-1): applies M^{-1} r
    where M = diag(d).  The ``eps`` guard prevents division by zero on a
    near-zero diagonal; the caller is responsible for choosing a physically
    appropriate value (default: 1e-12).

    Layout-agnostic: works for any ``ti.Vector.field`` or scalar ``ti.field``
    where element-wise max and division are defined.
    """
    for I in ti.grouped(r):
        z[I] = r[I] / ti.max(d[I], eps)
