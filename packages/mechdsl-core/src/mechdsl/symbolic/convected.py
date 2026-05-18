"""Convected coordinate operations.

Reference: 06-CODEGEN.md §8, 07-CONVENTIONS.md.
For MVP (Cartesian reference): G_IJ = δ_IJ, g_IJ = C_IJ = F^T F.
For curvilinear reference (Plan B phase B2): G_IJ supplied via MetricField.
"""

from __future__ import annotations

import sympy as sp


class UnsupportedError(Exception):
    """Raised for constructs outside the MVP supported subset."""

    pass


class MetricField:
    """Reference metric tensor G_IJ for a material configuration.

    Wraps either the Cartesian identity (fast path) or a user-supplied
    SymPy Matrix expression for curvilinear reference coordinates.

    Attributes:
        is_cartesian: True when G_IJ == δ_IJ (enables fast path).
        matrix: 3x3 SymPy Matrix representing G_IJ.

    Examples:
        Cartesian (fast path)::

            G = MetricField.cartesian()
            assert G.is_cartesian
            assert G.matrix == sp.eye(3)

        Cylindrical (r, theta, z)::

            r = sp.Symbol('r', positive=True)
            G = MetricField(sp.diag(1, r**2, 1))
    """

    def __init__(self, matrix: sp.Matrix) -> None:
        """Construct a MetricField from an explicit 3x3 SymPy Matrix.

        Args:
            matrix: 3x3 SymPy Matrix for G_IJ. Must be symmetric.

        Raises:
            ValueError: If the matrix is not 3x3 or not symmetric.
        """
        if matrix.shape != (3, 3):
            raise ValueError(f"MetricField requires a 3x3 matrix, got {matrix.shape}")
        if sp.simplify(matrix - matrix.T) != sp.zeros(3):
            raise ValueError("MetricField requires a symmetric matrix (G_IJ = G_JI).")
        self._matrix = matrix
        # Detect Cartesian: G - I simplifies to zero
        self._is_cartesian = sp.simplify(matrix - sp.eye(3)) == sp.zeros(3)

    @classmethod
    def cartesian(cls) -> MetricField:
        """Return the Cartesian reference metric G_IJ = δ_IJ."""
        return cls(sp.eye(3))

    @property
    def is_cartesian(self) -> bool:
        """True when G_IJ is the identity (Cartesian fast path)."""
        return self._is_cartesian

    @property
    def matrix(self) -> sp.Matrix:
        """The 3x3 SymPy Matrix for G_IJ."""
        return self._matrix

    def __repr__(self) -> str:
        if self._is_cartesian:
            return "MetricField(cartesian)"
        return f"MetricField({self._matrix})"


def compute_reference_metric(
    coords: str = "cartesian",
    G: sp.Matrix | None = None,
) -> sp.Matrix:
    """Compute reference metric tensor G_IJ.

    For Cartesian reference configuration: G_IJ = δ_IJ (3x3 identity).
    For curvilinear reference: supply an explicit ``G`` matrix.

    Args:
        coords: Coordinate system name.  ``"cartesian"`` selects G = I.
                Any other string is accepted when ``G`` is also provided.
                Passing a non-cartesian ``coords`` without ``G`` still raises
                ``UnsupportedError`` so callers that relied on the old guard
                continue to see meaningful errors for truly unsupported cases.
        G: Optional explicit 3x3 SymPy Matrix for G_IJ (curvilinear).
           When supplied, ``coords`` is used only as a label and the matrix
           is returned directly.

    Returns:
        3x3 SymPy Matrix for the reference metric G_IJ.

    Raises:
        UnsupportedError: When ``coords != "cartesian"`` and no ``G`` is given.
    """
    if G is not None:
        return G
    if coords == "cartesian":
        return sp.eye(3)
    raise UnsupportedError(
        f"Coordinate system '{coords}' requires an explicit G matrix. "
        "Pass G=<sympy.Matrix> for curvilinear reference configurations. "
        "Auto-construction of named curvilinear metrics is planned for Plan B phase B2."
    )


