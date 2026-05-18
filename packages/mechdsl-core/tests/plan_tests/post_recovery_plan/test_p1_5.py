"""Tests for Task P1-5: Extend compile_latex façade to surface f_ext kernel."""

from __future__ import annotations

import pytest

from mechdsl import compile_latex

_NEUMANN_LATEX = (
    "% mechanics dim 3\n"
    "% mechanics cell hex8\n"
    "% mechanics formulation total_lagrangian\n"
    "% mechanics coord spatial x y z\n"
    "% mechanics coord material X Y Z\n"
    "% mechanics material svk --E 200e3 --nu 0.3\n"
    '% mechanics boundary fix --type dirichlet --components "0 1 2" --value 0\n'
    '% mechanics boundary load --type neumann --traction "0 0 -1000" --surface z1\n'
)

_DIRICHLET_LATEX = (
    "% mechanics dim 3\n"
    "% mechanics cell hex8\n"
    "% mechanics formulation total_lagrangian\n"
    "% mechanics coord spatial x y z\n"
    "% mechanics coord material X Y Z\n"
    "% mechanics material svk --E 200e3 --nu 0.3\n"
    '% mechanics boundary fix --type dirichlet --components "0 1 2" --value 0\n'
    "% mechanics boundary load --type neumann --traction t_bar\n"
)


class TestTaskP1_5:
    """Tests for compile_latex façade f_ext_kernel surfacing."""

    @pytest.mark.integration
    def test_neumann_directive_yields_populated_f_ext_kernel(self):
        """Acceptance criterion #1: numeric-traction Neumann directive yields a non-None f_ext_kernel."""
        bundle = compile_latex(_NEUMANN_LATEX)
        assert bundle.f_ext_kernel is not None
        assert "init_f_ext_from_neumann_load" in bundle.f_ext_kernel
        assert "f_factor: ti.f64" in bundle.f_ext_kernel
        # Traction baked deterministically.
        assert "-1000" in bundle.f_ext_kernel

    @pytest.mark.integration
    def test_pure_symbolic_traction_returns_none_f_ext_kernel(self):
        """Acceptance criterion #1 (back-compat): symbolic-string traction
        keeps the legacy imported numeric injection path; f_ext_kernel
        stays None."""
        bundle = compile_latex(_DIRICHLET_LATEX)
        assert bundle.f_ext_kernel is None

    @pytest.mark.integration
    def test_existing_residual_tangent_fields_unchanged(self):
        """Acceptance criterion #2: existing emitted_source and bundle
        fields keep their shape and content for the Dirichlet baseline."""
        bundle = compile_latex(_DIRICHLET_LATEX)
        assert isinstance(bundle.emitted_source, str)
        assert bundle.emitted_source != ""  # Taichi printer still ran
        # Pre-existing fields are still populated.
        assert bundle.problem_ir_dict["material"]["model"] == "svk"
        assert bundle.element_ir_summary["element_type"] == "hex8"

    @pytest.mark.integration
    def test_neumann_bundle_round_trips_through_to_dict(self):
        """f_ext_kernel survives to_dict / from_dict round-trip."""
        from mechdsl.codegen.artifact import ArtifactBundle

        bundle = compile_latex(_NEUMANN_LATEX)
        restored = ArtifactBundle.from_dict(bundle.to_dict())
        assert restored.f_ext_kernel == bundle.f_ext_kernel

    @pytest.mark.integration
    def test_kernel_emission_is_parametric_in_f_factor(self):
        """The façade-emitted kernel takes f_factor as a runtime arg
        (no mesh available at compile time) and bakes traction as a
        literal."""
        bundle = compile_latex(_NEUMANN_LATEX)
        assert bundle.f_ext_kernel is not None
        # Body multiplies the literal traction by the runtime f_factor.
        assert "* f_factor" in bundle.f_ext_kernel
        # Spatial-component loop uses ti.static per index-partitioning rule.
        assert "for d in ti.static(range(3))" in bundle.f_ext_kernel
        # Mesh loops use runtime range.
        assert "for i in range(n_nodes)" in bundle.f_ext_kernel
