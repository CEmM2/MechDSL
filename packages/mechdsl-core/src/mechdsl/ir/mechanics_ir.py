"""Mechanics IR — ProblemIR schema with construction-time validation.

This is the semantic center of the FEM compiler pipeline.
All information flows through ProblemIR before lowering to ElementIR.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

from mechdsl.symbolic.convected import UnsupportedError

if TYPE_CHECKING:
    # Type-only: keeps the SymPy-heavy symbolic.energy off the IR import path
    # (ProblemIR is imported broadly). The `derived_energy` field is validated
    # by duck-typing in __post_init__, so the concrete class is not needed at
    # runtime; `from __future__ import annotations` makes the annotation a string.
    from mechdsl.symbolic.energy import EnergyModel

# ---------------------------------------------------------------------------
# Error classes (from ir.md)
# ---------------------------------------------------------------------------


class BoundaryRegionError(ValueError):
    """Raised when a BC references an undeclared mesh region.

    Spec reference: 08-VERIFICATION.md §2.3 M4.
    """


class Formulation(Enum):
    TOTAL_LAGRANGIAN = "total_lagrangian"
    UPDATED_LAGRANGIAN = "updated_lagrangian"


class Configuration(Enum):
    """Tags fields, gradients, and stress measures as living in the reference
    (material) or current (spatial) configuration.

    Plan B §B1.3 (Configuration-aware IR refactor) introduces this enum as the
    single source of truth for configuration-branching downstream of ProblemIR.
    Any emitter that needs to know whether to push forward PK2 → Cauchy or use
    det(J0) vs det(j) MUST read this enum on the IR — not sniff the material
    type, directive string, or formulation name.

    Consistency invariant (enforced in :meth:`ProblemIR.__post_init__`):
      - :attr:`Formulation.TOTAL_LAGRANGIAN` ⇔ :attr:`Configuration.REFERENCE`
      - :attr:`Formulation.UPDATED_LAGRANGIAN` ⇔ :attr:`Configuration.CURRENT`

    The split between Formulation and Configuration exists because later Plan B
    phases (B2 curvilinear, B4 hyperelastic, B6 damage) may introduce additional
    configuration variants (e.g. a mixed intermediate configuration for
    multiplicative plasticity) without widening the Formulation enum.
    """

    REFERENCE = "reference"
    CURRENT = "current"


class ElementType(Enum):
    """Element types known to the compiler.

    Support tier (per ``README.md`` Support tiers and
    ``dev/plans/recovery_plan_latex_contract.md`` Phase 1 (R0)):

    - **MVP-stable**: ``HEX8``. Only this element is part of the canonical
      compile path on the Taichi backend.
    - **experimental**: ``TET4``, ``TET10``, ``HEX20``. Preserved in tree but
      not part of the contract surface.
    """

    HEX8 = "hex8"
    TET4 = "tet4"  # experimental
    TET10 = "tet10"  # experimental
    HEX20 = "hex20"  # experimental


class DynamicsMode(Enum):
    """Selector between implicit static and explicit dynamic time integration.

    Plan B §B7 (task P7-1) introduces this enum so the generator can emit
    either a Newton–Raphson solve (:attr:`STATIC`, default) or a central-
    difference ``advance_one_step(dt)`` kernel (:attr:`EXPLICIT`).  The choice
    is a compile-time property of :class:`ProblemIR` — runtime switching is
    not supported.

    Values
    ------
    STATIC
        Implicit Newton–Raphson with tangent-based CG solve.  Existing Plan A
        behaviour; this is the default when ``dynamics_mode`` is omitted.
    EXPLICIT
        Central-difference explicit dynamics with lumped mass.  The emitted
        driver exposes ``advance_one_step(dt)`` and carries a velocity field
        ``v`` alongside the displacement field ``u``.  No linear solver is
        emitted in this mode.
    """

    STATIC = "static"
    EXPLICIT = "explicit"


class IntegrationRule(Enum):
    """Quadrature rule selector — orthogonal axis to :class:`ElementType`.

    Plan B §B5.4 introduces this enum so the element topology (hex8, tet4, ...)
    and the integration rule (full vs reduced Gauss) can vary independently.
    Each element type defines its own FULL default; REDUCED is only meaningful
    for hex8 today but the enum is shared so future element types (hex20
    reduced, etc.) reuse the same vocabulary.

    Values
    ------
    FULL
        Element-specific default rule (for Hex8: 2x2x2 = 8 Gauss points).
    REDUCED
        Element-specific reduced rule (for Hex8: 1-point centre). Unstable
        without hourglass control — see Plan B §B5.5.
    """

    FULL = "full"
    REDUCED = "reduced"


class BCType(Enum):
    DIRICHLET = "dirichlet"
    NEUMANN = "neumann"


# Traction may be:
#   - a symbolic string ("t_bar", "1e3") referencing a legacy named load,
#   - a 3-component numeric vector specifying explicit components, or
#   - None for non-Neumann BCs.
# The numeric form lets directive-driven Neumann BCs ("--traction \"0 0 -1000\"")
# round-trip through the IR without a separate symbolic-load registry.
TractionT = str | tuple[float, float, float] | None


@dataclass(frozen=True)
class BoundaryCondition:
    """A single boundary condition specification.

    For Neumann BCs, ``traction`` carries the load (string symbol or
    3-vector) and ``surface_tag`` identifies the mesh sideset on which it
    acts. When ``surface_tag`` is ``None`` the BC's ``name`` is used as the
    surface identifier — this preserves back-compat with directive-derived
    BCs that historically used ``name`` for both purposes.
    """

    name: str
    bc_type: BCType
    field_name: str = "u"
    components: tuple[int, ...] = (0, 1, 2)
    value: float | str = 0.0
    traction: TractionT = None
    surface_tag: str | None = None

    def __post_init__(self) -> None:
        # Normalize sequence-form traction to a length-3 tuple of floats so
        # downstream consumers can rely on a canonical shape.
        if isinstance(self.traction, (list, tuple)):
            try:
                tv = tuple(float(x) for x in self.traction)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"BoundaryCondition(name={self.name!r}) traction sequence must "
                    f"contain numeric components; got {self.traction!r}. "
                    "Validation added in post_recovery_plan Phase 1 (P1-1)."
                ) from exc
            if len(tv) != 3:
                raise ValueError(
                    f"BoundaryCondition(name={self.name!r}) traction vector must "
                    f"have length 3, got length {len(tv)}. "
                    "Validation added in post_recovery_plan Phase 1 (P1-1)."
                )
            object.__setattr__(self, "traction", tv)
        # A Neumann BC with no traction has no physical content; reject it
        # at construction time rather than emitting a silent zero load.
        if self.bc_type == BCType.NEUMANN and self.traction is None:
            raise ValueError(
                f"BoundaryCondition(name={self.name!r}, bc_type=neumann) requires "
                "a traction specification (symbolic string or 3-vector). "
                "Validation added in post_recovery_plan Phase 1 (P1-1)."
            )

    @property
    def effective_surface_tag(self) -> str:
        """Return ``surface_tag`` if set, otherwise the BC ``name``.

        Lowering passes use this property so callers do not need to repeat
        the fallback rule. Introduced in post_recovery_plan Phase 1 (P1-1)
        to give Phase 1 lowering a single, explicit surface identifier.
        """
        return self.surface_tag if self.surface_tag is not None else self.name

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        traction: Any = list(self.traction) if isinstance(self.traction, tuple) else self.traction
        return {
            "name": self.name,
            "bc_type": self.bc_type.value,
            "field_name": self.field_name,
            "components": list(self.components),
            "value": self.value,
            "traction": traction,
            "surface_tag": self.surface_tag,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BoundaryCondition:
        """Deserialize from dict."""
        raw_traction = d.get("traction")
        traction: TractionT
        if isinstance(raw_traction, list):
            traction = tuple(float(x) for x in raw_traction)  # type: ignore[assignment]
        else:
            traction = raw_traction
        return cls(
            name=d["name"],
            bc_type=BCType(d["bc_type"]),
            field_name=d.get("field_name", "u"),
            components=tuple(d.get("components", (0, 1, 2))),
            value=d.get("value", 0.0),
            traction=traction,
            surface_tag=d.get("surface_tag"),
        )

    @classmethod
    def from_context(cls, raw: dict[str, Any], index: int = 0) -> BoundaryCondition:
        """Adapt a frontend boundary dict to a :class:`BoundaryCondition`.

        The frontend boundary schema (produced by ``% mechanics`` directive
        parsing and by the legacy programmatic :func:`mechdsl.frontend.build_context`)
        differs from :meth:`from_dict` along two axes:

        - The boundary kind lives under the ``"type"`` key, not ``"bc_type"``.
        - The region label may appear under ``"name"``, ``"region"``, or
          ``"face"`` depending on whether the source was a directive or a
          test fixture; this adapter accepts all three with that priority.

        ``index`` provides a stable fallback name (``bc_<index>``) when the
        source dict carries none of the three name keys, matching the
        behaviour of the private adapters this method replaces.
        """
        bc_name = raw.get("name") or raw.get("region") or raw.get("face") or f"bc_{index}"
        components = tuple(raw.get("components", raw.get("dofs", (0, 1, 2))))
        raw_traction = raw.get("traction")
        traction: TractionT
        if isinstance(raw_traction, list):
            traction = tuple(float(x) for x in raw_traction)  # type: ignore[assignment]
        else:
            traction = raw_traction
        return cls(
            name=str(bc_name),
            bc_type=BCType(raw["type"]),
            field_name=str(raw.get("field_name", "u")),
            components=components,
            value=raw.get("value", 0.0),
            traction=traction,
            surface_tag=raw.get("surface_tag"),
        )


@dataclass(frozen=True)
class MaterialSpec:
    """Material model specification with named parameters."""

    model: str  # "svk" or "j2_power_law"
    params: dict[str, float | str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "model": self.model,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MaterialSpec:
        """Deserialize from dict."""
        return cls(
            model=d["model"],
            params=d.get("params", {}),
        )


# ---------------------------------------------------------------------------
# Optional semantic enrichment dataclasses.
#
# These four small frozen dataclasses carry information that the original
# ProblemIR left implicit. They are *additive*: every field is optional
# with a safe default, so legacy callers continue working without source
# changes.
# ---------------------------------------------------------------------------


# Allowed values for `FieldSpec.kind`. Module-level so callers can introspect
# the supported set instead of guessing from the docstring.
ALLOWED_FIELD_KINDS: frozenset[str] = frozenset({"scalar", "vector", "tensor"})


def _freeze_metadata(raw: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Wrap ``raw`` as a read-only ``MappingProxyType``.

    Frozen dataclasses block attribute reassignment but not in-place mutation
    through nested dicts. Wrapping the metadata bag in a ``MappingProxyType``
    means ``problem.domain.metadata["bbox"] = [...]`` raises ``TypeError`` at
    write time, restoring the immutability invariant the IR rules require.

    The wrapper is constructed once at ``__post_init__`` time and cached on the
    frozen instance via ``object.__setattr__``.
    """
    return MappingProxyType(dict(raw or {}))