def compute_convected_metric(
    F: sp.Matrix,
    G_ref_vecs: sp.Matrix | None = None,
) -> sp.Matrix:
    """Compute convected (current) metric tensor g_IJ.

    The covariant base vectors in the current configuration are
    g_I = F G_I, where G_I are columns of ``G_ref_vecs``.  The convected
    metric is their Euclidean inner product:

        g_IJ = g_I · g_J = G_ref_vecs^T (F^T F) G_ref_vecs

    In Total Lagrangian formulation with a Cartesian reference
    (G_ref_vecs = I), g_IJ = F^T F = C_IJ.

    Args:
        F: 3x3 deformation gradient in Cartesian coordinates (SymPy Matrix).
        G_ref_vecs: Optional 3x3 matrix whose columns are the reference base
            vectors G_I = ∂X/∂θ^I.  When ``None`` (default), Cartesian
            G_I = e_I is assumed and the result equals the MVP ``F^T F``
            fast path.

    Returns:
        3x3 convected metric tensor g_IJ.
    """
    if G_ref_vecs is None:
        # Cartesian fast path — bit-identical to original implementation
        return F.T @ F
    return G_ref_vecs.T @ (F.T @ F) @ G_ref_vecs


def invert_metric(g: sp.Matrix) -> sp.Matrix:
    """Invert a metric tensor to obtain the contravariant metric g^{IJ}.

    Computes the symbolic inverse ``g.inv()``.  Before inverting, the
    determinant is simplified and checked for zero; a singular metric
    raises ``ValueError``.

    Args:
        g: 3x3 SymPy Matrix representing the covariant metric g_IJ.

    Returns:
        3x3 SymPy Matrix representing the contravariant metric g^{IJ}.

    Raises:
        ValueError: If the metric is singular (det == 0).
    """
    det = g.det()
    simplified_det = sp.simplify(det)
    if simplified_det == 0:
        raise ValueError("Metric tensor is singular (det = 0); cannot invert.")
    return g.inv()


def covariant_bases(F: sp.Matrix, G_ref_vecs: sp.Matrix | None = None) -> list[sp.Matrix]:
    """Compute covariant base vectors g_I = F G_I at a material point.

    For a Cartesian reference, G_I = e_I (standard basis) so g_I equals
    the I-th column of F.

    For a curvilinear reference, G_I are the reference base vectors
    (columns of the reference tangent map), and g_I = F @ G_I.

    Args:
        F: 3x3 deformation gradient (SymPy Matrix).
        G_ref_vecs: 3x3 matrix whose columns are reference base vectors G_I.
                    When ``None`` (default), Cartesian G_I = e_I is used,
                    i.e. ``G_ref_vecs = I``.

    Returns:
        List of three 3x1 SymPy column matrices [g_1, g_2, g_3].
    """
    if G_ref_vecs is None:
        # Cartesian: g_I = column I of F
        return [F.col(i) for i in range(3)]
    return [F @ G_ref_vecs.col(i) for i in range(3)]


def contravariant_bases(
    cov_bases: list[sp.Matrix],
    g_inv: sp.Matrix,
) -> list[sp.Matrix]:
    """Compute contravariant base vectors g^I = g^{IJ} g_J.

    Args:
        cov_bases: List of three 3x1 covariant base vectors [g_1, g_2, g_3].
        g_inv: 3x3 contravariant metric g^{IJ} = (g_IJ)^{-1}.

    Returns:
        List of three 3x1 contravariant base vectors [g^1, g^2, g^3].
    """
    result: list[sp.Matrix] = []
    for ii in range(3):
        # g^ii = sum_jj g^{ii,jj} g_jj  (start from zero matrix to avoid int + Matrix error)
        vec = sp.zeros(3, 1)
        for jj in range(3):
            vec = vec + g_inv[ii, jj] * cov_bases[jj]
        result.append(vec)
    return result


def christoffel_symbols(
    g: sp.Matrix,
    theta: tuple[sp.Symbol, ...] | list[sp.Symbol],
) -> sp.MutableDenseNDimArray:
    """Compute Christoffel symbols of the second kind.

    Γ^K_{IJ} = (1/2) g^{KL} (∂g_{IL}/∂θ^J + ∂g_{JL}/∂θ^I − ∂g_{IJ}/∂θ^L)

    Args:
        g: 3x3 SymPy Matrix for the covariant metric g_IJ.
        theta: Tuple of 3 SymPy Symbols (θ^1, θ^2, θ^3).

    Returns:
        3x3x3 SymPy MutableDenseNDimArray. gamma[K, I, J] = Γ^K_{IJ}.
    """
    n = 3
    _zero_flat = [sp.S.Zero] * (n * n * n)

    # Fast path: if metric does not depend on any coordinate, all Christoffels are zero
    if all(sp.diff(g, t) == sp.zeros(n) for t in theta):
        return sp.MutableDenseNDimArray(_zero_flat, (n, n, n))

    # Invert metric once
    g_inv = invert_metric(g)

    # Precompute all partial derivatives of g once (cache)
    # dg[k][i, j] = ∂g_{IJ} / ∂θ^k
    dg = [sp.diff(g, theta[k]) for k in range(n)]

    # Allocate result array
    gamma = sp.MutableDenseNDimArray(_zero_flat, (n, n, n))

    for K in range(n):
        for I in range(n):
            for J in range(n):
                val = sp.S.Zero
                for L in range(n):
                    # ∂g_{IL}/∂θ^J + ∂g_{JL}/∂θ^I - ∂g_{IJ}/∂θ^L
                    bracket = dg[J][I, L] + dg[I][J, L] - dg[L][I, J]
                    val = val + g_inv[K, L] * bracket
                gamma[K, I, J] = sp.Rational(1, 2) * val

    return gamma


