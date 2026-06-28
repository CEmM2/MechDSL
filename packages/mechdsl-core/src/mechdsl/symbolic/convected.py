"""Convected coordinate operations.

Reference: 06-CODEGEN.md §8, 07-CONVENTIONS.md.
For MVP (Cartesian reference): G_IJ = δ_IJ, g_IJ = C_IJ = F^T F.
For curvilinear reference (Plan B phase B2): G_IJ supplied via MetricField.

This module is the single authoritative home for curvilinear-coordinate
tensor calculus in mechdsl.  The metric / Christoffel / covariant-derivative
implementations live here once; named-coordinate constructors
(:func:`cylindrical_basis`, :func:`spherical_basis`) and basis-vector
conveniences (:func:`metric_from_bases`, :func:`reciprocal_bases`,
:func:`verify_biorthogonality`, :func:`christoffel_from_bases`) compose those
primitives rather than duplicating the math (absorbed from constkit, P1-2).
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


def cylindrical_basis(
    r: sp.Expr | float,
    phi: sp.Expr | float,
) -> list[sp.Matrix]:
    """Covariant basis vectors for cylindrical coordinates (r, phi, z).

    The mapping is x^1 = r cos(phi), x^2 = r sin(phi), x^3 = z, so the
    covariant base vectors g_I = dx/dtheta^I are::

        g_r   = ( cos(phi),  sin(phi), 0 )
        g_phi = (-r sin(phi), r cos(phi), 0 )
        g_z   = ( 0, 0, 1 )

    Compose with :func:`metric_from_bases` to obtain g_IJ = diag(1, r^2, 1).

    Args:
        r: Radial coordinate (may be a SymPy expression or float).
        phi: Azimuthal coordinate.

    Returns:
        List of three 3x1 SymPy column matrices [g_r, g_phi, g_z].
    """
    g_r = sp.Matrix([sp.cos(phi), sp.sin(phi), 0])
    g_phi = sp.Matrix([-r * sp.sin(phi), r * sp.cos(phi), 0])
    g_z = sp.Matrix([0, 0, 1])
    return [g_r, g_phi, g_z]


def spherical_basis(
    R: sp.Expr | float,
    theta: sp.Expr | float,
    phi: sp.Expr | float,
) -> list[sp.Matrix]:
    """Covariant basis vectors for spherical coordinates (R, theta, phi).

    The mapping is x^1 = R sin(theta) cos(phi), x^2 = R sin(theta) sin(phi),
    x^3 = R cos(theta).  The covariant base vectors g_I = dx/dtheta^I compose
    with :func:`metric_from_bases` to give g_IJ = diag(1, R^2, R^2 sin^2(theta)).

    Args:
        R: Radial coordinate (may be a SymPy expression or float).
        theta: Polar (inclination) coordinate.
        phi: Azimuthal coordinate.

    Returns:
        List of three 3x1 SymPy column matrices [g_R, g_theta, g_phi].
    """
    st, ct = sp.sin(theta), sp.cos(theta)
    sp_, cp = sp.sin(phi), sp.cos(phi)

    g_R = sp.Matrix([st * cp, st * sp_, ct])
    g_theta = sp.Matrix([R * ct * cp, R * ct * sp_, -R * st])
    g_phi = sp.Matrix([-R * st * sp_, R * st * cp, 0])
    return [g_R, g_theta, g_phi]


def metric_from_bases(g_cov: list[sp.Matrix]) -> sp.Matrix:
    """Build the covariant metric g_IJ = g_I . g_J from covariant base vectors.

    This is the basis-vector form of the metric, complementing the
    deformation-gradient form :func:`compute_convected_metric` (which takes
    F and reference base vectors).  Each entry is the Euclidean inner product
    of two covariant base vectors, trigonometrically simplified.

    Args:
        g_cov: List of three 3x1 covariant base vectors [g_1, g_2, g_3]
            (e.g. from :func:`cylindrical_basis` or :func:`spherical_basis`).

    Returns:
        3x3 symmetric SymPy Matrix for the covariant metric g_IJ.

    Raises:
        ValueError: If ``g_cov`` does not contain exactly 3 basis vectors.
    """
    if len(g_cov) != 3:
        raise ValueError(f"metric_from_bases requires exactly 3 basis vectors, got {len(g_cov)}")
    g = sp.zeros(3, 3)
    for i in range(3):
        for j in range(3):
            g[i, j] = sp.trigsimp(g_cov[i].dot(g_cov[j]))
    return g


def reciprocal_bases(g_cov: list[sp.Matrix]) -> list[sp.Matrix]:
    """Contravariant (reciprocal) base vectors g^I dual to covariant g_I.

    Composes existing primitives rather than duplicating a cross-product
    formula: builds the metric via :func:`metric_from_bases`, inverts it
    with :func:`invert_metric`, then raises indices through the existing
    :func:`contravariant_bases` (g^I = g^{IJ} g_J).  The result satisfies
    biorthogonality g_I . g^J = delta^J_I.

    Args:
        g_cov: List of three 3x1 covariant base vectors [g_1, g_2, g_3].

    Returns:
        List of three 3x1 contravariant base vectors [g^1, g^2, g^3].

    Raises:
        ValueError: If the covariant base vectors are linearly dependent
            (singular metric).
    """
    g = metric_from_bases(g_cov)
    g_inv = invert_metric(g)
    return contravariant_bases(g_cov, g_inv)


def verify_biorthogonality(
    g_cov: list[sp.Matrix],
    g_contra: list[sp.Matrix],
) -> bool:
    """Verify biorthogonality g_I . g^J = delta^J_I for all I, J.

    Args:
        g_cov: List of three 3x1 covariant base vectors [g_1, g_2, g_3].
        g_contra: List of three 3x1 contravariant base vectors [g^1, g^2, g^3].

    Returns:
        ``True`` when all nine dot products match the Kronecker delta.

    Raises:
        AssertionError: With the offending indices and value when any
            dot product deviates from delta.
        ValueError: If either basis list does not contain exactly 3 vectors.
    """
    if len(g_cov) != 3 or len(g_contra) != 3:
        raise ValueError(
            "verify_biorthogonality requires exactly 3 covariant and 3 contravariant "
            f"basis vectors, got {len(g_cov)} and {len(g_contra)}"
        )
    for i in range(3):
        for j in range(3):
            expected = 1 if i == j else 0
            actual = sp.simplify(sp.trigsimp(g_cov[i].dot(g_contra[j])))
            if actual != expected:
                raise AssertionError(
                    f"Biorthogonality failed: g_{i + 1} . g^{j + 1} = {actual}, expected {expected}"
                )
    return True


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


def christoffel_from_bases(
    g_cov: list[sp.Matrix],
    coords: tuple[sp.Symbol, ...] | list[sp.Symbol],
) -> sp.MutableDenseNDimArray:
    """Christoffel symbols of the second kind from covariant base vectors.

    Convenience wrapper that composes existing primitives: it builds the
    covariant metric via :func:`metric_from_bases` and forwards to the
    authoritative :func:`christoffel_symbols` (metric-based).  The Christoffel
    formula is NOT reimplemented here.

    Args:
        g_cov: List of three 3x1 covariant base vectors [g_1, g_2, g_3]
            (e.g. from :func:`cylindrical_basis`), each depending on ``coords``.
        coords: Tuple of 3 SymPy coordinate symbols (theta^1, theta^2, theta^3).

    Returns:
        3x3x3 SymPy MutableDenseNDimArray. gamma[K, I, J] = Gamma^K_{IJ}.

    Raises:
        ValueError: If ``g_cov`` or ``coords`` does not have exactly 3 entries.
    """
    if len(g_cov) != 3:
        raise ValueError(
            f"christoffel_from_bases requires exactly 3 basis vectors, got {len(g_cov)}"
        )
    if len(coords) != 3:
        raise ValueError(f"coords must have exactly 3 coordinate symbols, got {len(coords)}")
    g = metric_from_bases(g_cov)
    return christoffel_symbols(g, coords)


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
    variant: str = "contravariant",
) -> sp.MutableDenseNDimArray:
    """Covariant derivative of a rank-2 tensor field.

    The ``variant`` selects the index character of ``T``:

    - ``"contravariant"`` (default) — upper indices T^{JK}::

          ∇_I T^{JK} = ∂T^{JK}/∂θ^I + Γ^J_{IL} T^{LK} + Γ^K_{IL} T^{JL}

    - ``"covariant"`` — lower indices T_{JK}::

          ∇_I T_{JK} = ∂T_{JK}/∂θ^I − Γ^L_{IJ} T_{LK} − Γ^L_{IK} T_{JL}

    - ``"mixed"`` — mixed indices T^J_K (first index up, second down)::

          ∇_I T^J_K = ∂T^J_K/∂θ^I + Γ^J_{IL} T^L_K − Γ^L_{IK} T^J_L

    Args:
        T: 3x3 Matrix of tensor components (interpretation set by ``variant``).
        gamma: Christoffel symbols gamma[K,I,J] = Γ^K_{IJ}.
        theta: Tuple of 3 coordinate symbols.
        variant: Index character of ``T`` — one of ``"contravariant"``,
            ``"covariant"``, or ``"mixed"``.  Defaults to ``"contravariant"``.

    Returns:
        3x3x3 MutableDenseNDimArray where result[I, J, K] = ∇_I T[J, K].

    Raises:
        ValueError: If ``variant`` is not one of the supported strings, ``T`` is
            not 3x3, or ``theta`` does not have exactly 3 coordinate symbols.
    """
    if variant not in ("contravariant", "covariant", "mixed"):
        raise ValueError(
            f"variant must be 'contravariant', 'covariant', or 'mixed', got '{variant}'"
        )
    if T.shape != (3, 3):
        raise ValueError(f"T must be a 3x3 matrix, got {T.shape}")
    if len(theta) != 3:
        raise ValueError(f"theta must have exactly 3 coordinate symbols, got {len(theta)}")

    n = 3
    _zero_flat = [sp.S.Zero] * (n * n * n)
    result = sp.MutableDenseNDimArray(_zero_flat, (n, n, n))
    if variant == "contravariant":
        for I in range(n):
            for J in range(n):
                for K in range(n):
                    val = sp.diff(T[J, K], theta[I])
                    for L in range(n):
                        val = val + gamma[J, I, L] * T[L, K] + gamma[K, I, L] * T[J, L]
                    result[I, J, K] = val
    elif variant == "covariant":
        for I in range(n):
            for J in range(n):
                for K in range(n):
                    val = sp.diff(T[J, K], theta[I])
                    for L in range(n):
                        val = val - gamma[L, I, J] * T[L, K] - gamma[L, I, K] * T[J, L]
                    result[I, J, K] = val
    elif variant == "mixed":
        for I in range(n):
            for J in range(n):
                for K in range(n):
                    val = sp.diff(T[J, K], theta[I])
                    for L in range(n):
                        val = val + gamma[J, I, L] * T[L, K] - gamma[L, I, K] * T[J, L]
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
