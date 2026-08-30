"""Pre-computed static tables for Hex8 **reduced** integration (Plan B §B5.4).

Hex8 trilinear hexahedron with a **1-point** Gauss rule at the centre of the
reference cube ``[-1, 1]^3``. The shape functions are identical to the full
Hex8 element — only the quadrature changes — so this module re-exports
``shape_functions`` / ``shape_gradients`` / ``HEX8_NODE_COORDS`` from
:mod:`mechdsl.codegen.hex8_tables` and provides its own quadrature tables.

Quadrature rule
---------------
  - Points: ``[(0, 0, 0)]``
  - Weights: ``[8.0]`` (volume of the reference cube)
  - Integrates all polynomials of total degree 1 exactly.

Stability warning
-----------------
Reduced integration introduces **hourglass** (zero-energy) modes: non-constant
deformation patterns whose strain vanishes at the single centre point. Without
hourglass control, a single element is numerically unstable — stiffness is
rank-deficient on those modes.

Plan B §B5.5 adds Flanagan-Belytschko hourglass stabilisation. **Users MUST
pair reduced Hex8 with an hourglass controller** (e.g. via a future
``hourglass='flanagan_belytschko'`` option) before running production analyses.

This module only exposes the 1-point quadrature — it does not add stabilisation.

Use
---
The reduced rule integrates constant-strain deformations exactly, so patch
tests on uniform deformation gradients return identical stress to the
full 2x2x2 rule (see :mod:`tests.test_hex8_reduced`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from mechdsl.codegen.hex8_tables import (
    HEX8_NODE_COORDS,
    shape_functions,
    shape_gradients,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = [
    "GRAD_AT_QUAD_REDUCED",
    "HEX8_NODE_COORDS",
    "HEX8_QUAD_POINTS_REDUCED",
    "HEX8_QUAD_WEIGHTS_REDUCED",
    "QUAD_POINTS_REDUCED",
    "QUAD_WEIGHTS_REDUCED",
    "SHAPE_AT_QUAD_REDUCED",
    "shape_functions",
    "shape_gradients",
]

# ---------------------------------------------------------------------------
# 1-point Gauss quadrature at the centre of the reference cube [-1,1]^3
# ---------------------------------------------------------------------------

HEX8_QUAD_POINTS_REDUCED: NDArray = np.array(
    [[0.0, 0.0, 0.0]],
    dtype=np.float64,
)

HEX8_QUAD_WEIGHTS_REDUCED: NDArray = np.array([8.0], dtype=np.float64)

# Convenience aliases matching the naming convention in sibling table modules.
QUAD_POINTS_REDUCED: NDArray = HEX8_QUAD_POINTS_REDUCED
QUAD_WEIGHTS_REDUCED: NDArray = HEX8_QUAD_WEIGHTS_REDUCED

# ---------------------------------------------------------------------------
# Pre-evaluated tables (computed once at module load time)
# ---------------------------------------------------------------------------

# SHAPE_AT_QUAD_REDUCED[q, a] = N_a(xi_q, eta_q, zeta_q) at the centre point.
SHAPE_AT_QUAD_REDUCED: NDArray = np.array(
    [shape_functions(float(pt[0]), float(pt[1]), float(pt[2])) for pt in HEX8_QUAD_POINTS_REDUCED],
    dtype=np.float64,
)

# GRAD_AT_QUAD_REDUCED[q, a, i] = dN_a / d(xi_i) at the centre point.
GRAD_AT_QUAD_REDUCED: NDArray = np.array(
    [shape_gradients(float(pt[0]), float(pt[1]), float(pt[2])) for pt in HEX8_QUAD_POINTS_REDUCED],
    dtype=np.float64,
)
