"""Canonical integration-surface contract tests for mechdsl.integration (Tier-1 façade).

This file is the holistic contract test for the entire ``mechdsl.integration``
module surface.  It is NOT a duplicate of the per-function task tests in
``tests/plan_tests/akms_executable_bridge/test_P1-1..4.py`` — those pin
acceptance criteria for individual tasks.  This file asserts the COMBINED
invariants that hold across the whole façade:

1. ``capabilities()`` shape, with the critical ``taichi_required_for``
   and ``actions`` / ``backends`` fields exactly as documented.
2. ``model_catalog()`` field-set per entry and MVP-model presence.
3. The **module-level Taichi-free invariant** across all four non-verify entry
   points — asserted via a fresh-interpreter subprocess so no parent-process
   Taichi import contaminates the check.  This is the load-bearing guard.
4. ``compile_from_sources()`` on a known-good SVK energy source returns all
   four documented keys.
5. ``transpile_algorithm()`` on ``RADIAL_RETURN_J2_LATEX`` returns
   ``valid_python=True``.
6. ``verify("patch_test", ...)`` runs and returns a pass/fail result dict.
7. ``"integration"`` is in ``mechdsl.__all__``.

Marks:
  - ``@pytest.mark.integration`` — all tests in this file.
  - ``@pytest.mark.slow`` — the verify (Taichi-paying) test only.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Shared LaTeX fixtures (duplicated here to keep this file fully
# self-contained — it is the canonical surface test).
# ---------------------------------------------------------------------------

_PROBLEM_SOURCE_SVK_NAMED = """\
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""

# SVK energy: \lambda sanitises to ``aleph``; companion problem must use those names.
_SVK_ENERGY_SOURCE = """\
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \\lambda \\mu --const
\\Psi = \\frac{\\lambda}{2} E^{I}_{I} E^{J}_{J} + \\mu E^{I J} E_{I J}
"""

# E=200e3, nu=0.3  =>  lam ≈ 115384.6, mu ≈ 76923.1
_PROBLEM_SOURCE_WITH_ENERGY = """\
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --aleph 115384.6 --mu 76923.1
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""


# ---------------------------------------------------------------------------
# 1. capabilities() shape
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCapabilitiesShape:
    """Holistic shape and contract checks for capabilities()."""

    def test_all_keys_present(self):
        """capabilities() returns exactly the seven documented keys."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        expected = {
            "version",
            "python",
            "profiles",
            "backends",
            "actions",
            "taichi_required_for",
            "models",
        }
        assert set(caps.keys()) == expected, (
            f"capabilities() key set mismatch.\n"
            f"Missing: {expected - set(caps.keys())!r}\n"
            f"Extra: {set(caps.keys()) - expected!r}"
        )

    def test_taichi_required_for_is_verify_only(self):
        """taichi_required_for must be exactly ['verify'] — this is the Tier-1 contract."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert caps["taichi_required_for"] == ["verify"], (
            f"taichi_required_for must be ['verify']; got {caps['taichi_required_for']!r}"
        )

    def test_actions_set(self):
        """actions must contain exactly {'emit', 'transpile', 'verify'}."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert set(caps["actions"]) == {"emit", "transpile", "verify"}, (
            f"actions mismatch: got {caps['actions']!r}"
        )

    def test_backends_is_taichi_only(self):
        """backends must be ['taichi'] for the MVP-stable contract."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert caps["backends"] == ["taichi"], (
            f"backends must be ['taichi'] for MVP; got {caps['backends']!r}"
        )

    def test_version_is_string(self):
        """version must be a non-empty string."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert isinstance(caps["version"], str) and caps["version"], (
            "version must be a non-empty string"
        )

    def test_profiles_contains_mvp(self):
        """profiles must include 'mvp'."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert "mvp" in caps["profiles"], "profiles must include 'mvp'"

    def test_models_list_non_empty_strings(self):
        """models must be a non-empty list of strings."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert isinstance(caps["models"], list) and caps["models"], "models must be non-empty list"
        assert all(isinstance(m, str) for m in caps["models"]), "each model must be a string"

    def test_mvp_models_in_capabilities(self):
        """SVK and J2 appear in capabilities().models."""
        from mechdsl.integration import capabilities

        caps = capabilities()
        models = caps["models"]
        assert "svk" in models, "capabilities.models must include 'svk'"
        # j2 (symbolic) or j2_isotropic (lib/plasticity) — either is fine
        assert any(m.startswith("j2") for m in models), (
            "capabilities.models must include a J2 variant"
        )