@dataclass(frozen=True)
class FieldSpec:
    """A solver field (unknown) the problem solves for.

    Most MVP problems carry a single vector displacement field ``u``;
    multi-field problems (e.g. mixed u-p formulations, planned Plan B)
    will declare additional ``FieldSpec`` entries in ``ProblemIR.fields``.

    ``kind`` is restricted to the values in :data:`ALLOWED_FIELD_KINDS`. The
    check runs at construction time so a typo like ``"vetcor"`` fails fast
    rather than propagating into emitted code.
    """

    name: str
    kind: str = "vector"  # one of ALLOWED_FIELD_KINDS
    components: int | None = None  # None = inferred from `kind` and dim

    def __post_init__(self) -> None:
        if self.kind not in ALLOWED_FIELD_KINDS:
            raise ValueError(
                f"FieldSpec(name={self.name!r}) kind={self.kind!r} is not supported; "
                f"allowed kinds are {sorted(ALLOWED_FIELD_KINDS)}. "
                "Wider field-kind support is planned for recovery-plan task P3-5."
            )

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "components": self.components}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FieldSpec:
        return cls(
            name=d["name"],
            kind=d.get("kind", "vector"),
            components=d.get("components"),
        )


@dataclass(frozen=True)
class FiberFieldSpec:
    """Per-element fiber-orientation field data for anisotropic models (HGO).

    constitutive_latex Phase 5 (P5-1). This is **field data**, deliberately
    distinct from :class:`MaterialSpec` scalar params: it carries one direction
    vector per fiber family (HGO uses two). Authored via the
    ``% mechanics fiber --family "x,y,z"`` directive as constant (uniform)
    directions, or supplied programmatically through
    :func:`mechdsl.frontend.build_context` ``fiber_data``. Genuinely
    heterogeneous per-element arrays remain a mesh-binding concern; this carrier
    holds the *declared* family directions that flow ProblemIR -> Element IR.

    Immutable; validated at construction (each family is a nonzero 3-vector).
    Directions are stored as authored — consumers normalise (the HGO oracle
    normalises internally), so the carry does not silently rescale user input.
    """

    families: tuple[tuple[float, float, float], ...]

    def __post_init__(self) -> None:
        if not self.families:
            raise ValueError(
                "FiberFieldSpec requires at least one fiber family; an "
                "anisotropic model needs its fiber direction(s) declared."
            )
        for k, a in enumerate(self.families):
            if len(a) != 3:
                raise ValueError(
                    f"FiberFieldSpec family {k} must be a 3-vector (x, y, z), got {a!r}."
                )
            if sum(float(c) * float(c) for c in a) <= 0.0:
                raise ValueError(
                    f"FiberFieldSpec family {k} must be a nonzero direction, got {a!r}."
                )

    @property
    def n_families(self) -> int:
        return len(self.families)

    def to_dict(self) -> dict[str, Any]:
        return {"families": [list(a) for a in self.families]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FiberFieldSpec:
        return cls(families=tuple((float(a[0]), float(a[1]), float(a[2])) for a in d["families"]))


@dataclass(frozen=True)
class DomainSpec:
    """Optional domain-level metadata (geometry / region naming hints).

    Kept intentionally permissive in the MVP: ``metadata`` is a free-form
    bag so callers can attach problem-specific keys (e.g. bounding box,
    geometry source path) without rotating the schema. Phase 4 (R3) is the
    place to introduce stricter typed domain descriptors if the bag turns
    out to be too loose in practice.

    The bag is exposed as a read-only ``MappingProxyType`` to honour the
    frozen-dataclass invariant — write attempts raise ``TypeError``. Callers
    that need to mutate should construct a new ``DomainSpec`` with an updated
    metadata dict.
    """

    name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DomainSpec:
        return cls(name=d.get("name"), metadata=dict(d.get("metadata", {})))


@dataclass(frozen=True)
class MeshContract:
    """Requirements the supplied mesh must satisfy.

    ``region_tags`` enumerates the mesh region names referenced by
    boundary conditions; downstream layers can use it to validate that
    the supplied mesh actually carries those tags before localisation.
    ``metadata`` is reserved for forward-compatible extensions and is
    exposed as a read-only ``MappingProxyType``.
    """

    region_tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {"region_tags": list(self.region_tags), "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MeshContract:
        return cls(
            region_tags=tuple(d.get("region_tags", ())),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass(frozen=True)
class ResidualContract:
    """Optional descriptor of the weak-form residual structure.

    ``terms`` enumerates the residual contributions present in the problem
    (e.g. ``("internal_force", "external_force")`` for a static problem).
    ``weak_form_label`` is a short human-readable name for the formulation
    family. Both are optional in the MVP-stable subset. ``metadata`` is
    exposed as a read-only ``MappingProxyType`` to honour the frozen
    invariant.
    """

    terms: tuple[str, ...] = ()
    weak_form_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "terms": list(self.terms),
            "weak_form_label": self.weak_form_label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResidualContract:
        return cls(
            terms=tuple(d.get("terms", ())),
            weak_form_label=d.get("weak_form_label"),
            metadata=dict(d.get("metadata", {})),
        )


# Roles that the equation classifier may emit but that carry no committed
# constitutive meaning. A role of ``unknown`` (or ``None``) must NOT be
# inferred into a real constitutive role — it is recorded as an auxiliary
# definition so the serialized IR still explains that the compiler saw the
# equation without claiming to understand its physics.
#
# ``auxiliary_definition`` is bucketed here because it is the classifier's own
# label for "a definition with no committed physics" — the same semantic bucket
# as ``unknown``. Normalizing it to the canonical ``"auxiliary"`` token keeps a
# single auxiliary spelling in the serialized record regardless of whether the
# role arrived as ``unknown``/``None`` (no classification) or
# ``auxiliary_definition`` (classified as auxiliary). The empty string covers a
# present-but-blank role field.
_NON_COMMITTED_ROLES: frozenset[str] = frozenset({"unknown", "auxiliary_definition", ""})


@dataclass(frozen=True)
class LatexSemantics:
    """Record of the LaTeX-derived semantics the compiler understood (fgram P5-1).

    This is the serializable explanation of *what the compiler read* from a
    LaTeX source: which fields were declared, which constitutive roles were
    tagged on which symbols, the weak-form label, and (when a ``$...$`` math
    block was present) the per-equation role assignments.

    It is **additive and advisory**: the authoritative IR configuration still
    lives in :class:`ProblemIR`'s typed fields. This record exists so the
    serialized bundle can be reviewed and golden-diffed without re-parsing the
    source. All members are JSON-primitive tuples/strings so :meth:`to_dict`
    stays round-trip-safe.

    ``role`` values are taken verbatim from directive-tagged metadata (which
    is authoritative per the Phase 4 handoff). A role of ``unknown`` /
    ``None`` from the equation classifier is downgraded to ``"auxiliary"``
    rather than inferred into a constitutive role.
    """

    fields: tuple[str, ...] = ()
    constitutive: tuple[tuple[str, str], ...] = ()  # (symbol, role) pairs
    weak_form_label: str | None = None
    equations: tuple[tuple[str, str], ...] = ()  # (lhs, role) pairs

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": list(self.fields),
            "constitutive": [{"symbol": s, "role": r} for s, r in self.constitutive],
            "weak_form_label": self.weak_form_label,
            "equations": [{"lhs": lhs, "role": role} for lhs, role in self.equations],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LatexSemantics:
        return cls(
            fields=tuple(d.get("fields", ())),
            constitutive=tuple(
                (entry["symbol"], entry["role"]) for entry in d.get("constitutive", [])
            ),
            weak_form_label=d.get("weak_form_label"),
            equations=tuple((entry["lhs"], entry["role"]) for entry in d.get("equations", [])),
        )


# ---------------------------------------------------------------------------
# MVP-stable subset contract.
#
# The "MVP-stable subset" is the set of `ProblemIR` configurations that the
# canonical compile path on the Taichi backend supports today (see the
# README.md support tiers). Configurations outside this subset may still
# construct successfully (`ProblemIR.__post_init__` keeps experimental enum
# values valid for in-tree research code), but `compile_latex(profile="mvp")`
# and other stability-promised entry points must reject them at the IR
# boundary so that the failure points at the IR rather than surfacing deep
# inside codegen / runtime.
#
# Keep this descriptor in lock-step with `ALLOWED_PROFILES` in
# `packages/mechdsl-core/src/mechdsl/__init__.py` and with the support-tier
# table in `README.md`. Adding a new MVP-stable value here is a contract
# change and must be paired with the corresponding doc/test updates.
# ---------------------------------------------------------------------------


class MvpSubsetViolation(UnsupportedError):
    """A `ProblemIR` configuration falls outside the MVP-stable subset.

    Subclasses :class:`UnsupportedError` so callers that already catch the
    generic "outside supported subset" exception (per `.claude/rules/ir.md`)
    keep working without source changes. Use the more specific class when
    callers want to distinguish "outside MVP-stable contract" from "outside
    the symbolic engine's supported subset".
    """


@dataclass(frozen=True)
class MvpStableSubset:
    """Snapshot of the MVP-stable `ProblemIR` configuration contract.

    Immutable, frozen-dataclass descriptor of every value that the canonical
    compile path on the Taichi backend supports today. The fields are tuples
    (not sets) so the iteration order matches the documentation tables; the
    equality/membership checks below are linear in the table size, which is
    deliberately small (single-digit entries per axis).

    Adding a new MVP-stable value is a contract change. Pair every edit here
    with:

    1. A row in `dev/design_docs/04-MECHANICS-IR.md` §3.1 (MVP-stable
       subset).
    2. A row/note in the `README.md` Support tiers table.
    3. A test case in
       `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p3_4.py`.
    """

    dim: tuple[int, ...]
    formulations: tuple[Formulation, ...]
    element_types: tuple[ElementType, ...]
    materials: tuple[str, ...]
    dynamics_modes: tuple[DynamicsMode, ...]
    configurations: tuple[Configuration, ...]


# Single canonical instance. Treat as a read-only constant — never mutate.
MVP_STABLE_SUBSET: MvpStableSubset = MvpStableSubset(
    dim=(3,),
    formulations=(Formulation.TOTAL_LAGRANGIAN,),
    element_types=(ElementType.HEX8,),
    materials=("svk", "j2_power_law"),
    dynamics_modes=(DynamicsMode.STATIC,),
    configurations=(Configuration.REFERENCE,),
)


# Required parameter sets for MVP-stable material models, used by
# construction-time validation. Models not listed here skip the check —
# experimental constitutive models declare their own parameter contracts
# elsewhere and will join this table as they enter the MVP-stable subset.
_MVP_MATERIAL_REQUIRED_PARAMS: dict[str, frozenset[str]] = {
    "svk": frozenset({"E", "nu"}),
    "j2_power_law": frozenset({"E", "nu", "sigma_y0", "K", "n"}),
}


@dataclass(frozen=True)
class ProblemIR:
    """Mechanics IR — the semantic center of the compiler pipeline.

    Captures the full problem specification: dimension, formulation,
    element type, material, and boundary conditions. Immutable and
    validated at construction time.

    Parameters
    ----------
    dim
        Spatial dimension. The MVP accepts only ``3``.
    formulation
        Kinematic formulation. The MVP accepts only
        :attr:`Formulation.TOTAL_LAGRANGIAN`.
    element_type
        Element family. The MVP accepts only :attr:`ElementType.HEX8`.
    material
        Material model specification and its named parameters.
    boundaries
        Boundary conditions attached to named mesh regions.
    coord_spatial
        Spatial coordinate names used for emitted metadata and validation.
    coord_material
        Material coordinate names used for emitted metadata and validation.
    declared_regions
        Optional frozenset of valid mesh region names. When provided,
        every :class:`BoundaryCondition` name must appear in this set.

    Raises
    ------
    ValueError
        If the problem leaves the MVP subset, has inconsistent coordinate
        metadata, or omits all boundary conditions.
    BoundaryRegionError
        If ``declared_regions`` is provided and a boundary references an
        undeclared region name.
    """

    dim: int
    formulation: Formulation
    element_type: ElementType
    material: MaterialSpec
    boundaries: tuple[BoundaryCondition, ...]
    coord_spatial: tuple[str, ...] = ("x", "y", "z")
    coord_material: tuple[str, ...] = ("X", "Y", "Z")
    declared_regions: frozenset[str] | None = None
    configuration: Configuration | None = None
    dynamics_mode: DynamicsMode | None = None

    # Optional semantic enrichment. All four default to a safe empty /
    # None value so legacy callers continue working without source changes.
    fields: tuple[FieldSpec, ...] = ()
    domain: DomainSpec | None = None
    mesh_contract: MeshContract | None = None
    residual_contract: ResidualContract | None = None

    # LaTeX-derived semantic record. Optional and advisory — captures what
    # the compiler understood from the LaTeX source (declared fields,
    # constitutive roles, weak-form label, equation roles) so the serialized
    # bundle can explain itself. None for IRs built without a LaTeX semantic
    # source (legacy / programmatic callers).
    latex_semantics: LatexSemantics | None = None

    # The LaTeX-derived symbolic energy model (PK2 stress + material
    # tangent) when the constitutive law was derived from a strain-energy
    # density rather than dispatched by model name. This is the carrier that
    # lets codegen emit from the derived energy instead of the hard-coded
    # named-model switch. Appended last, defaulting to ``None`` so existing
    # ProblemIR constructors pass no new argument and are unaffected. Held as
    # a Python object (SymPy expressions inside) and deliberately NOT
    # serialized into `to_dict`: SymPy does not JSON-encode cleanly, and the
    # codegen contract reads it off the in-memory IR / ArtifactBundle, not
    # the serialized dict.
    derived_energy: EnergyModel | None = None

    # Per-element fiber-orientation field data for anisotropic models
    # (HGO). Field data, NOT a scalar material param — carried separately
    # from MaterialSpec.params and flowed through to the Element IR. Appended
    # last, defaulting to None so every existing ProblemIR constructor is
    # unaffected.
    fiber_field: FiberFieldSpec | None = None

    # Formulation → Configuration mapping.
    _FORMULATION_TO_CONFIG: ClassVar[dict[Formulation, Configuration]] = {
        Formulation.TOTAL_LAGRANGIAN: Configuration.REFERENCE,
        Formulation.UPDATED_LAGRANGIAN: Configuration.CURRENT,
    }

    def __post_init__(self) -> None:
        """Validate at construction time."""
        # Auto-infer configuration from formulation when not explicitly
        # provided — callers should not need to manually pass configuration when
        # the formulation implies it.
        if self.configuration is None:
            inferred = self._FORMULATION_TO_CONFIG.get(self.formulation)
            if inferred is None:
                raise ValueError(
                    f"Cannot infer configuration for formulation "
                    f"{self.formulation.value}; pass configuration explicitly."
                )
            object.__setattr__(self, "configuration", inferred)

        assert self.configuration is not None  # guaranteed by auto-inference above

        # Auto-infer dynamics_mode to STATIC when omitted. Matches the
        # `configuration` auto-infer pattern above: a ProblemIR without
        # `dynamics_mode` gets the implicit static Newton solve.
        if self.dynamics_mode is None:
            object.__setattr__(self, "dynamics_mode", DynamicsMode.STATIC)

        assert self.dynamics_mode is not None  # guaranteed by auto-inference above

        if self.dim != 3:
            raise ValueError(
                f"dim={self.dim} not supported. "
                "Only dim=3 for MVP; 2D support is planned for Plan B phase B2."
            )
        # Formulation/Configuration consistency — see Configuration docstring.
        # This guard catches EXPLICIT mismatches (e.g. UL + REFERENCE).
        if (
            self.formulation == Formulation.TOTAL_LAGRANGIAN
            and self.configuration != Configuration.REFERENCE
        ):
            raise ValueError(
                f"Formulation {self.formulation.value} requires configuration="
                f"{Configuration.REFERENCE.value}, got "
                f"{self.configuration.value}. "
                "Plan B §B1.3 pins total_lagrangian to the reference configuration."
            )
        if (
            self.formulation == Formulation.UPDATED_LAGRANGIAN
            and self.configuration != Configuration.CURRENT
        ):
            raise ValueError(
                f"Formulation {self.formulation.value} requires configuration="
                f"{Configuration.CURRENT.value}, got "
                f"{self.configuration.value}. "
                "Plan B §B1.3 pins updated_lagrangian to the current configuration."
            )
        # element type: hex8, tet4, tet10, hex20 supported; others are not yet implemented
        _SUPPORTED_ELEMENT_TYPE_VALUES = {"hex8", "tet4", "tet10", "hex20"}
        if self.element_type.value not in _SUPPORTED_ELEMENT_TYPE_VALUES:
            raise ValueError(
                f"Element type {self.element_type.value!r} not supported. "
                "Additional element families are planned for Plan B phase B5."
            )
        if self.material.model not in (
            "svk",
            "j2_power_law",
            "perzyna",
            "johnson_cook",
            "neo_hookean",
            "mooney_rivlin",
            "ogden",
            "hgo",
            "lemaitre",
        ):
            raise ValueError(
                f"Unknown material model: {self.material.model}. "
                "Additional constitutive models are planned across Plan B phases "
                "B6 (damage)."
            )
        # need at least one boundary
        if not self.boundaries:
            raise ValueError("At least one boundary condition required.")
        if len(self.coord_spatial) != self.dim:
            raise ValueError(
                f"Expected {self.dim} spatial coordinates, got {len(self.coord_spatial)}"
            )
        if len(self.coord_material) != self.dim:
            raise ValueError(
                f"Expected {self.dim} material coordinates, got {len(self.coord_material)}"
            )
        # Check BC names against declared regions when regions are provided.
        if self.declared_regions is not None:
            for bc in self.boundaries:
                if bc.name not in self.declared_regions:
                    raise BoundaryRegionError(
                        f"Boundary condition '{bc.name}' references an undeclared mesh region. "
                        f"Declared regions: {sorted(self.declared_regions)}. "
                        "Ensure the BC name matches a region tag in the mesh."
                    )

        # ------------------------------------------------------------------
        # Targeted validation for semantics that were previously
        # implicit. Each block below converts a class of silent acceptance
        # (a malformed IR that used to surface as a cryptic codegen / runtime
        # error) into a clear ValueError raised at construction time.
        # ------------------------------------------------------------------

        # BC region names must be unique across the boundary tuple.
        # Two BCs with the same `name` would either silently overwrite each
        # other or produce conflicting load assemblers downstream.
        seen_bc_names: set[str] = set()
        for bc in self.boundaries:
            if bc.name in seen_bc_names:
                raise ValueError(
                    f"Duplicate boundary condition name {bc.name!r}. "
                    "Each region tag must appear at most once; if you need "
                    "two BCs on the same region, declare distinct region "
                    "tags in the mesh and reference each separately."
                )
            seen_bc_names.add(bc.name)

        # BC component indices must lie in [0, dim). Out-of-range
        # values used to flow through to codegen and produce off-by-one
        # array slices or silent zero rows.
        for bc in self.boundaries:
            for c in bc.components:
                if c < 0 or c >= self.dim:
                    raise ValueError(
                        f"Boundary condition {bc.name!r} component "
                        f"index {c} is out of range for dim={self.dim}; "
                        f"valid indices are 0..{self.dim - 1}."
                    )

        # Spatial and material coordinate names must be unique.
        # Repeated names produce ambiguous metadata downstream.
        if len(set(self.coord_spatial)) != len(self.coord_spatial):
            raise ValueError(
                f"coord_spatial={self.coord_spatial!r} has duplicate names; "
                "spatial coordinate labels must be unique."
            )
        if len(set(self.coord_material)) != len(self.coord_material):
            raise ValueError(
                f"coord_material={self.coord_material!r} has duplicate names; "
                "material coordinate labels must be unique."
            )

        # Declared field names must be unique. Two FieldSpec entries
        # with the same `name` are always a configuration bug.
        if self.fields:
            seen_field_names: set[str] = set()
            for f in self.fields:
                if f.name in seen_field_names:
                    raise ValueError(
                        f"Duplicate field name {f.name!r} in `fields`. "
                        "Each FieldSpec.name must be unique."
                    )
                seen_field_names.add(f.name)

            # BC `field_name` must reference a declared field when
            # `fields` is populated. Catches typos like `field_name="ux"` vs
            # `FieldSpec(name="u")`.
            declared_field_names = {f.name for f in self.fields}
            for bc in self.boundaries:
                if bc.field_name not in declared_field_names:
                    raise ValueError(
                        f"Boundary condition {bc.name!r} references field "
                        f"{bc.field_name!r}, but the declared `fields` set "
                        f"is {sorted(declared_field_names)}. Either add a "
                        f"FieldSpec with that name or correct the BC."
                    )

        # The required-params check lives in `assert_mvp_stable()` — see
        # that method for the rationale. In-tree research code builds
        # minimal IRs for shape testing without touching the constitutive
        # path, so validating required params at every IR construction would
        # break those fixtures. The check still fires at the canonical
        # compile-path boundary (`compile_latex(profile="mvp")` calls
        # `assert_mvp_stable()`).

        # Validate the derived-energy carrier at construction time (IR
        # discipline). A no-op when None (the default, so every legacy
        # constructor is unaffected); when present it must be a fully-formed
        # energy model carrying symbolic PK2 stress and tangent so codegen can
        # emit from it. Duck-typed to avoid importing the heavy symbolic.energy
        # module at IR-construction time.
        if self.derived_energy is not None:
            de = self.derived_energy
            # Three recognised derivation shapes, each carrying the symbolic
            # data its codegen path consumes (duck-typed to avoid importing the
            # heavy symbolic modules at IR-construction time):
            #   - invariant  (EnergyModel):          closed-form pk2 + rank-4 tangent
            #   - spectral   (SpectralEnergyModel):  principal stresses S_i(lambda)
            #   - anisotropic(AnisotropicEnergyModel): iso + fiber stress + Ibar4
            shapes = {
                "invariant": ("pk2", "tangent", "strain_symbols"),
                "spectral": ("principal_pk2", "stretch_symbols", "param_symbols"),
                "anisotropic": ("iso_pk2", "fiber_pk2", "fiber_ibar4", "strain_symbols"),
            }
            if not any(all(hasattr(de, a) for a in attrs) for attrs in shapes.values()):
                raise ValueError(
                    "derived_energy must be a recognised constitutive model carrying "
                    "its derived stress: a mechdsl.symbolic.energy.EnergyModel "
                    "(invariant), SpectralEnergyModel (Ogden), or AnisotropicEnergyModel "
                    "(HGO); got an object missing all of their required attributes."
                )

        # Validate the fiber-field carrier at construction time (IR
        # discipline). A no-op when None (the default). Duck-typed to keep this
        # cheap; FiberFieldSpec already validates its own families in its
        # __post_init__.
        if self.fiber_field is not None and not hasattr(self.fiber_field, "families"):
            raise ValueError(
                "fiber_field must be a mechdsl.ir.mechanics_ir.FiberFieldSpec "
                "carrying per-family direction vectors."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict for golden comparison."""
        assert self.configuration is not None  # guaranteed by __post_init__
        assert self.dynamics_mode is not None  # guaranteed by __post_init__
        return {
            "dim": self.dim,
            "formulation": self.formulation.value,
            "element_type": self.element_type.value,
            "material": self.material.to_dict(),
            "boundaries": [bc.to_dict() for bc in self.boundaries],
            "coord_spatial": list(self.coord_spatial),
            "coord_material": list(self.coord_material),
            "declared_regions": sorted(self.declared_regions) if self.declared_regions else None,
            "configuration": self.configuration.value,
            "dynamics_mode": self.dynamics_mode.value,
            # Enrichment fields. Always emitted so consumers can round-trip
            # them; legacy dicts without these keys are accepted in `from_dict` and
            # rebuild with safe defaults.
            "fields": [f.to_dict() for f in self.fields],
            "domain": self.domain.to_dict() if self.domain is not None else None,
            "mesh_contract": (
                self.mesh_contract.to_dict() if self.mesh_contract is not None else None
            ),
            "residual_contract": (
                self.residual_contract.to_dict() if self.residual_contract is not None else None
            ),
            # LaTeX-derived semantic record. Always emitted (None when absent)
            # so consumers can round-trip it; legacy dicts without the key rebuild
            # with `latex_semantics=None`.
            "latex_semantics": (
                self.latex_semantics.to_dict() if self.latex_semantics is not None else None
            ),
            # Fiber field data. Emitted only when present so every existing
            # (fiber-less) golden stays byte-identical; from_dict rebuilds None when
            # the key is absent.
            **({"fiber_field": self.fiber_field.to_dict()} if self.fiber_field is not None else {}),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProblemIR:
        """Deserialize from dict.

        Accepts both legacy dicts (without the Phase-3 enrichment keys) and
        enriched dicts. Missing enrichment keys rebuild with safe defaults so
        every existing golden file continues to round-trip.
        """
        raw_regions = d.get("declared_regions")
        declared_regions = frozenset(raw_regions) if raw_regions is not None else None
        # configuration is optional — when missing, auto-inferred from
        # formulation in __post_init__. Legacy TL goldens without a
        # "configuration" key auto-infer to REFERENCE (correct).
        raw_cfg = d.get("configuration")
        configuration = Configuration(raw_cfg) if raw_cfg is not None else None
        # dynamics_mode is optional — legacy dicts without the key
        # auto-infer to STATIC in __post_init__.
        raw_dyn = d.get("dynamics_mode")
        dynamics_mode = DynamicsMode(raw_dyn) if raw_dyn is not None else None
        # Enrichment fields. All optional; missing keys rebuild as empty /
        # None.
        raw_fields = d.get("fields", ())
        fields_tuple = tuple(FieldSpec.from_dict(f) for f in raw_fields) if raw_fields else ()
        raw_domain = d.get("domain")
        domain = DomainSpec.from_dict(raw_domain) if raw_domain else None
        raw_mesh = d.get("mesh_contract")
        mesh_contract = MeshContract.from_dict(raw_mesh) if raw_mesh else None
        raw_residual = d.get("residual_contract")
        residual_contract = ResidualContract.from_dict(raw_residual) if raw_residual else None
        # LaTeX semantic record. Optional; missing key rebuilds as None so
        # every existing golden continues to round-trip.
        raw_latex = d.get("latex_semantics")
        latex_semantics = LatexSemantics.from_dict(raw_latex) if raw_latex else None
        raw_fiber = d.get("fiber_field")
        fiber_field = FiberFieldSpec.from_dict(raw_fiber) if raw_fiber else None
        return cls(
            dim=d["dim"],
            formulation=Formulation(d["formulation"]),
            element_type=ElementType(d["element_type"]),
            material=MaterialSpec.from_dict(d["material"]),
            boundaries=tuple(BoundaryCondition.from_dict(bc) for bc in d["boundaries"]),
            coord_spatial=tuple(d.get("coord_spatial", ("x", "y", "z"))),
            coord_material=tuple(d.get("coord_material", ("X", "Y", "Z"))),
            declared_regions=declared_regions,
            configuration=configuration,
            dynamics_mode=dynamics_mode,
            fields=fields_tuple,
            domain=domain,
            mesh_contract=mesh_contract,
            residual_contract=residual_contract,
            latex_semantics=latex_semantics,
            fiber_field=fiber_field,
        )

    # ------------------------------------------------------------------
    # Boundary / domain semantic helpers.
    #
    # Every downstream layer (lowering, codegen, solver, mesh validation)
    # used to re-derive the same fact: "the BC name equals the mesh
    # boundary tag". The two helpers below centralize that assumption on
    # the IR — the semantic center — so consumers read a single source of
    # truth instead of scattering the implicit contract across layers.
    # ------------------------------------------------------------------

    def required_region_tags(self) -> tuple[str, ...]:
        """Mesh region tags this problem requires from its mesh.

        Returns the union of names declared via :attr:`boundaries` (always
        present) and :attr:`mesh_contract`'s ``region_tags`` (when the
        explicit contract is set). Ordering: the explicit contract names
        come first (their order is documentation-meaningful), then any BC
        names that the contract did not enumerate.
        """
        bc_names = tuple(bc.name for bc in self.boundaries)
        if self.mesh_contract is None:
            return bc_names
        out: list[str] = list(self.mesh_contract.region_tags)
        for name in bc_names:
            if name not in out:
                out.append(name)
        return tuple(out)

    def derived_mesh_contract(self) -> MeshContract:
        """Materialize a :class:`MeshContract` for this problem.

        When :attr:`mesh_contract` is set, returns it as-is. When the
        contract is implicit (the default for legacy IRs), synthesizes one
        from :meth:`required_region_tags` so downstream layers can always
        treat the contract as a real object instead of branching on
        ``mesh_contract is None``.
        """
        if self.mesh_contract is not None:
            return self.mesh_contract
        return MeshContract(region_tags=self.required_region_tags())

    # ------------------------------------------------------------------
    # Frontend context-dict adapter.
    # ------------------------------------------------------------------

    @classmethod
    def from_context(cls, ctx: dict[str, Any]) -> ProblemIR:
        """Adapt a frontend context dict to a validated :class:`ProblemIR`.

        The context-dict schema (the thin pre-IR representation produced by
        :func:`mechdsl.frontend.build_context` and the ``% mechanics``
        directive parser) carries different keys than the :meth:`to_dict`
        serialization shape: ``cell_type`` instead of ``element_type``,
        ``material_type`` instead of a nested ``material`` dict, and
        boundary entries that may use ``region`` / ``face`` / ``dofs``
        instead of ``name`` / ``components``.

        Before P3-2, three private adapters reimplemented this mapping in
        :mod:`mechdsl` (used by :func:`compile_latex`),
        ``test_full_pipeline.py``, and ``test_formulation_switching.py``.
        This classmethod replaces all three so the adapter lives on the
        IR — the semantic center — where it belongs.

        Parameters
        ----------
        ctx
            Frontend context dict. Required keys: ``dim``, ``formulation``,
            ``cell_type``, ``material_type``, ``boundaries``. Optional:
            ``params`` (defaults to an empty dict).

        Returns
        -------
        ProblemIR
            Validated IR. Construction-time errors (unknown enum values,
            empty boundary list, mismatched coordinate tuples) propagate
            unchanged.
        """
        boundaries = tuple(
            BoundaryCondition.from_context(bc, idx)
            for idx, bc in enumerate(ctx.get("boundaries", []))
        )
        return cls(
            dim=int(ctx["dim"]),
            formulation=Formulation(ctx["formulation"]),
            element_type=ElementType(ctx["cell_type"]),
            material=MaterialSpec(
                model=ctx["material_type"],
                params=dict(ctx.get("params", {})),
            ),
            boundaries=boundaries,
            fiber_field=cls._fiber_field_from_context(ctx),
        )

    @staticmethod
    def _fiber_field_from_context(ctx: dict[str, Any]) -> FiberFieldSpec | None:
        """Map fiber-direction directive entries to a :class:`FiberFieldSpec`.

        The ``% mechanics fiber --family "x,y,z"`` directive accumulates one
        ``{"direction": (x, y, z), "source_line": n}`` entry per family under
        ``ctx['fiber_families']`` (see ``frontend/directives.py``). Returns
        ``None`` when no fiber directive was declared, so isotropic problems
        carry no fiber field.
        """
        entries = ctx.get("fiber_families")
        if not entries:
            return None
        families: list[tuple[float, float, float]] = []
        for entry in entries:
            d = entry["direction"]
            families.append((float(d[0]), float(d[1]), float(d[2])))
        return FiberFieldSpec(families=tuple(families))

    # ------------------------------------------------------------------
    # LaTeX-semantic adapter.
    # ------------------------------------------------------------------

    @classmethod
    def from_latex_semantics(cls, ctx: dict[str, Any]) -> ProblemIR:
        """Build a validated :class:`ProblemIR` from LaTeX-derived semantics.

        This is the LaTeX-semantic constructor (fgram Phase 5). Unlike
        :meth:`from_context`, which reads only the thin directive core
        (``dim`` / ``cell_type`` / ``formulation`` / ``material_type`` /
        ``boundaries``), this adapter additionally consumes the richer
        semantic objects a LaTeX source carries through the frontend:

        - ``fields`` → :class:`FieldSpec` entries on :attr:`fields`.
        - ``residual_contract`` / ``weak_forms`` →
          :class:`ResidualContract` on :attr:`residual_contract`.
        - ``constitutive`` role tags and any ``$...$`` equation roles →
          a serializable :class:`LatexSemantics` record on
          :attr:`latex_semantics` so the bundle explains what the compiler
          understood.

        Convergence (Phase 4 handoff): the MVP-stable *core* of the returned
        IR is identical to :meth:`from_context` for the same ``ctx`` — this
        adapter only *adds* enrichment, it never diverges on the core
        configuration. Symbolic / constitutive meaning is not re-derived here:
        constitutive role tags are taken verbatim from the (authoritative)
        directive metadata, and equation roles that the classifier reported as
        ``unknown`` are recorded as ``"auxiliary"`` rather than inferred.

        Parameters
        ----------
        ctx
            Frontend context dict from :func:`mechdsl.frontend.parse` /
            :func:`mechdsl.frontend.parse_compile_context`. Required keys are
            those of :meth:`from_context`; the LaTeX-semantic keys
            (``fields``, ``constitutive``, ``weak_forms``,
            ``residual_contract``, ``math``) are all optional.

        Returns
        -------
        ProblemIR
            Validated, enriched IR. Construction-time errors propagate
            unchanged.
        """
        boundaries = tuple(
            BoundaryCondition.from_context(bc, idx)
            for idx, bc in enumerate(ctx.get("boundaries", []))
        )
        fields = cls._fields_from_context(ctx)
        residual_contract = cls._residual_contract_from_context(ctx)
        latex_semantics = cls._latex_semantics_from_context(ctx, fields)
        return cls(
            dim=int(ctx["dim"]),
            formulation=Formulation(ctx["formulation"]),
            element_type=ElementType(ctx["cell_type"]),
            material=MaterialSpec(
                model=ctx["material_type"],
                params=dict(ctx.get("params", {})),
            ),
            boundaries=boundaries,
            fields=fields,
            residual_contract=residual_contract,
            latex_semantics=latex_semantics,
            fiber_field=cls._fiber_field_from_context(ctx),
        )

    @staticmethod
    def _fields_from_context(ctx: dict[str, Any]) -> tuple[FieldSpec, ...]:
        """Map ``ctx['fields']`` directive entries to :class:`FieldSpec`.

        The directive normalizer emits ``{"name", "kind", "space", "order"}``
        dicts (see ``frontend/directives.py``); only ``name`` and ``kind``
        carry into the IR FieldSpec — ``space`` / ``order`` are SymPDE-stage
        metadata and stay out of the MVP IR.
        """
        return tuple(
            FieldSpec(name=str(entry["name"]), kind=str(entry.get("kind", "vector")))
            for entry in ctx.get("fields", [])
        )

    @staticmethod
    def _residual_contract_from_context(ctx: dict[str, Any]) -> ResidualContract | None:
        """Map weak-form metadata to a :class:`ResidualContract`.

        The directive layer already assembles a ``residual_contract`` dict
        (terms / weak_form_label / metadata) under ``ctx['residual_contract']``
        when a ``% mechanics weak_form`` directive is present. Reuse it
        directly so the LaTeX path and the directive layer agree on the
        contract shape. Returns ``None`` when no weak form was declared.
        """
        # A ProblemIR permits exactly one weak-form declaration. The directive
        # layer enforces this at parse time (a second ``% mechanics weak_form``
        # raises ParseError) and emits the singular ``residual_contract`` next to
        # a *single-entry* ``weak_forms`` list — so the two keys co-existing is
        # the normal state, not a conflict. A caller assembling ``ctx`` directly
        # can still smuggle in a ``weak_forms`` list carrying more than one form:
        # a genuine duplicate singular-field declaration. Reject it explicitly
        # rather than silently honouring only ``residual_contract`` (issue #274).
        # The check runs before the ``residual_contract`` lookup so it also
        # catches a duplicate ``weak_forms`` list passed without a contract.
        weak_forms = ctx.get("weak_forms")
        if isinstance(weak_forms, (list, tuple)) and len(weak_forms) > 1:
            labels = [
                wf.get("weak_form_label") if isinstance(wf, dict) else wf for wf in weak_forms
            ]
            raise ValueError(
                f"ctx declares {len(weak_forms)} weak forms ({labels!r}); "
                "ProblemIR.residual_contract is singular — declare exactly one "
                "'% mechanics weak_form' per source. The directive layer enforces "
                "this at parse time; multi-form support is planned for Plan B."
            )

        raw = ctx.get("residual_contract")
        if not raw:
            return None
        # A non-mapping ``residual_contract`` (e.g. a list of contracts or a bare
        # string) is likewise rejected explicitly rather than letting
        # ResidualContract.from_dict fail obscurely or silently build a wrong
        # contract.
        if not isinstance(raw, dict):
            raise ValueError(
                "ctx['residual_contract'] must be a single weak-form contract "
                f"mapping; got {type(raw).__name__}. A ProblemIR permits exactly "
                "one weak-form declaration — the directive layer rejects duplicate "
                "'% mechanics weak_form' directives at parse time."
            )
        return ResidualContract.from_dict(raw)

    @staticmethod
    def _latex_semantics_from_context(
        ctx: dict[str, Any], fields: tuple[FieldSpec, ...]
    ) -> LatexSemantics | None:
        """Assemble the serializable :class:`LatexSemantics` record.

        Records *what the compiler understood* — declared field names,
        directive-tagged constitutive roles (authoritative), the weak-form
        label, and any equation roles from a ``$...$`` math block. Equation
        roles reported as ``unknown`` / ``None`` are downgraded to
        ``"auxiliary"`` rather than inferred into a constitutive role (Phase 4
        handoff). Returns ``None`` when the context carries no LaTeX-derived
        semantics at all, so legacy / programmatic IRs stay unannotated.
        """
        constitutive = tuple(
            (str(entry["symbol"]), str(entry["role"])) for entry in ctx.get("constitutive", [])
        )
        residual = ctx.get("residual_contract") or {}
        weak_form_label = residual.get("weak_form_label")

        equations: list[tuple[str, str]] = []
        math = ctx.get("math")
        if isinstance(math, dict):
            for eq in math.get("equations", ()):
                lhs, role = ProblemIR._equation_lhs_and_role(eq)
                equations.append((lhs, role))

        field_names = tuple(f.name for f in fields)
        if not (field_names or constitutive or weak_form_label or equations):
            return None
        return LatexSemantics(
            fields=field_names,
            constitutive=constitutive,
            weak_form_label=weak_form_label,
            equations=tuple(equations),
        )

    @staticmethod
    def _equation_lhs_and_role(eq: Any) -> tuple[str, str]:
        """Extract ``(lhs, role)`` from an equation record, downgrading
        non-committed roles to ``"auxiliary"``.

        Accepts both the mapping form (e.g. a serialized
        ``EquationSemantics``) and any object exposing ``lhs`` / ``role``
        attributes, so the adapter does not depend on a single equation
        representation.
        """
        if isinstance(eq, Mapping):
            lhs = str(eq.get("lhs", ""))
            raw_role = eq.get("role")
        else:
            lhs = str(getattr(eq, "lhs", ""))
            raw_role = getattr(eq, "role", None)
        role = "" if raw_role is None else str(raw_role)
        if role in _NON_COMMITTED_ROLES:
            role = "auxiliary"
        return lhs, role

    # ------------------------------------------------------------------
    # MVP-stable subset contract.
    # ------------------------------------------------------------------

    def assert_mvp_stable(self) -> None:
        """Reject configurations outside the MVP-stable subset.

        The canonical compile path (`compile_latex(profile="mvp")`) must
        promise that every accepted IR is in the MVP-stable subset, so that
        users hitting an experimental combination get a clean IR-level
        rejection instead of a deep codegen/runtime failure.

        Raises
        ------
        MvpSubsetViolation
            When :attr:`dim`, :attr:`formulation`, :attr:`element_type`,
            :attr:`material.model`, :attr:`dynamics_mode`, or
            :attr:`configuration` is outside :data:`MVP_STABLE_SUBSET`.
            The message names the offending field, the actual value, the
            allowed values, and the Plan-B phase that adds support.
        """
        if self.dim not in MVP_STABLE_SUBSET.dim:
            raise MvpSubsetViolation(
                f"dim={self.dim} is outside the MVP-stable subset "
                f"{MVP_STABLE_SUBSET.dim}. "
                "2D / non-3D problems are planned for Plan B phase B2."
            )
        if self.formulation not in MVP_STABLE_SUBSET.formulations:
            raise MvpSubsetViolation(
                f"formulation={self.formulation.value!r} is outside the "
                f"MVP-stable subset "
                f"{tuple(f.value for f in MVP_STABLE_SUBSET.formulations)}. "
                "Updated Lagrangian is planned for Plan B phase B1."
            )
        if self.element_type not in MVP_STABLE_SUBSET.element_types:
            raise MvpSubsetViolation(
                f"element_type={self.element_type.value!r} is outside the "
                f"MVP-stable subset "
                f"{tuple(e.value for e in MVP_STABLE_SUBSET.element_types)}. "
                "Additional element families are planned for Plan B phase B5."
            )
        # A LaTeX-derived constitutive law supplies its own stress/tangent, so
        # the named-model allow-list does not gate it (mirrors the codegen
        # rationale in taichi_printer.emit_constitutive_update): the
        # strain-energy derivation, not the model name, defines the physics.
        if self.derived_energy is None and self.material.model not in MVP_STABLE_SUBSET.materials:
            raise MvpSubsetViolation(
                f"material.model={self.material.model!r} is outside the "
                f"MVP-stable subset {MVP_STABLE_SUBSET.materials}. "
                "Hyperelastic and damage models are planned for Plan B "
                "phases B4 and B6."
            )
        # `dynamics_mode` and `configuration` are auto-inferred in
        # `__post_init__` so they are never None at this point; the asserts
        # are for the type-checker.
        assert self.dynamics_mode is not None
        assert self.configuration is not None
        if self.dynamics_mode not in MVP_STABLE_SUBSET.dynamics_modes:
            raise MvpSubsetViolation(
                f"dynamics_mode={self.dynamics_mode.value!r} is outside the "
                f"MVP-stable subset "
                f"{tuple(d.value for d in MVP_STABLE_SUBSET.dynamics_modes)}. "
                "Explicit dynamics are planned for Plan B phase B7."
            )
        if self.configuration not in MVP_STABLE_SUBSET.configurations:
            raise MvpSubsetViolation(
                f"configuration={self.configuration.value!r} is outside the "
                f"MVP-stable subset "
                f"{tuple(c.value for c in MVP_STABLE_SUBSET.configurations)}. "
                "Current-configuration kinematics are planned for Plan B phase B1."
            )
        # Known MVP material models require their full parameter set.
        # Lives here (rather than in `__post_init__`) because in-tree
        # research code constructs minimal IRs for shape-only testing — the
        # check belongs to the production-readiness contract enforced by
        # the canonical compile path, not the bare IR schema.
        # A derived model's required parameters come from its strain-energy
        # LaTeX (enforced at emission, where the actual param names are known),
        # not from the named-model E/nu contract.
        required_params = (
            None
            if self.derived_energy is not None
            else _MVP_MATERIAL_REQUIRED_PARAMS.get(self.material.model)
        )
        if required_params is not None:
            missing = [k for k in required_params if k not in self.material.params]
            if missing:
                raise MvpSubsetViolation(
                    f"Material model {self.material.model!r} requires "
                    f"parameters {sorted(required_params)}; missing "
                    f"{missing}. Pass them via "
                    "`MaterialSpec(model=..., params={...})`."
                )

    def is_mvp_stable(self) -> bool:
        """Non-throwing variant of :meth:`assert_mvp_stable`.

        Returns ``True`` when the IR is in :data:`MVP_STABLE_SUBSET`,
        ``False`` otherwise. Useful for branching on the contract without
        catching exceptions; production callers that need the *reason* a
        configuration was rejected should call :meth:`assert_mvp_stable`
        and read the message.
        """
        try:
            self.assert_mvp_stable()
        except MvpSubsetViolation:
            return False
        return True
