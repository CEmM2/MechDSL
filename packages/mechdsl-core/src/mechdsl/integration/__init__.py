"""MechDSL integration façade — AKMS-unaware machine-readable surface.

This module is the stable entry point that downstream adapters (Tier-2 AKMS
bridge) call.  It wraps existing MechDSL entry points behind a minimal,
machine-readable API and **never** triggers Taichi initialisation on import
or during the emit/transpile paths.

Five entry points (implemented across tasks P1-1 … P1-4):

- :func:`capabilities` — declare supported profiles, backends, actions.
- :func:`model_catalog` — enumerate all constitutive models with metadata.
- :func:`compile_from_sources` — wraps ``mechdsl.compile_latex`` (P1-2).
- :func:`transpile_algorithm` — wraps ``algo2code.transpile`` (P1-3).
- :func:`verify` — wraps the verify harness; Taichi-paying path (P1-4).

**Taichi-free guarantee (Tier-1 contract):**
Importing this module and calling :func:`capabilities` or
:func:`model_catalog` must not execute ``ti.init``.  Only :func:`verify`
is allowed to pay the Taichi cost, and it imports Taichi lazily.

Add no entry points beyond the five above without a plan-level decision
(YAGNI — this surface is a machine API contract, not a convenience library).
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from os import PathLike

    import numpy as np

__all__ = [
    "capabilities",
    "compile_from_sources",
    "model_catalog",
    "transpile_algorithm",
    "verify",
]


# ---------------------------------------------------------------------------
# capabilities()
# ---------------------------------------------------------------------------


def capabilities() -> dict:
    """Return a machine-readable capability manifest for this MechDSL install.

    The dict shape is part of the Tier-1 contract; downstream adapters
    (MechDSLRunner in compmech_reference_pack) key off every field listed
    here.  Do not remove or rename keys without a breaking-change notice.

    Returns
    -------
    dict
        ``{version, python, profiles, backends, actions,
        taichi_required_for, models}``

        - ``version`` — mechdsl-core package version string.
        - ``python`` — required Python version specifier.
        - ``profiles`` — sorted list of accepted ``compile_latex`` profile
          strings (derived from :data:`mechdsl.ALLOWED_PROFILES`).
        - ``backends`` — list of code-generation backends (MVP: taichi only).
        - ``actions`` — list of top-level actions this facade exposes.
        - ``taichi_required_for`` — subset of ``actions`` that call
          ``ti.init`` at runtime; the rest are guaranteed Taichi-free.
        - ``models`` — list of model names from :func:`model_catalog`.
    """
    # Import ALLOWED_PROFILES lazily from mechdsl.__init__ — that import is
    # safe because mechdsl.__init__ itself is already in sys.modules whenever
    # this sub-package is reachable, and it does NOT call ti.init.
    from mechdsl import ALLOWED_PROFILES

    catalog = model_catalog()
    return {
        "version": _mechdsl_version(),
        "python": ">=3.12,<3.13",
        "profiles": sorted(ALLOWED_PROFILES),
        "backends": ["taichi"],
        "actions": ["emit", "transpile", "verify"],
        "taichi_required_for": ["verify"],
        "models": [entry["name"] for entry in catalog],
    }


# ---------------------------------------------------------------------------
# model_catalog()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Static metadata for lib/plasticity* models.
#
# mechdsl.lib.plasticity, plasticity_kinematic, and plasticity_mixed exec
# algo2code-transpiled Taichi source at module import time, which fires
# ti.init.  We therefore CANNOT import those modules here.  Instead, their
# metadata is listed statically and kept in sync manually with the source.
#
# When any of these modules changes its Material dataclass or state
# variables, update the corresponding entry in _LIB_PLASTICITY_CATALOG below.
# ---------------------------------------------------------------------------

_LIB_PLASTICITY_CATALOG: list[dict] = [
    {
        "name": "j2_isotropic",
        "module": "mechdsl.lib.plasticity",
        "tier": "mvp",
        "dissipative": True,
        "params": ["E", "nu", "sigma_y0", "K", "n"],
        "state_variables": ["alpha"],
    },
    {
        "name": "j2_kinematic",
        "module": "mechdsl.lib.plasticity_kinematic",
        "tier": "experimental",
        "dissipative": True,
        "params": ["E", "nu", "sigma_y0", "H_kin"],
        "state_variables": ["Ep", "beta"],
    },
    {
        "name": "j2_mixed",
        "module": "mechdsl.lib.plasticity_mixed",
        "tier": "experimental",
        "dissipative": True,
        "params": ["E", "nu", "sigma_y0", "K", "n", "H_kin"],
        "state_variables": ["alpha", "Ep", "beta"],
    },
]


def model_catalog() -> list[dict]:
    """Enumerate all constitutive models with their metadata.

    Covers both ``mechdsl.symbolic.models.*`` (fully introspected via
    :class:`mechdsl.symbolic.constitutive.ConstitutiveModel`) and
    ``mechdsl.lib.plasticity*`` (statically catalogued — those modules call
    ``ti.init`` at import time so they cannot be imported here).

    Each entry has the shape::

        {
            "name":            str,          # canonical model identifier
            "module":          str,          # dotted import path of the owning module
            "tier":            "mvp" | "experimental",
            "dissipative":     bool,
            "params":          list[str],    # material parameter names
            "state_variables": list[str],    # internal state variable names
        }

    The ``module`` field is the dotted Python import path of the module that
    owns the model (e.g. ``"mechdsl.symbolic.models.svk"`` or
    ``"mechdsl.lib.plasticity"``).  Downstream adapters may use it for
    display or tracing purposes; it is NOT guaranteed to be importable from
    the Taichi-free path (lib/plasticity* modules call ``ti.init`` at import
    time).

    The ``params`` list is derived from the frozen dataclass that accompanies
    each model (e.g. ``SVKMaterial``, ``J2PowerLawMaterial``).  Lemaitre is
    the exception: it has no :class:`ConstitutiveModel` subclass in the tree
    yet (only a standalone ``lemaitre_return`` function); its entry is
    hand-written but its ``LemaitreMaterial`` dataclass fields are the source
    of truth for ``params``.

    Returns
    -------
    list[dict]
        Ordered: MVP models first (svk, j2_isotropic via lib/plasticity),
        then experimental symbolic models, then experimental lib models.
    """
    import copy

    # The heavy work (importlib imports + dataclass introspection of nine
    # modules) is memoised in _build_model_catalog().  We deep-copy each entry
    # per call so a caller mutating the returned list can never corrupt the
    # cached snapshot that the next caller (or capabilities()) will read.
    return [copy.deepcopy(entry) for entry in _build_model_catalog()]


@functools.lru_cache(maxsize=1)
def _build_model_catalog() -> tuple[dict, ...]:
    """Build the immutable model-catalog snapshot (memoised, runs once).

    Performs all the ``importlib`` imports and dataclass introspection that
    back :func:`model_catalog`.  Returned as a tuple so the cached value is a
    read-only snapshot; :func:`model_catalog` deep-copies it per call.
    """
    catalog: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Introspect symbolic/models/* via ConstitutiveModel subclasses.
    #    These imports are Taichi-free (numpy + sympy only).
    # ------------------------------------------------------------------

    # (module_dotted_path, model_class_name, material_class_name, tier)
    _SYMBOLIC_MODELS: list[tuple[str, str, str, str]] = [
        # MVP-stable (from symbolic/models/__init__.py docstring)
        (
            "mechdsl.symbolic.models.svk",
            "SVKModel",
            "SVKMaterial",
            "mvp",
        ),
        (
            "mechdsl.symbolic.models.j2_power_law",
            "J2Model",
            "J2PowerLawMaterial",
            "mvp",
        ),
        # Experimental hyperelastic
        (
            "mechdsl.symbolic.models.neo_hookean",
            "NeoHookeanModel",
            "NeoHookeanMaterial",
            "experimental",
        ),
        (
            "mechdsl.symbolic.models.mooney_rivlin",
            "MooneyRivlinModel",
            "MooneyRivlinMaterial",
            "experimental",
        ),
        (
            "mechdsl.symbolic.models.ogden",
            "OgdenModel",
            "OgdenMaterial",
            "experimental",
        ),
        (
            "mechdsl.symbolic.models.hgo",
            "HGOModel",
            "HGOMaterial",
            "experimental",
        ),
        # Experimental dissipative
        (
            "mechdsl.symbolic.models.perzyna",
            "PerzynaModel",
            "PerzynaMaterial",
            "experimental",
        ),
        (
            "mechdsl.symbolic.models.johnson_cook",
            "JohnsonCookModel",
            "JohnsonCookMaterial",
            "experimental",
        ),
    ]

    import dataclasses
    import importlib

    for module_path, model_cls_name, material_cls_name, tier in _SYMBOLIC_MODELS:
        mod = importlib.import_module(module_path)
        model_cls = getattr(mod, model_cls_name)
        material_cls = getattr(mod, material_cls_name)

        # Derive a sentinel instance to read state_variables and is_dissipative.
        # We read the property values from the class itself where possible, or
        # from a throw-away dummy instance with placeholder params.
        # For properties that don't depend on mat params (all current models),
        # instantiating with zeros/ones is safe.
        state_vars, is_dissipative = _introspect_model_class(model_cls, material_cls)

        # params: ordered field names from the Material dataclass
        params = [f.name for f in dataclasses.fields(material_cls)]

        catalog.append(
            {
                "name": _model_name_from_class(model_cls_name),
                "module": module_path,
                "tier": tier,
                "dissipative": is_dissipative,
                "params": params,
                "state_variables": list(state_vars),
            }
        )

    # ------------------------------------------------------------------
    # 2. Lemaitre — experimental, has no ConstitutiveModel subclass yet.
    #    Parameters sourced from LemaitreMaterial dataclass; state from
    #    LemaitreReturnResult fields (alpha_new, D_new).
    # ------------------------------------------------------------------
    _lemaitre_mod = importlib.import_module("mechdsl.symbolic.models.lemaitre")
    _lemaitre_fields = [f.name for f in dataclasses.fields(_lemaitre_mod.LemaitreMaterial)]
    catalog.append(
        {
            "name": "lemaitre",
            "module": "mechdsl.symbolic.models.lemaitre",
            "tier": "experimental",
            "dissipative": True,
            "params": _lemaitre_fields,
            "state_variables": ["alpha", "D"],
        }
    )

    # ------------------------------------------------------------------
    # 3. lib/plasticity* — statically catalogued (Taichi-bound at import).
    # ------------------------------------------------------------------
    catalog.extend(_LIB_PLASTICITY_CATALOG)

    return tuple(catalog)


# ---------------------------------------------------------------------------
# compile_from_sources()
# ---------------------------------------------------------------------------


def compile_from_sources(
    *,
    problem_source: str | None = None,
    energy_source: str | None = None,
    energy_file: str | PathLike[str] | None = None,
    profile: str = "mvp",
) -> dict:
    """Compile a LaTeX mechanics problem to a machine-readable summary dict.

    Wraps :func:`mechdsl.compile_latex` behind a stable façade that returns
    a JSON-serialisable summary rather than the raw
    :class:`~mechdsl.codegen.artifact.ArtifactBundle`.  **Taichi-free:**
    calling this function does not trigger ``ti.init``; Taichi is only
    initialised when the emitted source string is *executed* at runtime.

    Parameters
    ----------
    problem_source:
        LaTeX source text containing ``% mechanics`` directives that describe
        the FEM problem (dimension, element, material, boundary conditions,
        formulation).  Always required; omitting it raises ``ValueError``.
    energy_source:
        Optional self-contained nrpylatex strain-energy block (the same string
        accepted by :func:`mechdsl.compile_latex`'s ``energy_source`` kwarg).
        When provided, the compiled bundle carries a LaTeX-derived energy.
        Mutually exclusive with ``energy_file``.
    energy_file:
        Path to a ``.tex`` file holding the strain-energy block.  Mutually
        exclusive with ``energy_source``; forwarded as-is to
        :func:`mechdsl.compile_latex`.
    profile:
        Compile profile selector.  Only ``"mvp"`` is currently accepted.

    Returns
    -------
    dict
        ``{element_ir_summary, emitted_source, content_hash,
        derived_energy_present}``

        - ``element_ir_summary`` — compact, JSON-serialisable summary of the
          Element IR extracted from the bundle: ``element_type``, ``dim``,
          ``n_nodes``, ``n_quadrature_points``, ``formulation``.  Callable
          objects (basis functions) are excluded so the summary round-trips
          through JSON cleanly.
        - ``emitted_source`` — the Taichi source string produced by the
          compiler (``ArtifactBundle.emitted_source``).
        - ``content_hash`` — deterministic sha-256 hex digest over the
          semantic IR content (problem IR dict + element IR summary +
          contraction plans), computed via
          :meth:`~mechdsl.codegen.artifact.ArtifactBundle.content_hash`.
          Identical inputs always produce the same hash; cosmetic whitespace
          changes in the emitted source do not affect it.
        - ``derived_energy_present`` — ``True`` when the bundle carries a
          LaTeX-derived energy (i.e. ``energy_source`` / ``energy_file`` was
          supplied and parsed successfully); ``False`` for named-model runs.

    Raises
    ------
    ValueError
        When ``profile`` is unsupported, or both ``energy_source`` and
        ``energy_file`` are provided, or ``problem_source`` is ``None``.
    mechdsl.frontend.parser.ParseError
        When the LaTeX source has a malformed ``% mechanics`` directive.
    mechdsl.symbolic.convected.UnsupportedError
        When the parsed context falls outside the MVP-supported subset.
    """
    if problem_source is None:
        raise ValueError(
            "compile_from_sources requires problem_source; "
            "supply a LaTeX string with % mechanics directives."
        )

    # Lazy import — mechdsl.__init__ is already in sys.modules when this
    # subpackage is reachable; the import does NOT call ti.init.
    from mechdsl import compile_latex

    bundle = compile_latex(
        problem_source,
        profile,
        energy_source=energy_source,
        energy_file=energy_file,
    )

    # Distil the element IR summary to JSON-serialisable primitives only.
    # The full bundle.element_ir_summary may contain nested dicts with
    # non-primitive values (geometry/material_eval/local_force/local_tangent
    # descriptors); we extract only the five stable scalar fields that form
    # the Tier-1 contract surface for downstream adapters.
    raw_summary = bundle.element_ir_summary
    element_ir_summary: dict = {
        "element_type": raw_summary.get("element_type"),
        "dim": raw_summary.get("dim"),
        "n_nodes": raw_summary.get("n_nodes"),
        "n_quadrature_points": raw_summary.get("n_quadrature_points"),
        "formulation": raw_summary.get("formulation"),
    }

    return {
        "element_ir_summary": element_ir_summary,
        "emitted_source": bundle.emitted_source,
        "content_hash": bundle.content_hash(),
        "derived_energy_present": bundle.derived_energy is not None,
    }


# ---------------------------------------------------------------------------
# transpile_algorithm()
# ---------------------------------------------------------------------------


def transpile_algorithm(algpseudocode: str, backend: str = "taichi") -> dict:
    """Transpile an algpseudocode LaTeX source to a backend and return metadata.

    Wraps :func:`algo2code.transpile` behind a stable façade that returns a
    JSON-serialisable metadata dict rather than a bare source string.
    **Taichi-free:** calling this function does not trigger ``ti.init``;
    ``algo2code`` has zero runtime dependencies beyond the stdlib, and the
    transpile step produces a *source string* — it never *executes* it.

    Parameters
    ----------
    algpseudocode:
        LaTeX source containing an ``\\begin{algorithmic} … \\end{algorithmic}``
        block (the same format accepted by :func:`algo2code.transpile`).
    backend:
        Code-generation backend.  Only ``"taichi"`` is supported in the MVP.

    Returns
    -------
    dict
        ``{code, entry_point, line_count, valid_python}``

        - ``code`` — the transpiled Python source string.
        - ``entry_point`` — the generated function name (derived from the
          algorithm name parsed out of the LaTeX source via
          :func:`algo2code.parse_algorithm`).
        - ``line_count`` — number of lines in ``code``
          (``len(code.splitlines())``).
        - ``valid_python`` — ``True`` when ``compile(code, "<transpiled>",
          "exec")`` succeeds; ``False`` when compilation raises
          ``SyntaxError``, ``ValueError``, or ``TypeError`` (e.g. a
          ``ValueError`` from null bytes in the source).  The compiled code
          object is discarded — the source string is never executed here.

    Raises
    ------
    ValueError
        When ``backend`` is unsupported (propagated from
        :func:`algo2code.transpile`).
    algo2code.algo_parser.ParseError
        When the LaTeX source is syntactically invalid
        (propagated from :func:`algo2code.parse_algorithm`).
    """
    # Lazy imports — algo2code has no third-party deps (stdlib only) so these
    # are safe; keeping them lazy is consistent with the rest of this module.
    from algo2code import parse_algorithm, transpile

    # Derive the entry_point from the parsed algorithm name.  parse_algorithm
    # is called by transpile() internally anyway, so this costs no extra parse
    # round-trip in terms of correctness — we call it once ourselves here to
    # extract the name, then call transpile() which calls it again internally.
    # The cost is negligible (pure Python, no IO).
    algo = parse_algorithm(algpseudocode)
    entry_point: str = algo.name

    code: str = transpile(algpseudocode, backend=backend)

    line_count: int = len(code.splitlines())

    try:
        compile(code, "<transpiled>", "exec")
        valid_python = True
    except (SyntaxError, ValueError, TypeError):
        valid_python = False

    return {
        "code": code,
        "entry_point": entry_point,
        "line_count": line_count,
        "valid_python": valid_python,
    }


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------

#: Supported kind strings for :func:`verify`.
_VERIFY_KINDS: tuple[str, ...] = (
    "patch_test",
    "rigid_body",
    "ad_oracle_svk",
    "ad_oracle_j2",
    "benchmark",
)


def verify(kind: str, params: dict) -> dict:
    """Run a verification harness and return a normalised result dict.

    This is the **only** entry point in this module that is permitted to pay
    the Taichi cost (or any other heavy runtime cost).  All imports of the
    verify subpackage are **lazy** — they happen inside this function body so
    that merely importing :mod:`mechdsl.integration` (and calling
    :func:`capabilities`, :func:`model_catalog`, :func:`compile_from_sources`,
    or :func:`transpile_algorithm`) never triggers ``ti.init``.

    Parameters
    ----------
    kind:
        Which verification harness to run.  Supported values:

        ``"patch_test"``
            Constant-strain patch test on a structured Hex8 mesh.  Uses
            :func:`mechdsl.verify.patch_test.run_patch_test` with the SVK
            model (numpy reference solver — Taichi-free at runtime, but
            architecturally allowed to pay the Taichi cost in future).

            *params keys*:

            - ``"lam"`` (float, default 1.0) — first Lamé parameter.
            - ``"mu"`` (float, default 1.0) — shear modulus.
            - ``"nx"`` (int, default 2) — mesh divisions in x.
            - ``"ny"`` (int, default 2) — mesh divisions in y.
            - ``"nz"`` (int, default 2) — mesh divisions in z.
            - ``"Lx"`` (float, default 1.0) — domain length in x.
            - ``"Ly"`` (float, default 1.0) — domain length in y.
            - ``"Lz"`` (float, default 1.0) — domain length in z.
            - ``"strain"`` (list[list[float]], optional) — 3×3 constant
              Green-Lagrange strain.  Defaults to a mild uniaxial strain
              ``diag(1e-4, 0, 0)``.
            - ``"tol"`` (float, default 1e-12) — pass/fail tolerance.

        ``"rigid_body"``
            Rigid-body motion test on a structured Hex8 mesh.  Uses
            :func:`mechdsl.verify.patch_test.run_rigid_body_test`.

            *params keys*: same mesh/material keys as ``"patch_test"``
            plus ``"angle"`` (float, default 0.1, radians — rotation
            angle for the elementary rotation-about-z rigid body motion).

        ``"ad_oracle_svk"``
            Finite-difference AD oracle for the SVK constitutive model.
            Uses :func:`mechdsl.verify.ad_oracle.verify_svk`.

            *params keys*:

            - ``"lam"`` / ``"mu"`` **or** ``"E"`` / ``"nu"`` (floats).
            - ``"n_samples"`` (int, default 100).
            - ``"seed"`` (int, default 42).

        ``"ad_oracle_j2"``
            Finite-difference AD oracle for the J2 elastic branch.
            Uses :func:`mechdsl.verify.ad_oracle.verify_j2_elastic_branch`.

            *params keys*:

            - ``"E"``, ``"nu"``, ``"sigma_y0"``, ``"K"``, ``"n"`` (floats).
            - ``"n_samples"`` (int, default 100).
            - ``"seed"`` (int, default 42).

        ``"benchmark"``
            Run a named physical benchmark from
            :mod:`mechdsl.verify.benchmarks` and return a normalised result
            dict.  This is the only Taichi-paying ``verify`` kind that also
            drives a full solve.

            *params keys*:

            - ``"name"`` (str, required) — which benchmark to run.  Supported
              values: ``"cantilever"``, ``"cook_membrane"``.  Anything else
              raises ``ValueError``.

            ``passed`` requires convergence (``relative_error <= tolerance``)
            when the benchmark checked against a reference, and falls back to
            "ran to completion" only when no reference is available (the
            default cook_membrane smoke cell).

            *Result ``details`` keys*: ``benchmark`` (name), ``newton_iters``
            (int), ``wallclock_s`` (float), ``n_nodes`` (int),
            ``relative_error`` (float | None), ``tolerance`` (float),
            ``reference_checked`` (bool), ``extras_keys`` (list[str]).

    params:
        Keyword arguments forwarded to the underlying harness (see above).
        Unknown keys are silently ignored so callers can pass a superset.

    Returns
    -------
    dict
        ``{kind, passed, details}``

        - ``kind`` — echoes the ``kind`` argument.
        - ``passed`` — ``True`` when the harness reports success.
        - ``details`` — harness-specific diagnostics dict (JSON-friendly
          where practical; numpy scalars are cast to ``float``).

    Raises
    ------
    ValueError
        When ``kind`` is not one of the supported values.
    """
    if kind not in _VERIFY_KINDS:
        supported = ", ".join(f'"{k}"' for k in _VERIFY_KINDS)
        raise ValueError(
            f"verify() received unsupported kind={kind!r}. Supported kinds: {supported}."
        )

    if kind == "patch_test":
        return _verify_patch_test(params)
    if kind == "rigid_body":
        return _verify_rigid_body(params)
    if kind == "ad_oracle_svk":
        return _verify_ad_oracle_svk(params)
    if kind == "ad_oracle_j2":
        return _verify_ad_oracle_j2(params)
    if kind == "benchmark":
        return _verify_benchmark(params)

    # Unreachable — guard exhausts _VERIFY_KINDS
    raise AssertionError(f"Unhandled kind {kind!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# verify() — per-kind implementation helpers (all imports are lazy)
# ---------------------------------------------------------------------------


def _build_hex8_mesh(params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Build a small structured Hex8 mesh from params.

    Returns (coords, conn) numpy arrays.  All imports are lazy so this
    helper (and its callers) do not trigger Taichi on import.
    """
    from mechdsl.solver.mesh_io import generate_hex8_mesh

    nx = int(params.get("nx", 2))
    ny = int(params.get("ny", 2))
    nz = int(params.get("nz", 2))
    Lx = float(params.get("Lx", 1.0))
    Ly = float(params.get("Ly", 1.0))
    Lz = float(params.get("Lz", 1.0))
    mesh = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
    return mesh.coords, mesh.connectivity


def _verify_patch_test(params: dict) -> dict:
    """Run the constant-strain patch test and normalise the result."""
    import numpy as np

    from mechdsl.verify.patch_test import PatchTestResult, run_patch_test

    coords, conn = _build_hex8_mesh(params)

    lam = float(params.get("lam", 1.0))
    mu = float(params.get("mu", 1.0))
    tol = float(params.get("tol", 1e-12))

    # Strain: accept a 3×3 nested list/array from params, or use a mild
    # uniaxial default that is well within the linear regime.
    if "strain" in params:
        strain = np.asarray(params["strain"], dtype=np.float64)
        if strain.shape != (3, 3):
            raise ValueError(f"params['strain'] must be shape (3, 3); got {strain.shape}")
    else:
        eps = 1e-4
        strain = np.diag([eps, 0.0, 0.0]).astype(np.float64)

    result: PatchTestResult = run_patch_test(coords, conn, lam, mu, strain, tol=tol)

    return {
        "kind": "patch_test",
        "passed": bool(result.passed),
        "details": {
            "error": float(result.error),
            "tol": float(result.tol),
            "interior_force_max": float(result.interior_force_max),
            "boundary_force_sum": float(result.boundary_force_sum),
            "n_nodes": int(result.n_nodes),
            "n_elements": int(result.n_elements),
        },
    }


def _verify_rigid_body(params: dict) -> dict:
    """Run the rigid-body motion test and normalise the result."""
    import numpy as np

    from mechdsl.verify.patch_test import RigidBodyResult, run_rigid_body_test

    coords, conn = _build_hex8_mesh(params)

    lam = float(params.get("lam", 1.0))
    mu = float(params.get("mu", 1.0))
    tol = float(params.get("tol", 1e-12))
    angle = float(params.get("angle", 0.1))  # radians, rotation about z

    # Elementary rotation about z-axis
    c, s = float(np.cos(angle)), float(np.sin(angle))
    rotation = np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    translation = np.zeros(3, dtype=np.float64)

    result: RigidBodyResult = run_rigid_body_test(
        coords, conn, lam, mu, rotation, translation, tol=tol
    )

    return {
        "kind": "rigid_body",
        "passed": bool(result.passed),
        "details": {
            "force_norm": float(result.force_norm),
            "tol": float(result.tol),
            "n_nodes": int(result.n_nodes),
            "n_elements": int(result.n_elements),
        },
    }


def _verify_ad_oracle_svk(params: dict) -> dict:
    """Run the SVK AD oracle and normalise the result."""
    from mechdsl.verify.ad_oracle import verify_svk

    # Accept partial overrides: if the caller supplies *either* Lamé parameter,
    # fill the missing one from its unit default rather than silently dropping
    # the whole override and reverting to (lam=1, mu=1).  An (E, nu) pair takes
    # precedence only when no Lamé key is present (mirrors _verify_ad_oracle_j2).
    mat_params: dict = {}
    if "lam" in params or "mu" in params:
        mat_params = {
            "lam": float(params.get("lam", 1.0)),
            "mu": float(params.get("mu", 1.0)),
        }
    elif "E" in params or "nu" in params:
        mat_params = {
            "E": float(params.get("E", 2.5)),
            "nu": float(params.get("nu", 0.25)),
        }
    else:
        mat_params = {"lam": 1.0, "mu": 1.0}

    n_samples = int(params.get("n_samples", 100))
    seed = int(params.get("seed", 42))

    result: dict = verify_svk(mat_params, n_samples=n_samples, seed=seed)

    return {
        "kind": "ad_oracle_svk",
        "passed": bool(result["all_passed"]),
        "details": {
            "max_stress_error": float(result["max_stress_error"]),
            "max_tangent_error": float(result["max_tangent_error"]),
            "n_samples": n_samples,
        },
    }


def _verify_ad_oracle_j2(params: dict) -> dict:
    """Run the J2 elastic-branch AD oracle and normalise the result."""
    from mechdsl.verify.ad_oracle import verify_j2_elastic_branch

    mat_params = {
        "E": float(params.get("E", 200_000.0)),
        "nu": float(params.get("nu", 0.3)),
        "sigma_y0": float(params.get("sigma_y0", 250.0)),
        "K": float(params.get("K", 1000.0)),
        "n": float(params.get("n", 0.5)),
    }
    n_samples = int(params.get("n_samples", 100))
    seed = int(params.get("seed", 42))

    result: dict = verify_j2_elastic_branch(mat_params, n_samples=n_samples, seed=seed)

    return {
        "kind": "ad_oracle_j2",
        "passed": bool(result["all_passed"]),
        "details": {
            "max_stress_error": float(result["max_stress_error"]),
            "n_samples": n_samples,
        },
    }


#: Named benchmarks supported by :func:`_verify_benchmark`.
_BENCHMARK_NAMES: tuple[str, ...] = ("cantilever", "cook_membrane")


def _verify_benchmark(params: dict) -> dict:
    """Run a named benchmark from mechdsl.verify.benchmarks and normalise the result.

    All imports are lazy (inside this function) so the module-level
    Taichi-free guarantee is preserved.

    Supported ``params["name"]`` values: ``"cantilever"``, ``"cook_membrane"``.
    An unknown or missing name raises ``ValueError`` before any Taichi cost.

    ``passed`` semantics depend on whether the benchmark compared against a
    reference solution (signalled by a finite ``relative_error`` in its
    ``extras``):

    - **Reference available** (cantilever vs Euler-Bernoulli; cook_membrane
      Hex8 reference path): ``passed`` requires the solve to finish AND
      ``relative_error <= tolerance``, where ``tolerance`` is the benchmark's
      own ``tip_tolerance`` if published, else 2% (the benchmark convergence
      bar from ``.claude/rules/tests.md``).
    - **No reference** (the default cook_membrane prescribed-displacement smoke
      cell reports ``relative_error = NaN``): ``passed`` falls back to "ran to
      completion with a non-None displacement field and non-negative
      ``newton_iters``".  ``details["reference_checked"]`` is ``False`` so the
      caller can tell convergence from a completion-only smoke pass.

    Returns
    -------
    dict
        ``{kind:"benchmark", passed:bool, details:{benchmark, newton_iters,
        wallclock_s, n_nodes, relative_error, tolerance, reference_checked,
        extras_keys}}``.  ``relative_error`` is ``None`` when no reference was
        checked.
    """
    name = params.get("name")
    if name not in _BENCHMARK_NAMES:
        raise ValueError(
            f"verify('benchmark', ...) requires params['name'] to be one of "
            f"{list(_BENCHMARK_NAMES)!r}; got {name!r}."
        )

    if name == "cantilever":
        from mechdsl.verify.benchmarks import run_cantilever_benchmark
        from mechdsl.verify.benchmarks.cantilever import CantileverParameters

        result = run_cantilever_benchmark(params=CantileverParameters())

    elif name == "cook_membrane":
        from mechdsl.verify.benchmarks import run_cook_membrane_benchmark
        from mechdsl.verify.benchmarks.cook_membrane import CookMembraneParameters

        result = run_cook_membrane_benchmark(params=CookMembraneParameters())

    else:  # pragma: no cover
        raise AssertionError(f"Unhandled benchmark name {name!r}")

    extras = result.extras
    ran_to_completion = result.displacements is not None and result.newton_iters >= 0

    # A finite ``relative_error`` means the benchmark compared its result
    # against a reference solution (cantilever vs Euler-Bernoulli beam theory;
    # the cook_membrane Hex8 reference path).  The default cook_membrane call
    # takes a prescribed-displacement smoke cell that reports NaN — there is no
    # reference to converge to on that path, so completion is all we can check.
    # Coerce via float() rather than isinstance(.., int | float): the latter
    # would (a) accept bools (bool subclasses int) and (b) reject numpy scalars
    # (np.float64 doesn't subclass Python float on numpy 1.x).  _coerce_finite
    # excludes bools and round-trips numpy scalars through float().
    rel_error = _coerce_finite(extras.get("relative_error"))
    reference_checked = rel_error is not None

    # Tolerance: prefer the benchmark's own published bar, else default
    # to 2% relative error.
    tol_raw = _coerce_finite(extras.get("tip_tolerance", extras.get("rel_error_tol")))
    tolerance = tol_raw if tol_raw is not None else 0.02

    if rel_error is not None:
        # Real reference available → require convergence within tolerance,
        # not merely that the solve finished.
        passed = ran_to_completion and rel_error <= tolerance
    else:
        # No reference on this path → completion smoke is the contract.
        passed = ran_to_completion

    return {
        "kind": "benchmark",
        "passed": passed,
        "details": {
            "benchmark": name,
            "newton_iters": int(result.newton_iters),
            "wallclock_s": float(result.wallclock_s),
            # displacements is None on a non-converged / failed solve; report 0
            # rather than crashing the harness with AttributeError.
            "n_nodes": (
                int(result.displacements.shape[0]) if result.displacements is not None else 0
            ),
            "relative_error": rel_error,
            "tolerance": tolerance,
            "reference_checked": reference_checked,
            "extras_keys": list(result.extras.keys()),
        },
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_finite(value: object) -> float | None:
    """Coerce a benchmark ``extras`` scalar to a finite ``float``, else ``None``.

    Robust to two traps that ``isinstance(value, int | float)`` falls into:

    - **bools** — ``bool`` subclasses ``int``, so ``isinstance(True, int)`` is
      ``True``; a stray boolean must not masquerade as a numeric error/tolerance.
    - **numpy scalars** — ``np.float64`` does not subclass Python ``float`` on
      numpy 1.x, so an ``isinstance`` check would wrongly reject a real value.

    Returns ``None`` for ``None``, bools, non-numeric values, and non-finite
    floats (``NaN`` / ``±inf``).
    """
    import math

    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mechdsl_version() -> str:
    """Return mechdsl-core version, preferring importlib.metadata."""
    try:
        from importlib.metadata import version

        return version("mechdsl-core")
    except Exception:
        # Fallback: read from mechdsl.__version__ which is set in __init__.py
        from mechdsl import __version__

        return __version__


def _model_name_from_class(cls_name: str) -> str:
    """Convert a CamelCase Model class name to a snake_case catalog name.

    Examples::

        SVKModel           -> svk
        J2Model            -> j2
        NeoHookeanModel    -> neo_hookean
        MooneyRivlinModel  -> mooney_rivlin
        OgdenModel         -> ogden
        HGOModel           -> hgo
        PerzynaModel       -> perzyna
        JohnsonCookModel   -> johnson_cook
    """
    # Strip trailing "Model"
    if cls_name.endswith("Model"):
        cls_name = cls_name[: -len("Model")]
    # Convert CamelCase to snake_case
    import re

    # Insert underscore before sequences: upper-lower boundary
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", cls_name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower()


def _introspect_model_class(model_cls: type, material_cls: type) -> tuple[tuple[str, ...], bool]:
    """Read ``state_variables`` and ``is_dissipative`` from a ConstitutiveModel subclass.

    We instantiate a minimal dummy instance (params filled with plausible
    float defaults) and read the abstract properties.  This is safe because:

    - All current model properties are pure Python (no Taichi).
    - The properties are read-only and do not depend on numerical param values.

    Returns
    -------
    tuple[tuple[str, ...], bool]
        ``(state_variables, is_dissipative)``
    """
    import dataclasses

    # Build keyword args for the Material dataclass with sensible defaults.
    dummy_kwargs: dict = {}
    for field in dataclasses.fields(material_cls):
        # Use field default if available, else pick a plausible positive float.
        if field.default is not dataclasses.MISSING:
            dummy_kwargs[field.name] = field.default
        elif field.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            dummy_kwargs[field.name] = field.default_factory()  # type: ignore[misc]
        else:
            dummy_kwargs[field.name] = _default_for_field(field.name)

    try:
        mat = material_cls(**dummy_kwargs)
        # Some models close over extra constructor data beyond the Material
        # (e.g. HGOModel takes per-element fiber directions). Fill any extra
        # required positional/keyword parameters with safe dummies so the
        # introspection-only properties below can be read.
        instance = model_cls(mat, **_dummy_model_ctor_args(model_cls))
    except Exception as exc:
        # Swallowing this would make model_catalog() silently emit a WRONG
        # entry (empty state_variables, dissipative=False) for a real model.
        # For a machine-readable contract that downstream adapters key off,
        # silent corruption is worse than a loud failure — so surface it with
        # an actionable message instead of falling back to ((), False).
        raise RuntimeError(
            f"model_catalog could not introspect {model_cls.__name__}: "
            f"instantiating it with dummy params failed ({exc!r}). Add or fix "
            f"a _default_for_field / _default_for_model_arg entry for the "
            f"offending parameter."
        ) from exc
    return instance.state_variables, instance.is_dissipative


def _default_for_field(field_name: str) -> object:
    """Return a safe positive-float default for a material parameter field.

    These values are only used to instantiate throwaway dummy instances for
    property introspection — they are never used in computation.
    """
    # Fields where negative / special values cause __post_init__ to raise
    _SPECIAL: dict[str, object] = {
        # Poisson's ratio: must be in (-1, 0.5) — 1.0 is invalid
        "nu": 0.3,
        # OgdenMaterial uses tuple fields
        "mus": (1.0,),
        "alphas": (2.0,),
        # JohnsonCookMaterial: T_melt must be > T_ref
        "T_melt": 1800.0,
        "T_ref": 293.0,
        # HGOMaterial: fiber_dispersion must be in [0, 1/3]
        "fiber_dispersion": 0.0,
        # Perzyna: eta > 0
        "eta": 1.0,
        # Rate exponents
        "m": 1.0,
        "n": 1.0,
        "s_d": 1.0,
        # Damage threshold
        "eps_D": 0.0,
        # Misc positive floats
        "rho_c_p": 1.0,
        "eps_dot_0": 1.0,
        "beta": 0.9,
    }
    return _SPECIAL.get(field_name, 1.0)


def _dummy_model_ctor_args(model_cls: type) -> dict:
    """Return dummy kwargs for a model constructor's extra (non-material) params.

    Most ``ConstitutiveModel`` subclasses take only the Material as a
    constructor argument.  A few close over additional per-element data —
    e.g. ``HGOModel(mat, fiber_dirs)``.  We inspect the constructor signature,
    skip ``self`` and the first (material) parameter, and supply a safe dummy
    for every remaining *required* parameter via :func:`_default_for_model_arg`.

    Parameters with defaults, ``*args``, and ``**kwargs`` are left untouched.
    """
    import inspect

    # Inspecting the class (not __init__) yields the constructor signature with
    # ``self`` already removed; drop the first real parameter (the Material).
    sig = inspect.signature(model_cls)
    params = list(sig.parameters.values())[1:]

    extras: dict = {}
    for p in params:
        if p.default is not inspect.Parameter.empty:
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        extras[p.name] = _default_for_model_arg(p.name)
    return extras


def _default_for_model_arg(name: str) -> object:
    """Return a safe dummy for an extra (non-material) model constructor arg.

    Only used to build throw-away instances for property introspection.
    Raises loudly for an unknown required parameter so a future model that
    needs new constructor data is never silently mis-catalogued.
    """
    import numpy as np

    if name == "fiber_dirs":
        # Two orthonormal in-plane directions; HGOModel unit-normalises them.
        return (
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
        )

    raise RuntimeError(
        f"model_catalog: no dummy value registered for required model "
        f"constructor parameter {name!r}; add one to _default_for_model_arg."
    )