# ---------------------------------------------------------------------------
# 2. model_catalog() field-set and MVP models
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestModelCatalog:
    """Holistic field-set and content checks for model_catalog()."""

    _REQUIRED_ENTRY_KEYS: frozenset[str] = frozenset(
        {"name", "module", "tier", "dissipative", "params", "state_variables"}
    )

    def test_returns_non_empty_list(self):
        """model_catalog() returns a non-empty list."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()
        assert isinstance(catalog, list) and catalog, "model_catalog() must return a non-empty list"

    def test_every_entry_has_full_field_set(self):
        """Every catalog entry has exactly the six documented fields."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()
        for entry in catalog:
            assert set(entry.keys()) == self._REQUIRED_ENTRY_KEYS, (
                f"Entry {entry.get('name')!r} has wrong keys.\n"
                f"Missing: {self._REQUIRED_ENTRY_KEYS - set(entry.keys())!r}\n"
                f"Extra: {set(entry.keys()) - self._REQUIRED_ENTRY_KEYS!r}"
            )
            assert isinstance(entry["name"], str) and entry["name"]
            assert isinstance(entry["module"], str) and "." in entry["module"]
            assert entry["tier"] in ("mvp", "experimental")
            assert isinstance(entry["dissipative"], bool)
            assert isinstance(entry["params"], list)
            assert isinstance(entry["state_variables"], list)

    def test_mvp_models_present_and_correctly_tagged(self):
        """SVK and J2 power-law (symbolic) are present and tagged 'mvp'."""
        from mechdsl.integration import model_catalog

        by_name = {e["name"]: e for e in model_catalog()}

        assert "svk" in by_name, "svk must be in model_catalog()"
        assert by_name["svk"]["tier"] == "mvp"
        assert by_name["svk"]["dissipative"] is False

        assert "j2" in by_name, "j2 (symbolic) must be in model_catalog()"
        assert by_name["j2"]["tier"] == "mvp"
        assert by_name["j2"]["dissipative"] is True

        assert "j2_isotropic" in by_name, "j2_isotropic must be in model_catalog()"
        assert by_name["j2_isotropic"]["tier"] == "mvp"

    def test_catalog_models_match_capabilities(self):
        """capabilities().models is exactly [e['name'] for e in model_catalog()]."""
        from mechdsl.integration import capabilities, model_catalog

        catalog = model_catalog()
        caps = capabilities()
        expected_names = [e["name"] for e in catalog]
        assert caps["models"] == expected_names, (
            f"capabilities.models does not match catalog names.\n"
            f"capabilities.models: {caps['models']!r}\n"
            f"catalog names:       {expected_names!r}"
        )


