"""Element IR — FE localisation schema for Hex8 Total Lagrangian.

Captures the element-level discretisation: basis functions, quadrature
rule, and formulation metadata. Produced by lowering ProblemIR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import numpy as np

from mechdsl.ir.mechanics_ir import IntegrationRule

if TYPE_CHECKING:
    from collections.abc import Mapping

    from numpy.typing import NDArray

# Hex8 node coordinates in reference space [-1,1]^3
_HEX8_NODES: NDArray = np.array(
    [
        [-1, -1, -1],
        [+1, -1, -1],
        [+1, +1, -1],
        [-1, +1, -1],
        [-1, -1, +1],
        [+1, -1, +1],
        [+1, +1, +1],
        [-1, +1, +1],
    ],
    dtype=np.float64,
)


@dataclass(frozen=True)
class QuadratureRule:
    """Gauss quadrature rule on the reference element."""

    points: NDArray  # (n_pts, 3) reference coordinates
    weights: NDArray  # (n_pts,) weights

    def __post_init__(self) -> None:
        if self.points.ndim != 2 or self.points.shape[1] != 3:
            raise ValueError(f"points must be (n, 3), got {self.points.shape}")
        if self.weights.ndim != 1:
            raise ValueError(f"weights must be 1D, got shape {self.weights.shape}")
        if self.points.shape[0] != self.weights.shape[0]:
            raise ValueError(
                f"points rows ({self.points.shape[0]}) != weights length ({self.weights.shape[0]})"
            )

    @property
    def n_points(self) -> int:
        return len(self.weights)


@dataclass(frozen=True)
class BasisFunctions:
    """Shape functions for a finite element.

    For Hex8: 8 trilinear shape functions on [-1,1]^3.
    N_i(xi, eta, zeta) = (1/8)(1 + xi_i*xi)(1 + eta_i*eta)(1 + zeta_i*zeta)
    """

    n_nodes: int

    def evaluate(self, xi: float, eta: float, zeta: float) -> NDArray:
        """Shape function values at a point. Returns (n_nodes,)."""
        if self.n_nodes == 8:
            vals = np.empty(8, dtype=np.float64)
            for i in range(8):
                xi_i, eta_i, zeta_i = _HEX8_NODES[i]
                vals[i] = 0.125 * (1.0 + xi_i * xi) * (1.0 + eta_i * eta) * (1.0 + zeta_i * zeta)
            return vals
        if self.n_nodes == 4:
            # Linear Tet4 shape functions: N0=1-xi-eta-zeta, N1=xi, N2=eta, N3=zeta
            return np.array(
                [1.0 - xi - eta - zeta, xi, eta, zeta],
                dtype=np.float64,
            )
        if self.n_nodes == 10:
            from mechdsl.codegen.tet10_tables import shape_functions as _tet10_sf

            return _tet10_sf(xi, eta, zeta)
        if self.n_nodes == 20:
            from mechdsl.codegen.hex20_tables import shape_functions as _hex20_sf

            return _hex20_sf(xi, eta, zeta)
        raise NotImplementedError(f"evaluate not implemented for n_nodes={self.n_nodes}")

    def gradient(self, xi: float, eta: float, zeta: float) -> NDArray:
        """Shape function gradients at a point. Returns (n_nodes, 3).

        Columns are dN/d(xi), dN/d(eta), dN/d(zeta).
        """
        if self.n_nodes == 8:
            grad = np.empty((8, 3), dtype=np.float64)
            for i in range(8):
                xi_i, eta_i, zeta_i = _HEX8_NODES[i]
                # dN_i/d(xi)
                grad[i, 0] = 0.125 * xi_i * (1.0 + eta_i * eta) * (1.0 + zeta_i * zeta)
                # dN_i/d(eta)
                grad[i, 1] = 0.125 * (1.0 + xi_i * xi) * eta_i * (1.0 + zeta_i * zeta)
                # dN_i/d(zeta)
                grad[i, 2] = 0.125 * (1.0 + xi_i * xi) * (1.0 + eta_i * eta) * zeta_i
            return grad
        if self.n_nodes == 4:
            del xi, eta, zeta  # Tet4 gradients are constant; args kept for API parity.
            return np.array(
                [
                    [-1.0, -1.0, -1.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
        if self.n_nodes == 10:
            from mechdsl.codegen.tet10_tables import shape_gradients as _tet10_sg

            return _tet10_sg(xi, eta, zeta)
        if self.n_nodes == 20:
            from mechdsl.codegen.hex20_tables import shape_gradients as _hex20_sg

            return _hex20_sg(xi, eta, zeta)
        raise NotImplementedError(f"gradient not implemented for n_nodes={self.n_nodes}")


# ---------------------------------------------------------------------------
# Execution-contract enrichment (recovery-plan Phase 4 / R3.1 / P4-1).
#
# Pre-P4-1, downstream codegen and lowering re-derived facts about each
# element's reference volume, the constitutive call's input/output shapes,
# and the local force / tangent layout from a mix of `element_type` strings,
# `quadrature.n_points`, and hard-coded knowledge of MVP Hex8. P4-1 promotes
# those facts into four small frozen dataclasses that ride on `ElementIR` as
# optional fields with safe defaults so legacy callers continue working.
#
# The four contracts deliberately stay backend-agnostic — no Taichi-specific
# slot names, no Voigt-specific field layouts that would leak into MFEM /
# MOOSE. Per the Phase 4 constraints: "Avoid backend-specific leakage into
# IR types."
# ---------------------------------------------------------------------------


def _freeze_metadata(raw: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Wrap ``raw`` as a read-only :class:`MappingProxyType`.

    Mirrors the helper in ``mechanics_ir.py``: frozen-dataclass attribute
    immutability does not extend through nested dicts. ``MappingProxyType``
    closes that gap for the metadata bags below.
    """
    return MappingProxyType(dict(raw or {}))


