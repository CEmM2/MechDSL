"""Tests for Task P5-3: switch lib/plasticity.py default to algo2code path
with feature-flag fallback.

Acceptance criteria covered:
1. Default solver run (no flag set) uses algo2code-generated path.
2. Setting ``MECHDSL_USE_IMPORTED_RR=1`` reverts to imported path.
3. Switch happens via env var alone — no rebuild / no JIT cache reset.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.lib.plasticity import (
    FEATURE_FLAG_ENV,
    ReturnMappingResult,
    active_path_name,
    radial_return,
)
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial


def _sample_material() -> J2PowerLawMaterial:
    return J2PowerLawMaterial(E=200_000.0, nu=0.3, sigma_y0=250.0, K=500.0, n=0.5)


def _zero_strain() -> np.ndarray:
    return np.zeros((3, 3), dtype=float)


class TestTaskP5_3:
    """Tests for Task P5-3: lib/plasticity.py dispatch + feature flag."""

    @pytest.mark.integration
    def test_default_path_is_algo2code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(FEATURE_FLAG_ENV, raising=False)
        assert active_path_name() == "algo2code"
        result = radial_return(_sample_material(), _zero_strain(), 0.0)
        assert isinstance(result, ReturnMappingResult)

    @pytest.mark.integration
    def test_flag_reverts_to_imported_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FEATURE_FLAG_ENV, "1")
        assert active_path_name() == "imported"
        result = radial_return(_sample_material(), _zero_strain(), 0.0)
        assert isinstance(result, ReturnMappingResult)

    @pytest.mark.integration
    def test_env_var_switch_no_recompile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Toggle the env var between calls within a single Python
        session and confirm ``active_path_name`` updates without any
        cached module-level state needing reset."""
        monkeypatch.delenv(FEATURE_FLAG_ENV, raising=False)
        assert active_path_name() == "algo2code"
        monkeypatch.setenv(FEATURE_FLAG_ENV, "1")
        assert active_path_name() == "imported"
        monkeypatch.setenv(FEATURE_FLAG_ENV, "0")
        assert active_path_name() == "algo2code"
        for truthy in ("true", "Yes", "ON"):
            monkeypatch.setenv(FEATURE_FLAG_ENV, truthy)
            assert active_path_name() == "imported", (
                f"truthy value {truthy!r} did not flip active path"
            )

    @pytest.mark.integration
    def test_radial_return_signature_matches_imported(self) -> None:
        """``mechdsl.lib.plasticity.radial_return`` exposes the same
        keyword surface as the imported implementation so callers can
        switch the import without code changes elsewhere.
        """
        import inspect

        from mechdsl.symbolic.models.j2_power_law import (
            radial_return as imported_rr,
        )

        dispatcher_sig = inspect.signature(radial_return)
        imported_sig = inspect.signature(imported_rr)
        assert list(dispatcher_sig.parameters) == list(imported_sig.parameters)

    @pytest.mark.integration
    def test_dispatch_preserves_imported_results_under_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under the feature flag, dispatcher output is bit-identical
        to a direct call into the imported implementation. Sanity
        check that the dispatcher does not silently transform the
        result.
        """
        from mechdsl.symbolic.models.j2_power_law import (
            radial_return as imported_rr,
        )

        mat = _sample_material()
        E = np.array(
            [[0.005, 0.0, 0.0], [0.0, -0.0025, 0.0], [0.0, 0.0, -0.0025]],
            dtype=float,
        )
        alpha_old = 0.001

        monkeypatch.setenv(FEATURE_FLAG_ENV, "1")
        via_dispatcher = radial_return(mat, E, alpha_old)
        direct = imported_rr(mat, E, alpha_old)

        np.testing.assert_array_equal(via_dispatcher.stress, direct.stress)
        assert via_dispatcher.alpha_new == direct.alpha_new
        assert via_dispatcher.delta_lambda == direct.delta_lambda
        assert via_dispatcher.is_plastic == direct.is_plastic
        np.testing.assert_array_equal(via_dispatcher.tangent, direct.tangent)