# ---------------------------------------------------------------------------
# 3. Module-level Taichi-free invariant (the load-bearing guard)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTaichiFreeInvariant:
    """Subprocess-based guard: all four non-verify entry points must stay Taichi-free.

    A fresh interpreter is used on every test so no parent-process import of
    Taichi can contaminate the result.  This is the canonical form of the guard
    described in the Phase-1 context summary as the 'load-bearing invariant'.
    """

    def _run_subprocess_script(
        self, script: str, timeout: int = 120
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_taichi_free_capabilities_and_model_catalog(self):
        """capabilities() + model_catalog() in a fresh interpreter: taichi not in sys.modules."""
        script = (
            "import sys; "
            "from mechdsl.integration import capabilities, model_catalog; "
            "capabilities(); "
            "model_catalog(); "
            "loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', loaded); "
            "sys.exit(1 if loaded else 0)"
        )
        r = self._run_subprocess_script(script)
        assert r.returncode == 0, (
            "capabilities()/model_catalog() triggered Taichi load.\n"
            f"stdout: {r.stdout!r}\nstderr: {r.stderr!r}"
        )
        assert "taichi_loaded: False" in r.stdout

    def test_taichi_free_compile_from_sources(self):
        """compile_from_sources() in a fresh interpreter: taichi not in sys.modules."""
        problem_arg = (
            "'% mechanics dim 3\\n"
            "% mechanics cell hex8\\n"
            "% mechanics formulation total_lagrangian\\n"
            "% mechanics material svk --E 200e3 --nu 0.3\\n"
            "% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2\\n"
            '% mechanics boundary load --type neumann --traction "t_bar"\\n\''
        )
        script = (
            "import sys; "
            "from mechdsl.integration import compile_from_sources; "
            f"compile_from_sources(problem_source={problem_arg}); "
            "loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', loaded); "
            "sys.exit(1 if loaded else 0)"
        )
        r = self._run_subprocess_script(script)
        assert r.returncode == 0, (
            "compile_from_sources() triggered Taichi load.\n"
            f"stdout: {r.stdout!r}\nstderr: {r.stderr!r}"
        )
        assert "taichi_loaded: False" in r.stdout

    def test_taichi_free_transpile_algorithm(self):
        """transpile_algorithm() in a fresh interpreter: taichi not in sys.modules."""
        script = (
            "import sys; "
            "from mechdsl.integration import transpile_algorithm; "
            "from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX; "
            "result = transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend='taichi'); "
            "assert result['entry_point'] == 'radial_return_j2'; "
            "loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', loaded); "
            "sys.exit(1 if loaded else 0)"
        )
        r = self._run_subprocess_script(script, timeout=60)
        assert r.returncode == 0, (
            "transpile_algorithm() triggered Taichi load.\n"
            f"stdout: {r.stdout!r}\nstderr: {r.stderr!r}"
        )
        assert "taichi_loaded: False" in r.stdout

    def test_taichi_free_all_four_in_one_process(self):
        """All four non-verify entry points together in a single fresh interpreter."""
        problem_arg = (
            "'% mechanics dim 3\\n"
            "% mechanics cell hex8\\n"
            "% mechanics formulation total_lagrangian\\n"
            "% mechanics material svk --E 200e3 --nu 0.3\\n"
            "% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2\\n"
            '% mechanics boundary load --type neumann --traction "t_bar"\\n\''
        )
        script = (
            "import sys; "
            "from mechdsl.integration import ("
            "    capabilities, model_catalog, compile_from_sources, transpile_algorithm"
            "); "
            "from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX; "
            "capabilities(); "
            "model_catalog(); "
            f"compile_from_sources(problem_source={problem_arg}); "
            "transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend='taichi'); "
            "loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', loaded); "
            "sys.exit(1 if loaded else 0)"
        )
        r = self._run_subprocess_script(script)
        assert r.returncode == 0, (
            "One or more of the four Taichi-free entry points triggered a Taichi load.\n"
            f"stdout: {r.stdout!r}\nstderr: {r.stderr!r}"
        )
        assert "taichi_loaded: False" in r.stdout


# ---------------------------------------------------------------------------
# 4. compile_from_sources() — known-good SVK energy, four documented keys
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCompileFromSources:
    """compile_from_sources() façade contract — holistic key + type assertions."""

    def test_returns_four_keys_with_energy(self):
        """compile_from_sources() with SVK energy returns the four documented keys."""
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(
            problem_source=_PROBLEM_SOURCE_WITH_ENERGY,
            energy_source=_SVK_ENERGY_SOURCE,
        )
        expected_keys = {
            "element_ir_summary",
            "emitted_source",
            "content_hash",
            "derived_energy_present",
        }
        assert set(result.keys()) == expected_keys, (
            f"compile_from_sources() keys mismatch.\n"
            f"Missing: {expected_keys - set(result.keys())!r}\n"
            f"Extra: {set(result.keys()) - expected_keys!r}"
        )

    def test_element_ir_summary_fields(self):
        """element_ir_summary contains the five stable scalar fields."""
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(
            problem_source=_PROBLEM_SOURCE_WITH_ENERGY,
            energy_source=_SVK_ENERGY_SOURCE,
        )
        summary = result["element_ir_summary"]
        assert isinstance(summary, dict)
        required = {"element_type", "dim", "n_nodes", "n_quadrature_points", "formulation"}
        assert required <= set(summary.keys()), (
            f"element_ir_summary missing fields: {required - set(summary.keys())!r}"
        )
        assert summary["element_type"] == "hex8"
        assert summary["dim"] == 3
        assert summary["formulation"] == "total_lagrangian"

    def test_emitted_source_is_non_empty_string(self):
        """emitted_source is a non-empty string."""
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(problem_source=_PROBLEM_SOURCE_SVK_NAMED)
        assert isinstance(result["emitted_source"], str) and result["emitted_source"]

    def test_content_hash_is_sha256_hex(self):
        """content_hash is a 64-char lowercase hex string (sha-256)."""
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(problem_source=_PROBLEM_SOURCE_SVK_NAMED)
        h = result["content_hash"]
        assert isinstance(h, str) and len(h) == 64, f"content_hash must be 64-char hex; got {h!r}"
        assert all(c in "0123456789abcdef" for c in h)

    def test_derived_energy_present_true_when_energy_supplied(self):
        """derived_energy_present is True when energy_source is supplied."""
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(
            problem_source=_PROBLEM_SOURCE_WITH_ENERGY,
            energy_source=_SVK_ENERGY_SOURCE,
        )
        assert result["derived_energy_present"] is True

    def test_derived_energy_present_false_for_named_model(self):
        """derived_energy_present is False for a named-model run."""
        from mechdsl.integration import compile_from_sources

        result = compile_from_sources(problem_source=_PROBLEM_SOURCE_SVK_NAMED)
        assert result["derived_energy_present"] is False


# ---------------------------------------------------------------------------
# 5. transpile_algorithm() — RADIAL_RETURN_J2_LATEX, valid_python True
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTranspileAlgorithm:
    """transpile_algorithm() façade contract — holistic assertions."""

    def test_returns_four_keys_valid_python_true(self):
        """transpile_algorithm on RADIAL_RETURN_J2_LATEX returns four keys and valid_python=True."""
        from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
        from mechdsl.integration import transpile_algorithm

        result = transpile_algorithm(RADIAL_RETURN_J2_LATEX, backend="taichi")

        expected_keys = {"code", "entry_point", "line_count", "valid_python"}
        assert set(result.keys()) == expected_keys, (
            f"transpile_algorithm() keys mismatch.\n"
            f"Missing: {expected_keys - set(result.keys())!r}\n"
            f"Extra: {set(result.keys()) - expected_keys!r}"
        )

        assert isinstance(result["code"], str) and result["code"]
        assert result["entry_point"] == "radial_return_j2"
        assert isinstance(result["line_count"], int) and result["line_count"] > 0
        assert result["line_count"] == len(result["code"].splitlines())
        assert result["valid_python"] is True, (
            f"valid_python must be True for RADIAL_RETURN_J2_LATEX.\ncode:\n{result['code']}"
        )


# ---------------------------------------------------------------------------
# 6. verify("patch_test", ...) — Taichi-paying path
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestVerifyPatchTest:
    """verify() on the patch_test kind — minimal run, pass/fail result dict."""

    def test_patch_test_returns_result_dict(self):
        """verify('patch_test', ...) returns a dict with {kind, passed, details}."""
        from mechdsl.integration import verify

        result = verify(
            "patch_test",
            {"lam": 1.0, "mu": 1.0, "nx": 2, "ny": 2, "nz": 2, "tol": 1e-12},
        )

        assert isinstance(result, dict), f"verify() must return dict; got {type(result)!r}"
        assert "kind" in result
        assert "passed" in result
        assert "details" in result

        assert result["kind"] == "patch_test"
        assert isinstance(result["passed"], bool)
        assert isinstance(result["details"], dict)

    def test_patch_test_passes(self):
        """verify('patch_test') reports passed=True on a 2×2×2 mesh with unit Lamé params."""
        from mechdsl.integration import verify

        result = verify(
            "patch_test",
            {"lam": 1.0, "mu": 1.0, "nx": 2, "ny": 2, "nz": 2, "tol": 1e-12},
        )
        assert result["passed"], f"Patch test FAILED — details: {result['details']!r}"

    def test_patch_test_passes_with_custom_strain(self):
        """verify('patch_test') accepts an explicit strain tensor in params."""
        from mechdsl.integration import verify

        strain = [[1e-4, 0.0, 0.0], [0.0, 1e-4, 0.0], [0.0, 0.0, 1e-4]]
        result = verify("patch_test", {"lam": 1.0, "mu": 1.0, "strain": strain})
        assert result["kind"] == "patch_test"
        assert isinstance(result["passed"], bool)


# ---------------------------------------------------------------------------
# 7. mechdsl.__all__ contains "integration"
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_in_mechdsl_all():
    """'integration' is exported in mechdsl.__all__."""
    import mechdsl

    assert "integration" in mechdsl.__all__, (
        f"'integration' missing from mechdsl.__all__; got {mechdsl.__all__!r}"
    )


@pytest.mark.integration
def test_all_five_functions_importable():
    """All five façade entry points are importable from mechdsl.integration."""
    import mechdsl.integration as mod
    from mechdsl.integration import (  # noqa: F401
        capabilities,
        compile_from_sources,
        model_catalog,
        transpile_algorithm,
        verify,
    )

    for name in (
        "capabilities",
        "model_catalog",
        "compile_from_sources",
        "transpile_algorithm",
        "verify",
    ):
        assert hasattr(mod, name), f"{name!r} not found on mechdsl.integration"
        assert callable(getattr(mod, name)), f"{name!r} must be callable"
        assert name in mod.__all__, f"{name!r} must be in mechdsl.integration.__all__"


# ---------------------------------------------------------------------------
# 8. verify() unknown-kind error — fast, no Taichi
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestVerifyUnknownKind:
    """Fast (Taichi-free) tests for verify() error semantics on bad inputs.

    Separated from TestVerifyPatchTest (which is slow) because unknown-kind
    validation raises before any Taichi call and must run in the fast tier.
    """

    def test_unknown_kind_raises_value_error_with_supported_kinds(self):
        """verify() raises ValueError naming 'Supported kinds:' for an unknown kind."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError, match=r"Supported kinds:"):
            verify("unsupported_kind", {})

    def test_unknown_kind_mentions_offending_kind(self):
        """The ValueError message includes the offending kind token."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError, match="bogus_kind"):
            verify("bogus_kind", {})

    def test_benchmark_kind_is_listed_as_supported(self):
        """'benchmark' appears in the supported-kinds list on a bad-name ValueError."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError, match="benchmark") as exc_info:
            verify("benchmark", {})  # missing name → ValueError before Taichi
        # The error must come from _verify_benchmark (params['name'] missing),
        # not from the kind guard — i.e. 'benchmark' IS a supported kind.
        assert "Supported kinds" not in str(exc_info.value), (
            "'benchmark' kind must be accepted by the kind guard; "
            "ValueError should come from missing params['name'], not the kind check."
        )

    def test_benchmark_unknown_name_raises_value_error(self):
        """verify('benchmark', {'name': 'nonexistent'}) raises ValueError."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError, match="nonexistent"):
            verify("benchmark", {"name": "nonexistent"})

    def test_benchmark_missing_name_raises_value_error(self):
        """verify('benchmark', {}) — missing name key — raises ValueError."""
        from mechdsl.integration import verify

        with pytest.raises(ValueError):
            verify("benchmark", {})


# ---------------------------------------------------------------------------
# 9. verify("benchmark", ...) — Taichi-paying benchmark kind coverage
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestVerifyBenchmarkKind:
    """verify('benchmark', ...) — result shape and semantics for the benchmark kind."""

    def test_cantilever_result_shape(self):
        """verify('benchmark', {'name':'cantilever'}) returns the normalised dict."""
        from mechdsl.integration import verify

        result = verify("benchmark", {"name": "cantilever"})

        assert isinstance(result, dict), f"result must be a dict; got {type(result)!r}"
        assert result["kind"] == "benchmark", f"kind must be 'benchmark'; got {result['kind']!r}"
        assert isinstance(result["passed"], bool), (
            f"passed must be bool; got {type(result['passed'])!r}"
        )
        assert isinstance(result["details"], dict), (
            f"details must be dict; got {type(result['details'])!r}"
        )

        details = result["details"]
        assert details["benchmark"] == "cantilever"
        assert isinstance(details["newton_iters"], int)
        assert isinstance(details["wallclock_s"], float)
        assert isinstance(details["n_nodes"], int) and details["n_nodes"] > 0
        assert isinstance(details["extras_keys"], list)

    def test_cantilever_passes(self):
        """verify('benchmark', {'name':'cantilever'}) reports passed=True."""
        from mechdsl.integration import verify

        result = verify("benchmark", {"name": "cantilever"})
        assert result["passed"], f"Cantilever benchmark FAILED — details: {result['details']!r}"

    def test_cantilever_passes_by_convergence_not_just_completion(self):
        """Cantilever pass is gated on relative_error <= tolerance, not mere completion."""
        from mechdsl.integration import verify

        details = verify("benchmark", {"name": "cantilever"})["details"]
        assert details["reference_checked"] is True, (
            "cantilever compares against Euler-Bernoulli theory, so a reference "
            f"WAS checked; details: {details!r}"
        )
        assert isinstance(details["relative_error"], float)
        assert isinstance(details["tolerance"], float)
        assert details["relative_error"] <= details["tolerance"], (
            f"cantilever did not converge: relative_error={details['relative_error']} "
            f"> tolerance={details['tolerance']}"
        )

    def test_cook_membrane_smoke_has_no_reference(self):
        """The default cook_membrane call is a smoke cell — completion-only pass."""
        from mechdsl.integration import verify

        details = verify("benchmark", {"name": "cook_membrane"})["details"]
        assert details["reference_checked"] is False, (
            "the default cook_membrane call injects no reference solver, so no "
            f"convergence check is possible; details: {details!r}"
        )
        assert details["relative_error"] is None
        assert details["benchmark"] == "cook_membrane"

    def test_benchmark_details_expose_convergence_fields(self):
        """Every benchmark result carries relative_error / tolerance / reference_checked."""
        from mechdsl.integration import verify

        for name in ("cantilever", "cook_membrane"):
            details = verify("benchmark", {"name": name})["details"]
            assert "relative_error" in details, name
            assert "tolerance" in details, name
            assert "reference_checked" in details, name
            assert isinstance(details["reference_checked"], bool), name
            assert isinstance(details["tolerance"], float), name

    def test_cantilever_result_is_json_friendly(self):
        """The cantilever benchmark result round-trips through json.dumps."""
        import json

        from mechdsl.integration import verify

        result = verify("benchmark", {"name": "cantilever"})
        serialised = json.dumps(result)
        recovered = json.loads(serialised)
        assert recovered["kind"] == "benchmark"
        assert recovered["details"]["benchmark"] == "cantilever"

    def test_verify_kinds_includes_benchmark(self):
        """_VERIFY_KINDS includes 'benchmark'."""
        from mechdsl.integration import _VERIFY_KINDS

        assert "benchmark" in _VERIFY_KINDS, (
            f"'benchmark' must be in _VERIFY_KINDS; got {_VERIFY_KINDS!r}"
        )


# ---------------------------------------------------------------------------
# 10. _LIB_PLASTICITY_CATALOG drift guard — the static lib/plasticity* entries
#     must stay in sync with the real (Taichi-bound) Material dataclasses.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestLibPlasticityCatalogDrift:
    """Catch silent drift between the hand-maintained static catalog and reality.

    ``mechdsl.lib.plasticity_kinematic`` and ``…plasticity_mixed`` exec
    transpiled Taichi source at import time (firing ``ti.init``), so
    ``model_catalog`` lists their models *statically* in
    ``_LIB_PLASTICITY_CATALOG`` rather than introspecting them live.  That
    static list can silently diverge if the underlying ``Material`` dataclasses
    gain or lose a field.  This guard imports the real dataclasses in a fresh
    interpreter (Taichi is allowed to load there) and asserts the catalog's
    ``params`` still match the dataclass field names exactly.
    """

    def test_static_catalog_params_match_real_dataclasses(self):
        """Each _LIB_PLASTICITY_CATALOG entry's params == its Material dataclass fields."""
        script = (
            "import sys; "
            "from dataclasses import fields; "
            "from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial; "
            "from mechdsl.lib.plasticity_kinematic import J2KinematicMaterial; "
            "from mechdsl.lib.plasticity_mixed import J2MixedMaterial; "
            "from mechdsl.integration import _LIB_PLASTICITY_CATALOG; "
            "real = {"
            "  'j2_isotropic': [f.name for f in fields(J2PowerLawMaterial)],"
            "  'j2_kinematic': [f.name for f in fields(J2KinematicMaterial)],"
            "  'j2_mixed': [f.name for f in fields(J2MixedMaterial)],"
            "}; "
            "by_name = {e['name']: e for e in _LIB_PLASTICITY_CATALOG}; "
            "drift = {n: (by_name[n]['params'], rp) "
            "         for n, rp in real.items() if by_name[n]['params'] != rp}; "
            "print('drift:', drift); "
            "sys.exit(1 if drift else 0)"
        )
        r = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert r.returncode == 0, (
            "_LIB_PLASTICITY_CATALOG params have drifted from the real Material "
            "dataclasses — update the static catalog in mechdsl/integration/"
            f"__init__.py.\nstdout: {r.stdout!r}\nstderr: {r.stderr!r}"
        )
        assert "drift: {}" in r.stdout
