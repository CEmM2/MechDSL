"""Voigt and Mandel conversion utilities.

Conventions (from 07-CONVENTIONS.md §2):
- Voigt ordering: [xx, yy, zz, xy, xz, yz]
- Shears are UNSCALED (tensorial Voigt, not engineering Voigt)
- All arrays are float64
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Voigt maps (§2.3 of 07-CONVENTIONS.md)
# ---------------------------------------------------------------------------

VOIGT_MAP_3D: list[tuple[int, int]] = [
    (0, 0),
    (1, 1),
    (2, 2),
    (0, 1),
    (0, 2),
    (1, 2),
]

VOIGT_INV_3D: dict[tuple[int, int], int] = {
    (0, 0): 0,
    (1, 1): 1,
    (2, 2): 2,
    (0, 1): 3,
    (1, 0): 3,
    (0, 2): 4,
    (2, 0): 4,
    (1, 2): 5,
    (2, 1): 5,
}

# ---------------------------------------------------------------------------
# 2nd-order tensor  <->  Voigt 6-vector
# ---------------------------------------------------------------------------


def sym_tensor_to_voigt(T: NDArray) -> NDArray:
    """Convert 3x3 symmetric tensor to 6-vector.

    Unscaled shears (tensorial Voigt):
        v = [T_00, T_11, T_22, T_01, T_02, T_12]
    """
    if T.shape != (3, 3):
        msg = f"Expected (3,3) tensor, got {T.shape}"
        raise ValueError(msg)
    v = np.empty(6, dtype=np.float64)
    for a, (i, j) in enumerate(VOIGT_MAP_3D):
        v[a] = T[i, j]
    return v


def voigt_to_sym_tensor(v: NDArray) -> NDArray:
    """Convert 6-vector to 3x3 symmetric tensor.

    Assumes unscaled shears (tensorial Voigt).
    """
    if v.shape != (6,):
        msg = f"Expected (6,) vector, got {v.shape}"
        raise ValueError(msg)
    T = np.empty((3, 3), dtype=np.float64)
    for a, (i, j) in enumerate(VOIGT_MAP_3D):
        T[i, j] = v[a]
        T[j, i] = v[a]  # symmetry
    return T


# ---------------------------------------------------------------------------
# 4th-order tangent  <->  Voigt 6x6 matrix
# ---------------------------------------------------------------------------


def tangent_to_voigt_66(C4: NDArray) -> NDArray:
    """Convert 4th-order tangent (3,3,3,3) to 6x6 Voigt matrix.

    C6[a,b] = C4[i,j,k,l]  where (i,j) = VOIGT_MAP_3D[a], (k,l) = VOIGT_MAP_3D[b].
    Unscaled shears -- no factors of 2 or 4.
    """
    if C4.shape != (3, 3, 3, 3):
        msg = f"Expected (3,3,3,3) tangent, got {C4.shape}"
        raise ValueError(msg)
    C6 = np.empty((6, 6), dtype=np.float64)
    for a, (i, j) in enumerate(VOIGT_MAP_3D):
        for b, (k, el) in enumerate(VOIGT_MAP_3D):  # el = l (tensor index)
            C6[a, b] = C4[i, j, k, el]
    return C6


def voigt_66_to_tangent(C6: NDArray) -> NDArray:
    """Convert 6x6 Voigt matrix to 4th-order tangent (3,3,3,3).

    Reconstructs full minor symmetries (C_ijkl = C_jikl = C_ijlk = C_jilk).
    """
    if C6.shape != (6, 6):
        msg = f"Expected (6,6) matrix, got {C6.shape}"
        raise ValueError(msg)
    C4 = np.zeros((3, 3, 3, 3), dtype=np.float64)
    for a, (i, j) in enumerate(VOIGT_MAP_3D):
        for b, (k, el) in enumerate(VOIGT_MAP_3D):  # el = l (tensor index)
            val = C6[a, b]
            C4[i, j, k, el] = val
            C4[j, i, k, el] = val  # minor sym left
            C4[i, j, el, k] = val  # minor sym right
            C4[j, i, el, k] = val  # both
    return C4


# ---------------------------------------------------------------------------
# Mandel scaling
# ---------------------------------------------------------------------------

MANDEL_SCALE: NDArray = np.array(
    [1.0, 1.0, 1.0, np.sqrt(2), np.sqrt(2), np.sqrt(2)],
    dtype=np.float64,
)


def voigt_to_mandel(v: NDArray) -> NDArray:
    """Convert Voigt 6-vector to Mandel 6-vector.

    m = P @ v  where P = diag(1, 1, 1, sqrt(2), sqrt(2), sqrt(2)).
    """
    result: NDArray = v * MANDEL_SCALE
    return result


def mandel_to_voigt(m: NDArray) -> NDArray:
    """Convert Mandel 6-vector to Voigt 6-vector.

    v = P^{-1} @ m.
    """
    result: NDArray = m / MANDEL_SCALE
    return result


def tangent_voigt_to_mandel(C6: NDArray) -> NDArray:
    """Convert 6x6 Voigt tangent to Mandel form.

    C_mandel = P @ C_voigt @ P^{-1}
    where P = diag(1, 1, 1, sqrt(2), sqrt(2), sqrt(2)).
    """
    P = np.diag(MANDEL_SCALE)
    P_inv = np.diag(1.0 / MANDEL_SCALE)
    result: NDArray = P @ C6 @ P_inv
    return result


def tangent_mandel_to_voigt(C6_mandel: NDArray) -> NDArray:
    """Convert 6x6 Mandel tangent to Voigt form.

    C_voigt = P^{-1} @ C_mandel @ P
    """
    P = np.diag(MANDEL_SCALE)
    P_inv = np.diag(1.0 / MANDEL_SCALE)
    result: NDArray = P_inv @ C6_mandel @ P
    return result
