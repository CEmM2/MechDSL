"""Artifact bundle model for golden comparison and codegen output tracking.

Stores all pipeline artifacts (IRs, contraction plans, emitted source) in an
immutable, serialisable bundle.  Content hashing enables golden-file regression
without sensitivity to cosmetic whitespace changes in emitted code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Type-only: keeps SymPy-heavy symbolic.energy off the codegen import path.
    # `derived_energy` rides as an opaque Python object (excluded from all
    # serialisation), so the concrete class is not needed at runtime.
    from mechdsl.ir.mechanics_ir import ProblemIR
    from mechdsl.lowering.fe_localise import LocalisationResult
    from mechdsl.symbolic.energy import EnergyModel


@dataclass(frozen=True)
class ContractionPlan:
    """Stores an optimised contraction plan for a single einsum.

    Attributes:
        einsum_string: The einsum subscript notation (e.g. ``"ij,jk->ik"``).
        contraction_path: Pairwise contraction order produced by *opt_einsum*.
        estimated_flops: Estimated floating-point operations for the contraction.
        tier: Einsum tier classification (1, 2, or 3) — the scheduling axis.
        family: Contraction family name (P9-2) — the realisation axis. Stored
            as the enum *name* string for JSON round-trip safety.  Defaults
            to ``"FALLBACK"`` so bundles serialised before P9-2 deserialise
            cleanly; the Taichi/MFEM/MOOSE printers treat ``"FALLBACK"`` as
            the legacy emission path.
    """

    einsum_string: str
    contraction_path: list[tuple[int, ...]] = field(default_factory=list)
    estimated_flops: int = 0
    tier: int = 0  # 1, 2, or 3 — 0 means unclassified
    family: str = "FALLBACK"  # enum-name string (see Family registry)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "einsum_string": self.einsum_string,
            "contraction_path": [list(pair) for pair in self.contraction_path],
            "estimated_flops": self.estimated_flops,
            "tier": self.tier,
            "family": self.family,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ContractionPlan:
        """Deserialise from a dict.

        Raises ``KeyError`` if required fields are missing and ``TypeError``
        on structural problems.
        """
        try:
            einsum_string = d["einsum_string"]
        except KeyError:
            raise KeyError(
                "ContractionPlan.from_dict: missing required field 'einsum_string'"
            ) from None

        raw_path = d.get("contraction_path", [])
        contraction_path = [tuple(pair) for pair in raw_path]

        return cls(
            einsum_string=einsum_string,
            contraction_path=contraction_path,
            estimated_flops=d.get("estimated_flops", 0),
            tier=d.get("tier", 0),
            family=d.get("family", "FALLBACK"),
        )


@dataclass(frozen=True)
class ArtifactBundle:
    """Stores all pipeline artifacts for golden comparison and codegen.

    The bundle captures:
    * The serialised ProblemIR (``problem_ir_dict``).
    * The canonical ElementIR contract-surface dict (``element_ir_dict``) —
      added by recovery-plan P4-5 (R3.5) to reflect the post-P4-1 IR
      ownership: ``ElementIR`` is the primary semantic carrier and the
      ``ContractionPlan`` tuple is the derived optimizer view. Defaults to
      an empty dict so pre-P4-5 bundles round-trip cleanly.
    * Element IR metadata (``element_ir_summary``) — legacy summary kept
      for back-compat with pre-P4-5 golden files. Excludes callable basis
      functions that cannot be serialised.
    * Optimised contraction plans (``contraction_plans``) — derived view.
    * The emitted Taichi source code (``emitted_source``).
    * Free-form ``metadata`` (commit hash, timestamps, compiler version, …).

    Ownership hierarchy (post-P4-5):

        problem_ir_dict   ──primary semantic input
        element_ir_dict   ──primary semantic carrier (ElementIR with
                            P4-1 contract enrichment)
        element_ir_summary──legacy summary, derived from element_ir_dict
        contraction_plans ──derived optimizer view over element_ir_dict

    ``content_hash`` is computed over the semantic content (IRs + plans)
    and deliberately ignores ``emitted_source`` so that cosmetic
    whitespace changes do not invalidate golden files.
    """

    problem_ir_dict: dict[str, Any]
    element_ir_summary: dict[str, Any]
    contraction_plans: tuple[ContractionPlan, ...] = ()
    emitted_source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Canonical ElementIR contract-surface dict. Default empty so older
    # bundles deserialise cleanly without the new key.
    element_ir_dict: dict[str, Any] = field(default_factory=dict)
    # Optional source for the Neumann ``f_ext`` initialisation kernel(s).
    # ``None`` when the problem has no Neumann BCs with numeric traction
    # (legacy symbolic-string traction stays handled by the existing
    # imported numeric injection path). Kept off the ``content_hash`` for
    # the same reason ``emitted_source`` is — its contents are derived
    # from ``problem_ir_dict``'s boundary list.
    f_ext_kernel: str | None = None

    # Parallel Python-object channel carrying the LaTeX-derived symbolic
    # energy model (PK2 stress + material tangent) so the Taichi printer
    # can emit the constitutive ``@ti.func`` from the derived energy
    # instead of the hard-coded named-model switch. Held off the JSON path
    # entirely (`to_dict`, `from_dict`, `content_hash`, and the
    # `to_json`/`from_json` round-trip): the model carries SymPy
    # expressions that do not serialise cleanly, and golden files compare
    # the JSON-able semantic surface only. ``None`` for every named-model
    # bundle so the JSON path and content hash are byte-identical to
    # bundles without a derived energy.
    derived_energy: EnergyModel | None = field(default=None, compare=False)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_pipeline(
        cls,
        problem_ir: ProblemIR,
        localisation: LocalisationResult,
        contraction_plans: tuple[ContractionPlan, ...],
        emitted_source: str = "",
    ) -> ArtifactBundle:
        """Create an artifact bundle from pipeline results.

        Parameters
        ----------
        problem_ir : ProblemIR
            The semantic problem specification.
        localisation : LocalisationResult
            Result of :func:`mechdsl.lowering.fe_localise.localise`.
        contraction_plans : tuple[ContractionPlan, ...]
            Optimised contraction plans (one per einsum spec).
        emitted_source : str
            Taichi source code emitted by the backend (may be empty during
            early pipeline stages).

        Returns
        -------
        ArtifactBundle
            A fully populated, immutable artifact bundle.
        """
        element_ir = localisation.element_ir
        element_ir_summary: dict[str, Any] = {
            "element_type": element_ir.element_type,
            "n_nodes": element_ir.n_nodes,
            "dim": element_ir.dim,
            "n_quadrature_points": element_ir.quadrature.n_points,
            "formulation": element_ir.formulation,
            # Surface the execution-contract enrichment when present so
            # downstream consumers (and golden artifacts) see the enriched
            # ElementIR's contract blocks. Each key stays at None when the
            # corresponding descriptor is unset, preserving round-trip
            # compatibility with older bundles.
            "geometry": (
                element_ir.geometry.to_dict() if element_ir.geometry is not None else None
            ),
            "material_eval": (
                element_ir.material_eval.to_dict() if element_ir.material_eval is not None else None
            ),
            "local_force": (
                element_ir.local_force.to_dict() if element_ir.local_force is not None else None
            ),
            "local_tangent": (
                element_ir.local_tangent.to_dict() if element_ir.local_tangent is not None else None
            ),
        }

        # Store the canonical ElementIR contract surface alongside the legacy
        # summary. The summary stays for golden-file back-compat;
        # `element_ir_dict` is the primary semantic carrier.
        return cls(
            problem_ir_dict=problem_ir.to_dict(),
            element_ir_summary=element_ir_summary,
            contraction_plans=contraction_plans,
            emitted_source=emitted_source,
            element_ir_dict=element_ir.to_dict(),
            # Carry the LaTeX-derived energy (if any) into codegen via the
            # Python-object channel. ``None`` for named-model IRs.
            derived_energy=problem_ir.derived_energy,
        )

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    def content_hash(self) -> str:
        """Compute a semantic content hash for golden comparison.

        The hash covers ``problem_ir_dict``, ``element_ir_summary`` and
        ``contraction_plans``.  It does **not** include ``emitted_source``
        or ``metadata`` so that cosmetic formatting differences (whitespace,
        comment rewording) and non-semantic metadata do not affect the hash.
        """
        hashable = {
            "problem_ir_dict": self.problem_ir_dict,
            "element_ir_summary": self.element_ir_summary,
            "contraction_plans": [cp.to_dict() for cp in self.contraction_plans],
        }
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Full serialisation to a JSON-compatible dict.

        Always emits ``element_ir_dict`` (the P4-5 canonical contract
        surface) so post-P4-5 consumers see the primary semantic carrier;
        legacy ``element_ir_summary`` rides alongside for back-compat.
        """
        return {
            "problem_ir_dict": self.problem_ir_dict,
            "element_ir_summary": self.element_ir_summary,
            "contraction_plans": [cp.to_dict() for cp in self.contraction_plans],
            "emitted_source": self.emitted_source,
            "metadata": self.metadata,
            "element_ir_dict": self.element_ir_dict,
            "f_ext_kernel": self.f_ext_kernel,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArtifactBundle:
        """Deserialise from a dict.

        Raises ``KeyError`` when required fields (``problem_ir_dict``,
        ``element_ir_summary``) are missing and ``TypeError`` on structural
        problems. ``element_ir_dict`` is optional — pre-P4-5 bundles
        rebuild with an empty dict so legacy goldens continue to round-trip.
        """
        missing = [k for k in ("problem_ir_dict", "element_ir_summary") if k not in d]
        if missing:
            raise KeyError(
                f"ArtifactBundle.from_dict: missing required field(s): "
                f"{', '.join(repr(k) for k in missing)}"
            )

        raw_plans = d.get("contraction_plans", [])
        plans = tuple(ContractionPlan.from_dict(p) for p in raw_plans)

        return cls(
            problem_ir_dict=d["problem_ir_dict"],
            element_ir_summary=d["element_ir_summary"],
            contraction_plans=plans,
            emitted_source=d.get("emitted_source", ""),
            metadata=d.get("metadata", {}),
            element_ir_dict=d.get("element_ir_dict", {}),
            f_ext_kernel=d.get("f_ext_kernel"),
        )

    # ------------------------------------------------------------------
    # JSON convenience
    # ------------------------------------------------------------------

    def to_json(self, path: str | None = None) -> str:
        """Serialise to a JSON string.  Optionally write to *path*."""
        text = json.dumps(self.to_dict(), indent=2, sort_keys=True)
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_json(
        cls,
        json_str: str | None = None,
        path: str | None = None,
    ) -> ArtifactBundle:
        """Deserialise from a JSON string or file.

        Exactly one of *json_str* or *path* must be provided.

        Raises ``ValueError`` on invalid JSON and ``KeyError`` on missing
        required fields.
        """
        if json_str is not None and path is not None:
            raise ValueError("ArtifactBundle.from_json: provide json_str or path, not both")
        if json_str is None and path is None:
            raise ValueError("ArtifactBundle.from_json: provide either json_str or path")

        raw: str = json_str if json_str is not None else Path(path).read_text(encoding="utf-8")  # type: ignore[arg-type]

        try:
            d = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"ArtifactBundle.from_json: invalid JSON — {exc}") from exc

        return cls.from_dict(d)
