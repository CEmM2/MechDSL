"""Field allocation + ``ti.init`` boilerplate (PlanJune14 PJ-0).

The minimal runtime preamble generated code (and the test harness) targets:
choose a backend, allocate the standard field kinds. Kept deliberately thin —
heavy field-registry / domain-manager machinery from NumerixWeave is *not*
harvested (PlanJune14 "avoid" list).
"""

from __future__ import annotations

import taichi as ti

_ARCH = {
    "cpu": ti.cpu,
    "gpu": ti.gpu,
    "cuda": ti.cuda,
    "metal": ti.metal,
    "vulkan": ti.vulkan,
}


def init(arch: str = "cpu", default_fp=ti.f64, **kwargs) -> None:
    """Initialise Taichi for a named backend (``cpu``/``gpu``/``cuda``/``metal``)."""
    if arch not in _ARCH:
        raise ValueError(f"Unknown arch {arch!r}; expected one of {sorted(_ARCH)}.")
    ti.init(arch=_ARCH[arch], default_fp=default_fp, **kwargs)


def vector_field(dim: int, n: int, dtype=ti.f64):
    """``n`` nodes × ``dim`` dof (e.g. displacement, force, residual)."""
    return ti.Vector.field(dim, dtype=dtype, shape=n)


def scalar_field(n: int, dtype=ti.f64):
    return ti.field(dtype=dtype, shape=n)


def matrix_field(rows: int, cols: int, shape, dtype=ti.f64):
    return ti.Matrix.field(rows, cols, dtype=dtype, shape=shape)


def index_field(shape, dtype=ti.i32):
    """Integer field, e.g. element→node connectivity."""
    return ti.field(dtype=dtype, shape=shape)