def covariant_derivative_contravariant(
    v: sp.Matrix,
    gamma: sp.MutableDenseNDimArray,
    theta: tuple[sp.Symbol, ...] | list[sp.Symbol],
) -> sp.Matrix:
    """Covariant derivative of a contravariant vector field.

    (∇v)_{IJ} = ∇_I v^J = ∂v^J/∂θ^I + Γ^J_{IK} v^K

    Args:
        v: 3x1 column vector of contravariant components v^J.
        gamma: Christoffel symbols gamma[K,I,J] = Γ^K_{IJ} (3x3x3 array).
        theta: Tuple of 3 coordinate symbols.

    Returns:
        3x3 Matrix where result[I, J] = ∇_I v^J.
    """
    n = 3
    result = sp.zeros(n, n)
    for I in range(n):
        for J in range(n):
            val = sp.diff(v[J], theta[I])
            for K in range(n):
                val = val + gamma[J, I, K] * v[K]
            result[I, J] = val
    return result


def covariant_derivative_covariant(
    v: sp.Matrix,
    gamma: sp.MutableDenseNDimArray,
    theta: tuple[sp.Symbol, ...] | list[sp.Symbol],
) -> sp.Matrix:
    """Covariant derivative of a covariant vector field.

    (∇v)_{IJ} = ∇_I v_J = ∂v_J/∂θ^I − Γ^K_{IJ} v_K

    Args:
        v: 3x1 column vector of covariant components v_J.
        gamma: Christoffel symbols gamma[K,I,J] = Γ^K_{IJ}.
        theta: Tuple of 3 coordinate symbols.

    Returns:
        3x3 Matrix where result[I, J] = ∇_I v_J.
    """
    n = 3
    result = sp.zeros(n, n)
    for I in range(n):
        for J in range(n):
            val = sp.diff(v[J], theta[I])
            for K in range(n):
                val = val - gamma[K, I, J] * v[K]
            result[I, J] = val
    return result


def covariant_derivative_tensor2(
    T: sp.Matrix,
    gamma: sp.MutableDenseNDimArray,
    theta: tuple[sp.Symbol, ...] | list[sp.Symbol],
) -> sp.MutableDenseNDimArray:
    """Covariant derivative of a rank-2 contravariant tensor field.

    (∇T)_{IJK} = ∇_I T^{JK} = ∂T^{JK}/∂θ^I + Γ^J_{IL} T^{LK} + Γ^K_{IL} T^{JL}

    Args:
        T: 3x3 Matrix of contravariant components T^{JK}.
        gamma: Christoffel symbols gamma[K,I,J] = Γ^K_{IJ}.
        theta: Tuple of 3 coordinate symbols.

    Returns:
        3x3x3 MutableDenseNDimArray where result[I, J, K] = ∇_I T^{JK}.
    """
    n = 3
    _zero_flat = [sp.S.Zero] * (n * n * n)
    result = sp.MutableDenseNDimArray(_zero_flat, (n, n, n))
    for I in range(n):
        for J in range(n):
            for K in range(n):
                val = sp.diff(T[J, K], theta[I])
                for L in range(n):
                    val = val + gamma[J, I, L] * T[L, K] + gamma[K, I, L] * T[J, L]
                result[I, J, K] = val
    return result


def green_lagrange_convected(g: sp.Matrix, G: sp.Matrix) -> sp.Matrix:
    """Compute Green-Lagrange strain from convected and reference metrics.

    E_IJ = 0.5 * (g_IJ - G_IJ)

    Args:
        g: 3x3 current (convected) metric tensor.
        G: 3x3 reference metric tensor.

    Returns:
        3x3 Green-Lagrange strain tensor E_IJ.
    """
    return sp.Rational(1, 2) * (g - G)