@dataclass(frozen=True)
class GeometrySummary:
    """Per-element geometry summary — single source of truth for downstream.

    Captures the element's reference-cell volume, quadrature size, and
    parametric dimension. Pre-P4-1 these were re-derived from
    ``ElementIR.element_type`` everywhere that needed them; P4-1 promotes
    them to a single dataclass so downstream consumers read one value.
    """

    n_quad: int
    reference_volume: float
    natural_coord_dim: int = 3

    def __post_init__(self) -> None:
        if self.n_quad < 1:
            raise ValueError(f"GeometrySummary.n_quad must be >= 1, got {self.n_quad}")
        if self.reference_volume <= 0.0:
            raise ValueError(
                f"GeometrySummary.reference_volume must be > 0, got {self.reference_volume}"
            )
        if self.natural_coord_dim not in (1, 2, 3):
            raise ValueError(
                f"GeometrySummary.natural_coord_dim must be 1, 2, or 3; "
                f"got {self.natural_coord_dim}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_quad": self.n_quad,
            "reference_volume": self.reference_volume,
            "natural_coord_dim": self.natural_coord_dim,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GeometrySummary:
        return cls(
            n_quad=int(d["n_quad"]),
            reference_volume=float(d["reference_volume"]),
            natural_coord_dim=int(d.get("natural_coord_dim", 3)),
        )


@dataclass(frozen=True)
class MaterialEvalContract:
    """Per-quadrature constitutive evaluation contract.

    Captures the input / output shapes and stress / strain measures the
    material model expects at each quadrature point. Downstream codegen
    reads this to wire up the right stress measure (PK2 vs Cauchy) and
    tangent shape, instead of inferring them from the formulation tag.

    ``allowed_stress_measures`` and ``allowed_strain_measures`` are
    module-level frozensets so callers can introspect the supported
    vocabulary without guessing.
    """

    stress_measure: str = "pk2"
    strain_measure: str = "green_lagrange"
    tangent_rank: int = 4
    voigt_size: int = 6
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stress_measure not in ALLOWED_STRESS_MEASURES:
            raise ValueError(
                f"MaterialEvalContract.stress_measure={self.stress_measure!r} "
                f"is not supported; allowed values are "
                f"{sorted(ALLOWED_STRESS_MEASURES)}. "
                "Wider stress-measure support is planned for Plan B §B1."
            )
        if self.strain_measure not in ALLOWED_STRAIN_MEASURES:
            raise ValueError(
                f"MaterialEvalContract.strain_measure={self.strain_measure!r} "
                f"is not supported; allowed values are "
                f"{sorted(ALLOWED_STRAIN_MEASURES)}."
            )
        if self.tangent_rank not in (2, 4):
            raise ValueError(
                f"MaterialEvalContract.tangent_rank must be 2 (Voigt) or 4 "
                f"(full); got {self.tangent_rank}."
            )
        if self.voigt_size not in (3, 6):
            raise ValueError(
                f"MaterialEvalContract.voigt_size must be 3 (2D) or 6 (3D); got {self.voigt_size}."
            )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stress_measure": self.stress_measure,
            "strain_measure": self.strain_measure,
            "tangent_rank": self.tangent_rank,
            "voigt_size": self.voigt_size,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MaterialEvalContract:
        return cls(
            stress_measure=d.get("stress_measure", "pk2"),
            strain_measure=d.get("strain_measure", "green_lagrange"),
            tangent_rank=int(d.get("tangent_rank", 4)),
            voigt_size=int(d.get("voigt_size", 6)),
            metadata=dict(d.get("metadata", {})),
        )


# Allowed values for `MaterialEvalContract.{stress,strain}_measure`. Module-
# level so callers can introspect the supported set instead of guessing.
ALLOWED_STRESS_MEASURES: frozenset[str] = frozenset({"pk2", "cauchy"})
ALLOWED_STRAIN_MEASURES: frozenset[str] = frozenset({"green_lagrange", "almansi", "logarithmic"})


@dataclass(frozen=True)
class LocalForceDescriptor:
    """Per-element local force-vector layout descriptor.

    Records the per-element force-vector size and a backend-agnostic
    contraction sketch. The descriptor is documentation-grade today — the
    Taichi printer and other emitters still write the actual contraction
    inline. P4-1 promotes the layout to a first-class IR object so a future
    P5-3 (codegen façade) can drive emission from this descriptor instead
    of the printer's hard-coded knowledge.
    """

    n_dof: int  # n_nodes * dim
    contraction_sketch: str = ""

    def __post_init__(self) -> None:
        if self.n_dof < 1:
            raise ValueError(f"LocalForceDescriptor.n_dof must be >= 1, got {self.n_dof}")

    def to_dict(self) -> dict[str, Any]:
        return {"n_dof": self.n_dof, "contraction_sketch": self.contraction_sketch}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LocalForceDescriptor:
        return cls(
            n_dof=int(d["n_dof"]),
            contraction_sketch=d.get("contraction_sketch", ""),
        )


@dataclass(frozen=True)
class LocalTangentDescriptor:
    """Per-element local tangent (stiffness) matrix layout descriptor.

    The local tangent is a square (n_dof x n_dof) matrix. ``is_symmetric``
    flags whether downstream solvers can assume symmetry — true for SVK
    elasticity and the algorithmic-symmetric J2 return map; false for
    non-associative or rate-dependent models that ship with non-symmetric
    consistent tangents.
    """

    n_dof: int  # n_nodes * dim
    is_symmetric: bool = True
    contraction_sketch: str = ""

    def __post_init__(self) -> None:
        if self.n_dof < 1:
            raise ValueError(f"LocalTangentDescriptor.n_dof must be >= 1, got {self.n_dof}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_dof": self.n_dof,
            "is_symmetric": self.is_symmetric,
            "contraction_sketch": self.contraction_sketch,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LocalTangentDescriptor:
        return cls(
            n_dof=int(d["n_dof"]),
            is_symmetric=bool(d.get("is_symmetric", True)),
            contraction_sketch=d.get("contraction_sketch", ""),
        )


@dataclass(frozen=True)
class ElementIR:
    """Element-level IR — the discretisation schema.

    Captures element type, basis functions, quadrature rule, and
    formulation. Immutable and validated at construction time.

    Parameters
    ----------
    element_type
        Element family identifier. The MVP accepts only ``"hex8"``.
    n_nodes
        Number of nodes per element. The MVP Hex8 element requires ``8``.
    dim
        Spatial dimension. The MVP accepts only ``3``.
    basis
        Basis-function object for evaluating shape functions and gradients.
    quadrature
        Reference-element quadrature rule used during localisation.
    formulation
        Formulation identifier. The MVP accepts only
        ``"total_lagrangian"``.
    integration_rule
        Quadrature-rule selector. Defaults to :attr:`IntegrationRule.FULL`
        (the element-specific full Gauss rule). :attr:`IntegrationRule.REDUCED`
        selects a reduced rule — currently only meaningful for Hex8 (1-point
        centre). See Plan B §B5.4 for the axis-orthogonal split between
        element topology and integration rule; Plan B §B5.5 adds the
        hourglass control required to stabilise reduced Hex8.
    geometry, material_eval, local_force, local_tangent
        Optional execution-contract enrichment introduced by recovery
        Phase 4 / R3.1 / P4-1. All four default to ``None`` so legacy
        callers continue constructing ``ElementIR`` without source changes.
        When populated, they expose the per-element geometry summary,
        constitutive evaluation contract, and local force / tangent layout
        as a single source of truth so downstream codegen does not
        re-derive these facts from the element-type tag.

    Raises
    ------
    ValueError
        If the element metadata leaves the MVP Hex8/3D subset, or if the
        execution-contract descriptors are inconsistent with the element
        topology (e.g. ``LocalForceDescriptor.n_dof != n_nodes * dim``).
    """

    element_type: str  # "hex8"
    n_nodes: int  # 8
    dim: int  # 3
    basis: BasisFunctions
    quadrature: QuadratureRule
    formulation: str  # "total_lagrangian" or "updated_lagrangian"
    configuration: str = "reference"  # "reference" (TL) or "current" (UL)
    integration_rule: IntegrationRule = IntegrationRule.FULL

    # Recovery-plan P4-1 execution-contract enrichment. Optional; safe defaults.
    geometry: GeometrySummary | None = None
    material_eval: MaterialEvalContract | None = None
    local_force: LocalForceDescriptor | None = None
    local_tangent: LocalTangentDescriptor | None = None

    # constitutive_latex P5-1: per-element fiber-orientation field data carried
    # down from ProblemIR.fiber_field (anisotropic models, HGO). One unit-ish
    # direction per fiber family; None for isotropic problems. Held as a plain
    # data tuple so the Element IR stays decoupled from the Mechanics-IR
    # FiberFieldSpec type. This is the no-layer-bypass carry: frontend directive
    # -> ProblemIR.fiber_field -> ElementIR.fiber_field.
    fiber_field: tuple[tuple[float, float, float], ...] | None = None

    def __post_init__(self) -> None:
        """Validate at construction."""
        _SUPPORTED = {"hex8": 8, "tet4": 4, "tet10": 10, "hex20": 20}
        if self.element_type not in _SUPPORTED:
            raise ValueError(
                f"Element type {self.element_type!r} not supported. "
                "Additional element families are planned for Plan B phase B5."
            )
        expected_nodes = _SUPPORTED[self.element_type]
        if self.n_nodes != expected_nodes:
            raise ValueError(
                f"{self.element_type.upper()} requires {expected_nodes} nodes, got {self.n_nodes}"
            )
        if self.dim != 3:
            raise ValueError(f"Only 3D supported, got {self.dim}. 2D is planned for Plan B.")
        if self.configuration not in ("reference", "current"):
            raise ValueError(
                f"Unknown configuration {self.configuration!r}. "
                "Valid values are 'reference' (TL) or 'current' (UL). "
                "See Plan B §B1.3 (Configuration-aware IR refactor)."
            )
        if not isinstance(self.integration_rule, IntegrationRule):
            raise ValueError(
                f"integration_rule must be an IntegrationRule enum member, "
                f"got {type(self.integration_rule).__name__}. "
                "See Plan B phase B5 (§B5.4) for the integration-rule axis."
            )
        # Reduced integration is currently only implemented for Hex8 (Plan B §B5.4).
        if self.integration_rule == IntegrationRule.REDUCED and self.element_type != "hex8":
            raise ValueError(
                f"Reduced integration is only implemented for hex8, got "
                f"{self.element_type!r}. "
                "Reduced rules for other element families are planned for "
                "Plan B phase B5."
            )

        # P4-1: enriched execution-contract consistency checks. Each runs only
        # when the optional descriptor is populated, so legacy callers that
        # leave the fields at None see no behaviour change.
        if self.geometry is not None and self.geometry.n_quad != self.quadrature.n_points:
            raise ValueError(
                f"GeometrySummary.n_quad ({self.geometry.n_quad}) does not "
                f"match quadrature.n_points ({self.quadrature.n_points})."
            )
        expected_n_dof = self.n_nodes * self.dim
        if self.local_force is not None and self.local_force.n_dof != expected_n_dof:
            raise ValueError(
                f"LocalForceDescriptor.n_dof ({self.local_force.n_dof}) does "
                f"not match n_nodes * dim ({expected_n_dof}) for "
                f"{self.element_type!r}."
            )
        if self.local_tangent is not None and self.local_tangent.n_dof != expected_n_dof:
            raise ValueError(
                f"LocalTangentDescriptor.n_dof ({self.local_tangent.n_dof}) "
                f"does not match n_nodes * dim ({expected_n_dof}) for "
                f"{self.element_type!r}."
            )
        # Configuration / stress-measure consistency: TL must pair with PK2,
        # UL with Cauchy. This guard catches IRs hand-constructed with
        # mismatched contracts (e.g. configuration="reference" but
        # stress_measure="cauchy").
        if self.material_eval is not None:
            if self.configuration == "reference" and self.material_eval.stress_measure != "pk2":
                raise ValueError(
                    f"configuration='reference' requires "
                    f"MaterialEvalContract.stress_measure='pk2'; got "
                    f"{self.material_eval.stress_measure!r}."
                )
            if self.configuration == "current" and self.material_eval.stress_measure != "cauchy":
                raise ValueError(
                    f"configuration='current' requires "
                    f"MaterialEvalContract.stress_measure='cauchy'; got "
                    f"{self.material_eval.stress_measure!r}."
                )

    # ------------------------------------------------------------------
    # Serialization (recovery-plan P4-1 / P4-5).
    #
    # ElementIR carries numpy arrays via QuadratureRule and a basis-function
    # object; the round-trip serialization here is intentionally narrow —
    # it captures the *contract surface* (element identity, formulation,
    # configuration, integration rule, and the four enrichment dataclasses)
    # but not the basis / quadrature numerics, which are reconstructible
    # from the element_type via the existing `create_*_element_ir` helpers.
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the contract surface to a JSON-compatible dict.

        Always emits the four enrichment keys (with ``None`` when the
        corresponding descriptor is unset) so consumers can round-trip
        them; legacy dicts without these keys are accepted by
        :meth:`from_dict` and rebuild with safe defaults.
        """
        return {
            "element_type": self.element_type,
            "n_nodes": self.n_nodes,
            "dim": self.dim,
            "formulation": self.formulation,
            "configuration": self.configuration,
            "integration_rule": self.integration_rule.value,
            "geometry": self.geometry.to_dict() if self.geometry is not None else None,
            "material_eval": (
                self.material_eval.to_dict() if self.material_eval is not None else None
            ),
            "local_force": (self.local_force.to_dict() if self.local_force is not None else None),
            "local_tangent": (
                self.local_tangent.to_dict() if self.local_tangent is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ElementIR:
        """Deserialize the contract surface, rebuilding basis / quadrature
        from the recorded element_type via the canonical constructors.

        Accepts both legacy dicts (without the P4-1 enrichment keys) and
        enriched dicts. Missing enrichment keys rebuild as ``None``.
        """
        element_type = d["element_type"]
        formulation = d.get("formulation", "total_lagrangian")
        configuration = d.get("configuration", "reference")
        integration_rule = IntegrationRule(d.get("integration_rule", "full"))
        # Rebuild basis / quadrature from the canonical constructors.
        constructors: dict[str, Any] = {
            "hex8": (hex8_basis, hex8_quadrature, hex8_reduced_quadrature),
            "tet4": (tet4_basis, tet4_quadrature, None),
            "tet10": (tet10_basis, tet10_quadrature, None),
            "hex20": (hex20_basis, hex20_quadrature, None),
        }
        if element_type not in constructors:
            raise ValueError(
                f"Cannot deserialize ElementIR with element_type={element_type!r}; "
                "additional element families are planned for Plan B phase B5."
            )
        basis_fn, quad_fn, reduced_quad_fn = constructors[element_type]
        if integration_rule == IntegrationRule.REDUCED and reduced_quad_fn is not None:
            quad_obj = reduced_quad_fn()
        else:
            quad_obj = quad_fn()
        # Optional enrichment fields.
        raw_geom = d.get("geometry")
        geometry = GeometrySummary.from_dict(raw_geom) if raw_geom else None
        raw_meval = d.get("material_eval")
        material_eval = MaterialEvalContract.from_dict(raw_meval) if raw_meval else None
        raw_force = d.get("local_force")
        local_force = LocalForceDescriptor.from_dict(raw_force) if raw_force else None
        raw_tangent = d.get("local_tangent")
        local_tangent = LocalTangentDescriptor.from_dict(raw_tangent) if raw_tangent else None
        return cls(
            element_type=element_type,
            n_nodes=int(d["n_nodes"]),
            dim=int(d["dim"]),
            basis=basis_fn(),
            quadrature=quad_obj,
            formulation=formulation,
            configuration=configuration,
            integration_rule=integration_rule,
            geometry=geometry,
            material_eval=material_eval,
            local_force=local_force,
            local_tangent=local_tangent,
        )


def hex8_basis() -> BasisFunctions:
    """Create Hex8 trilinear basis functions."""
    return BasisFunctions(n_nodes=8)


def hex8_quadrature() -> QuadratureRule:
    """2x2x2 Gauss quadrature for Hex8.

    Points at +/- 1/sqrt(3), all weights = 1.0.
    Integrates exactly polynomials up to degree 3 in each direction.
    """
    g = 1.0 / np.sqrt(3.0)
    # Build all 2^3 = 8 combinations
    coords_1d = np.array([-g, +g])
    pts = np.array(
        [[xi, eta, zeta] for xi in coords_1d for eta in coords_1d for zeta in coords_1d],
        dtype=np.float64,
    )
    weights = np.ones(8, dtype=np.float64)
    return QuadratureRule(points=pts, weights=weights)


def hex8_reduced_quadrature() -> QuadratureRule:
    """1-point Gauss quadrature at the centre of the reference cube (Plan B §B5.4).

    Single quadrature point at ``(0, 0, 0)`` with weight ``8.0``
    (the volume of ``[-1, 1]^3``). This rule integrates all polynomials
    of total degree 1 exactly — sufficient for constant-strain patches.

    Warning
    -------
    Reduced Hex8 is rank-deficient without hourglass control. Non-constant
    deformation modes (hourglass modes) produce zero strain at the centre
    point and therefore contribute no stiffness. Plan B §B5.5 adds the
    Flanagan-Belytschko hourglass controller; until that is wired up,
    reduced Hex8 should only be used for constant-strain verification.
    """
    from mechdsl.codegen.hex8_reduced_tables import (
        HEX8_QUAD_POINTS_REDUCED,
        HEX8_QUAD_WEIGHTS_REDUCED,
    )

    return QuadratureRule(
        points=HEX8_QUAD_POINTS_REDUCED.copy(),
        weights=HEX8_QUAD_WEIGHTS_REDUCED.copy(),
    )


def create_hex8_element_ir(
    formulation: str = "total_lagrangian",
    configuration: str = "reference",
    integration_rule: IntegrationRule = IntegrationRule.FULL,
) -> ElementIR:
    """Create a complete Hex8 ElementIR.

    Parameters
    ----------
    formulation
        ``"total_lagrangian"`` (default, Plan A) or ``"updated_lagrangian"``
        (Plan B §B1).
    configuration
        ``"reference"`` (default, Plan A) or ``"current"`` (Plan B §B1.3).
        The configuration determines which Jacobian (J0 vs j) downstream
        emitters will select. P1-1 only carries the tag; P1-2 populates the
        actual j-Jacobian slots.
    integration_rule
        :attr:`IntegrationRule.FULL` (default, 2x2x2 = 8 Gauss points) or
        :attr:`IntegrationRule.REDUCED` (1-point centre, Plan B §B5.4).
        Reduced integration requires hourglass control (Plan B §B5.5) to be
        stable on non-constant strains.
    """
    if integration_rule == IntegrationRule.REDUCED:
        quad = hex8_reduced_quadrature()
    else:
        quad = hex8_quadrature()
    return ElementIR(
        element_type="hex8",
        n_nodes=8,
        dim=3,
        basis=hex8_basis(),
        quadrature=quad,
        formulation=formulation,
        configuration=configuration,
        integration_rule=integration_rule,
    )


# ---------------------------------------------------------------------------
# Tet4 constructors  (Plan B §B5.1)
# ---------------------------------------------------------------------------


def tet4_basis() -> BasisFunctions:
    """Create Tet4 linear basis functions (4 nodes on the reference tet)."""
    return BasisFunctions(n_nodes=4)


def tet4_quadrature() -> QuadratureRule:
    """1-point centroid quadrature for Tet4.

    Single Gauss point at the centroid (1/4, 1/4, 1/4) with weight 1/6.
    This rule integrates constants exactly, which is sufficient for the
    linear Tet4 basis.  The weight equals the reference-tet volume so that
    ∫_tet 1 dV = w * 1 = 1/6.
    """
    pts = np.array([[0.25, 0.25, 0.25]], dtype=np.float64)
    weights = np.array([1.0 / 6.0], dtype=np.float64)
    return QuadratureRule(points=pts, weights=weights)


def create_tet4_element_ir(
    formulation: str = "total_lagrangian",
    configuration: str = "reference",
) -> ElementIR:
    """Create a complete Tet4 ElementIR.

    Parameters
    ----------
    formulation
        ``"total_lagrangian"`` (default). Updated Lagrangian is planned for
        Plan B §B1.
    configuration
        ``"reference"`` (default) or ``"current"`` (Plan B §B1.3).

    Notes
    -----
    Tet4 uses 1-point centroid quadrature and is susceptible to volumetric
    locking with near-incompressible materials (nu -> 0.5).  B-bar / F-bar
    stabilisation is deferred to Plan B §B5.3.
    """
    return ElementIR(
        element_type="tet4",
        n_nodes=4,
        dim=3,
        basis=tet4_basis(),
        quadrature=tet4_quadrature(),
        formulation=formulation,
        configuration=configuration,
    )


# ---------------------------------------------------------------------------
# Tet10 constructors  (Plan B §B5.2)
# ---------------------------------------------------------------------------


def tet10_basis() -> BasisFunctions:
    """Create Tet10 quadratic basis functions (10 nodes on the reference tet)."""
    return BasisFunctions(n_nodes=10)


def tet10_quadrature() -> QuadratureRule:
    """4-point symmetric Gauss quadrature for Tet10 (Keast/Zienkiewicz §5.5).

    Four quadrature points, each with weight 1/24.  The sum of weights equals
    1/6 (= reference-tet volume).  The rule integrates all polynomials up to
    degree 2 exactly, which is the minimum needed for the quadratic Tet10 basis.

    Point coordinates in (xi, eta, zeta):
      a = (5 - sqrt(5)) / 20, b = (5 + 3*sqrt(5)) / 20
      Q0: (a, a, a)   Q1: (b, a, a)   Q2: (a, b, a)   Q3: (a, a, b)
    """
    from mechdsl.codegen.tet10_tables import TET10_QUAD_POINTS, TET10_QUAD_WEIGHTS

    return QuadratureRule(points=TET10_QUAD_POINTS.copy(), weights=TET10_QUAD_WEIGHTS.copy())


def create_tet10_element_ir(
    formulation: str = "total_lagrangian",
    configuration: str = "reference",
) -> ElementIR:
    """Create a complete Tet10 ElementIR.

    Parameters
    ----------
    formulation
        ``"total_lagrangian"`` (default). Updated Lagrangian is planned for
        Plan B §B1.
    configuration
        ``"reference"`` (default) or ``"current"`` (Plan B §B1.3).

    Notes
    -----
    Tet10 uses 4-point symmetric Gauss quadrature which integrates degree-2
    polynomials exactly, matching the quadratic Tet10 basis.  Tet10 is
    substantially less susceptible to volumetric locking than Tet4.
    """
    return ElementIR(
        element_type="tet10",
        n_nodes=10,
        dim=3,
        basis=tet10_basis(),
        quadrature=tet10_quadrature(),
        formulation=formulation,
        configuration=configuration,
    )


# ---------------------------------------------------------------------------
# Hex20 constructors  (Plan B §B5.3)
# ---------------------------------------------------------------------------


def hex20_basis() -> BasisFunctions:
    """Create Hex20 serendipity basis functions (20 nodes on the reference hex)."""
    return BasisFunctions(n_nodes=20)


def hex20_quadrature() -> QuadratureRule:
    """3x3x3 = 27-point Gauss quadrature for Hex20.

    Tensor product of 3-point 1-D Gauss rules:
      xi_i in {-sqrt(3/5), 0, +sqrt(3/5)}, weights {5/9, 8/9, 5/9}.
    Sum of 27 weights = 8 (volume of [-1,1]^3).
    This rule integrates polynomials up to degree 5 in each direction,
    which is sufficient for the quadratic serendipity Hex20 basis.
    """
    from mechdsl.codegen.hex20_tables import HEX20_QUAD_POINTS, HEX20_QUAD_WEIGHTS

    return QuadratureRule(points=HEX20_QUAD_POINTS.copy(), weights=HEX20_QUAD_WEIGHTS.copy())


def create_hex20_element_ir(
    formulation: str = "total_lagrangian",
    configuration: str = "reference",
) -> ElementIR:
    """Create a complete Hex20 ElementIR.

    Parameters
    ----------
    formulation
        ``"total_lagrangian"`` (default). Updated Lagrangian is planned for
        Plan B §B1.
    configuration
        ``"reference"`` (default) or ``"current"`` (Plan B §B1.3).

    Notes
    -----
    Hex20 uses 3x3x3 = 27-point Gauss quadrature. The 27x20 = 540 element-
    level ops per quadrature traversal is close to the 512-line-per-@ti.func
    JIT budget. Sub-function splitting for Taichi codegen is deferred to
    Plan B phase B5.
    """
    return ElementIR(
        element_type="hex20",
        n_nodes=20,
        dim=3,
        basis=hex20_basis(),
        quadrature=hex20_quadrature(),
        formulation=formulation,
        configuration=configuration,
    )
