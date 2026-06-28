"""Tests for Task P1-1: Scaffold mechdsl.integration module + capabilities() + model_catalog().

AC[0]: capabilities() returns the documented keys.
AC[1]: model_catalog() enumerates each model with tier/dissipative flags.
AC[2]: importing mechdsl.integration does not trigger ti.init.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


class TestTaskP1_1:
    """Tests for Task P1-1: Scaffold mechdsl.integration module + capabilities() + model_catalog()."""

    # -----------------------------------------------------------------------
    # AC[0]: capabilities() shape
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_capabilities_shape(self):
        """capabilities() returns all documented keys with correct types/values."""
        from mechdsl.integration import capabilities

        caps = capabilities()

        # All required keys must be present
        required_keys = {
            "version",
            "python",
            "profiles",
            "backends",
            "actions",
            "taichi_required_for",
            "models",
        }
        assert required_keys == set(caps.keys()), (
            f"capabilities() keys mismatch. "
            f"Missing: {required_keys - set(caps.keys())!r}. "
            f"Extra: {set(caps.keys()) - required_keys!r}."
        )

        # version: a non-empty string
        assert isinstance(caps["version"], str) and caps["version"], (
            "version must be a non-empty string"
        )

        # python: fixed specifier string
        assert caps["python"] == ">=3.12,<3.13", (
            f"Expected python='>=3.12,<3.13', got {caps['python']!r}"
        )

        # profiles: list derived from ALLOWED_PROFILES — must contain "mvp"
        assert isinstance(caps["profiles"], list), "profiles must be a list"
        assert "mvp" in caps["profiles"], "profiles must include 'mvp'"

        # backends: exactly ["taichi"] for MVP
        assert caps["backends"] == ["taichi"], (
            f"Expected backends=['taichi'], got {caps['backends']!r}"
        )

        # actions: the three canonical actions
        expected_actions = {"emit", "transpile", "verify"}
        assert set(caps["actions"]) == expected_actions, (
            f"actions mismatch: got {caps['actions']!r}"
        )

        # taichi_required_for: only verify pays the Taichi cost
        assert caps["taichi_required_for"] == ["verify"], (
            f"Expected taichi_required_for=['verify'], got {caps['taichi_required_for']!r}"
        )

        # models: non-empty list of strings; must include the two MVP models
        assert isinstance(caps["models"], list) and len(caps["models"]) > 0, (
            "models must be a non-empty list"
        )
        assert all(isinstance(m, str) for m in caps["models"]), "each model entry must be a string"
        assert "svk" in caps["models"], "capabilities.models must include 'svk'"
        assert "j2" in caps["models"] or "j2_isotropic" in caps["models"], (
            "capabilities.models must include the j2 power-law model"
        )

    @pytest.mark.unit
    def test_capabilities_profiles_matches_allowed_profiles(self):
        """capabilities().profiles is exactly the sorted ALLOWED_PROFILES set."""
        from mechdsl import ALLOWED_PROFILES
        from mechdsl.integration import capabilities

        caps = capabilities()
        assert caps["profiles"] == sorted(ALLOWED_PROFILES), (
            "capabilities.profiles must equal sorted(ALLOWED_PROFILES)"
        )

    # -----------------------------------------------------------------------
    # AC[1]: model_catalog() entries
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_model_catalog_entries(self):
        """model_catalog() enumerates each model with correct field shapes."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()

        assert isinstance(catalog, list) and len(catalog) > 0, (
            "model_catalog() must return a non-empty list"
        )

        required_entry_keys = {"name", "module", "tier", "dissipative", "params", "state_variables"}

        for entry in catalog:
            assert required_entry_keys == set(entry.keys()), (
                f"Entry {entry.get('name')!r} has wrong keys. "
                f"Missing: {required_entry_keys - set(entry.keys())!r}. "
                f"Extra: {set(entry.keys()) - required_entry_keys!r}."
            )
            # name: non-empty string
            assert isinstance(entry["name"], str) and entry["name"], (
                f"name must be a non-empty string: {entry!r}"
            )
            # module: dotted path string
            assert isinstance(entry["module"], str) and "." in entry["module"], (
                f"module must be a dotted path string: {entry!r}"
            )
            # tier: one of the two allowed values
            assert entry["tier"] in ("mvp", "experimental"), (
                f"tier must be 'mvp' or 'experimental': {entry!r}"
            )
            # dissipative: bool
            assert isinstance(entry["dissipative"], bool), f"dissipative must be bool: {entry!r}"
            # params: list of strings
            assert isinstance(entry["params"], list) and all(
                isinstance(p, str) for p in entry["params"]
            ), f"params must be a list of strings: {entry!r}"
            # state_variables: list of strings
            assert isinstance(entry["state_variables"], list) and all(
                isinstance(s, str) for s in entry["state_variables"]
            ), f"state_variables must be a list of strings: {entry!r}"

    @pytest.mark.unit
    def test_model_catalog_mvp_models_present(self):
        """SVK and J2 power-law models are present and correctly tagged as mvp."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()
        by_name = {e["name"]: e for e in catalog}

        # SVK: mvp, not dissipative, Lame parameters
        assert "svk" in by_name, "svk must be in model_catalog()"
        svk = by_name["svk"]
        assert svk["tier"] == "mvp", f"svk tier must be 'mvp', got {svk['tier']!r}"
        assert svk["dissipative"] is False, "svk must not be dissipative"
        assert set(svk["params"]) == {"lam", "mu"}, (
            f"svk params must be {{'lam', 'mu'}}, got {svk['params']!r}"
        )
        assert svk["state_variables"] == [], "svk state_variables must be empty"

        # J2 power-law (symbolic model)
        assert "j2" in by_name, "j2 must be in model_catalog()"
        j2 = by_name["j2"]
        assert j2["tier"] == "mvp", f"j2 tier must be 'mvp', got {j2['tier']!r}"
        assert j2["dissipative"] is True, "j2 must be dissipative"
        assert "alpha" in j2["state_variables"], "j2 state_variables must contain 'alpha'"

        # J2 isotropic lib dispatcher (MVP tier, Taichi-bound)
        assert "j2_isotropic" in by_name, "j2_isotropic must be in model_catalog()"
        j2_iso = by_name["j2_isotropic"]
        assert j2_iso["tier"] == "mvp", f"j2_isotropic tier must be 'mvp', got {j2_iso['tier']!r}"
        assert j2_iso["dissipative"] is True, "j2_isotropic must be dissipative"

    @pytest.mark.unit
    def test_model_catalog_experimental_models_present(self):
        """All expected experimental models appear in catalog."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()
        names = {e["name"] for e in catalog}

        expected_experimental = {
            "neo_hookean",
            "mooney_rivlin",
            "ogden",
            "hgo",
            "perzyna",
            "johnson_cook",
            "lemaitre",
            "j2_kinematic",
            "j2_mixed",
        }
        missing = expected_experimental - names
        assert not missing, f"model_catalog() is missing experimental models: {missing!r}"

    @pytest.mark.unit
    def test_model_catalog_dissipative_models_have_state_variables(self):
        """Dissipative models must have at least one state variable."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()
        for entry in catalog:
            if entry["dissipative"]:
                assert len(entry["state_variables"]) > 0, (
                    f"Dissipative model {entry['name']!r} must have state_variables, "
                    f"got {entry['state_variables']!r}"
                )

    @pytest.mark.unit
    def test_model_catalog_elastic_models_have_no_state_variables(self):
        """Non-dissipative (elastic) models must have empty state_variables."""
        from mechdsl.integration import model_catalog

        catalog = model_catalog()
        for entry in catalog:
            if not entry["dissipative"]:
                assert entry["state_variables"] == [], (
                    f"Elastic model {entry['name']!r} must have empty state_variables, "
                    f"got {entry['state_variables']!r}"
                )

    # -----------------------------------------------------------------------
    # AC[2]: no ti.init on import (subprocess — most robust)
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_no_ti_init_on_import(self):
        """Importing mechdsl.integration and calling capabilities()/model_catalog()
        must not trigger ti.init (i.e. must not load the taichi package).

        Uses a subprocess with a fresh interpreter so no parent-process state
        can contaminate the result.  The subprocess exits with code 0 on success
        or code 1 if taichi appears in sys.modules.
        """
        script = (
            "import sys; "
            "from mechdsl.integration import capabilities, model_catalog; "
            "capabilities(); "
            "model_catalog(); "
            "taichi_loaded = 'taichi' in sys.modules; "
            "print('taichi_loaded:', taichi_loaded); "
            "sys.exit(1 if taichi_loaded else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Print stderr for diagnostics if the test fails
        assert result.returncode == 0, (
            "Importing mechdsl.integration triggered ti.init (taichi was loaded).\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
        assert "taichi_loaded: False" in result.stdout, (
            f"Expected 'taichi_loaded: False' in subprocess stdout.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )

    @pytest.mark.unit
    def test_no_ti_init_on_import_monkeypatch(self, monkeypatch):
        """Secondary check using monkeypatch: if taichi were imported, ti.init
        would be called and the patched version would raise.

        This test runs in the same process.  Because other tests may have
        already imported mechdsl.integration (and therefore cached imports),
        this complements — rather than replaces — the subprocess test above.
        """
        import importlib
        import types

        # Create a fake taichi module whose init() raises immediately.
        fake_ti = types.ModuleType("taichi")

        def _init_raises(*args, **kwargs):
            raise RuntimeError("ti.init was called — Taichi-free guarantee violated!")

        fake_ti.init = _init_raises  # type: ignore[attr-defined]

        # Patch sys.modules so that any `import taichi` gets our fake module.
        monkeypatch.setitem(sys.modules, "taichi", fake_ti)

        # Importing and calling the API must NOT call ti.init.
        # (Re-importing may use cached modules; that's fine — the point is
        # that the façade API itself doesn't call ti.init.)
        integration = importlib.import_module("mechdsl.integration")
        caps = integration.capabilities()
        catalog = integration.model_catalog()

        assert isinstance(caps, dict), "capabilities() must return a dict"
        assert isinstance(catalog, list), "model_catalog() must return a list"

    # -----------------------------------------------------------------------
    # Integration check: capabilities().models matches model_catalog() names
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_capabilities_models_matches_catalog(self):
        """capabilities().models must equal [e['name'] for e in model_catalog()]."""
        from mechdsl.integration import capabilities, model_catalog

        caps = capabilities()
        catalog = model_catalog()
        expected_models = [e["name"] for e in catalog]
        assert caps["models"] == expected_models, (
            f"capabilities.models does not match model_catalog() names.\n"
            f"capabilities.models: {caps['models']!r}\n"
            f"model_catalog names: {expected_models!r}"
        )
