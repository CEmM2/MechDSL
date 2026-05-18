"""Live audit for recovery-plan P5-3: Taichi codegen façade layer.

Task P5-3 introduces a thin façade over the existing module-level emitters
(``emit_preamble``, ``emit_constants``, ``emit_field_declarations``,
``emit_constitutive_update``) in ``taichi_printer.py:323+``. The façade
should present a design-doc-aligned API (an object/class that aggregates
``emit_*`` helpers under one entry point) while leaving the underlying
emitters intact.

Acceptance criteria:
1. Snapshot/API tests confirm façade stability without loss of current behavior.
2. All deliverables for P5-3 are in place at the surfaces listed.
3. No regressions on the existing test suite.
"""

from __future__ import annotations

import inspect

import pytest

import mechdsl.codegen.taichi_printer as tp
from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    TaichiCodegenFacade,
    emit,
    emit_constants,
    emit_constitutive_update,
    emit_explicit_driver,
    emit_field_declarations,
    emit_internal_force_kernel,
    emit_main,
    emit_newton_driver,
    emit_postprocess,
    emit_preamble,
    emit_tangent_matvec_kernel,
    emit_validate_mesh,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize


def _make_test_bundle() -> ArtifactBundle:
    """Create a minimal test bundle for P5-3 façade testing."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


def _make_j2_bundle() -> ArtifactBundle:
    """Create a minimal test bundle with J2 plasticity for P5-3 façade testing."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y": 250.0, "n_exp": 10.0},
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


# ---------------------------------------------------------------------------
# P5-3-c1: Snapshot/API tests confirm façade stability
# ---------------------------------------------------------------------------


class TestP5_3FacadeAPI:
    """P5-3-c1: Façade API stability — object/class aggregates emit_* helpers."""

    @pytest.mark.unit
    def test_facade_class_exists_in_module(self) -> None:
        """Verify that a façade class exists in taichi_printer module."""
        assert hasattr(tp, "TaichiCodegenFacade"), (
            "TaichiCodegenFacade class not found in mechdsl.codegen.taichi_printer"
        )
        assert inspect.isclass(tp.TaichiCodegenFacade)

    @pytest.mark.unit
    def test_facade_aggregates_preamble_emission(self) -> None:
        """Façade has method/property that calls emit_preamble."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "preamble"), "façade missing 'preamble' method"
        assert callable(facade.preamble)
        # Verify it actually delegates: output must match emit_preamble directly
        bundle = _make_test_bundle()
        ctx_direct = EmissionContext()
        emit_preamble(ctx_direct, bundle)
        ctx_facade = EmissionContext()
        facade.preamble(ctx_facade, bundle)
        assert ctx_facade.get_source() == ctx_direct.get_source()

    @pytest.mark.unit
    def test_facade_aggregates_constants_emission(self) -> None:
        """Façade has method/property that calls emit_constants."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "constants"), "façade missing 'constants' method"
        assert callable(facade.constants)
        bundle = _make_test_bundle()
        ctx_direct = EmissionContext()
        emit_constants(ctx_direct, bundle)
        ctx_facade = EmissionContext()
        facade.constants(ctx_facade, bundle)
        assert ctx_facade.get_source() == ctx_direct.get_source()

    @pytest.mark.unit
    def test_facade_aggregates_field_declarations_emission(self) -> None:
        """Façade has method/property that calls emit_field_declarations."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "field_declarations"), "façade missing 'field_declarations' method"
        assert callable(facade.field_declarations)
        bundle = _make_test_bundle()
        ctx_direct = EmissionContext()
        emit_field_declarations(ctx_direct, bundle)
        ctx_facade = EmissionContext()
        facade.field_declarations(ctx_facade, bundle)
        assert ctx_facade.get_source() == ctx_direct.get_source()

    @pytest.mark.unit
    def test_facade_aggregates_constitutive_update_emission(self) -> None:
        """Façade has method/property that calls emit_constitutive_update."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "constitutive_update"), "façade missing 'constitutive_update' method"
        assert callable(facade.constitutive_update)
        bundle = _make_test_bundle()
        ctx_direct = EmissionContext()
        emit_constitutive_update(ctx_direct, bundle)
        ctx_facade = EmissionContext()
        facade.constitutive_update(ctx_facade, bundle)
        assert ctx_facade.get_source() == ctx_direct.get_source()

    @pytest.mark.unit
    def test_facade_aggregates_internal_force_kernel_emission(self) -> None:
        """Façade delegates internal_force_kernel to emit_internal_force_kernel."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "internal_force_kernel"), (
            "façade missing 'internal_force_kernel' method"
        )
        assert callable(facade.internal_force_kernel)
        bundle = _make_test_bundle()

        ctx_direct = EmissionContext()
        emit_internal_force_kernel(ctx_direct, bundle)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.internal_force_kernel(ctx_facade, bundle)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_aggregates_tangent_matvec_kernel_emission(self) -> None:
        """Façade delegates tangent_matvec_kernel to emit_tangent_matvec_kernel."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "tangent_matvec_kernel"), (
            "façade missing 'tangent_matvec_kernel' method"
        )
        assert callable(facade.tangent_matvec_kernel)
        bundle = _make_test_bundle()

        ctx_direct = EmissionContext()
        emit_tangent_matvec_kernel(ctx_direct, bundle)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.tangent_matvec_kernel(ctx_facade, bundle)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_aggregates_newton_driver_emission(self) -> None:
        """Façade delegates newton_driver to emit_newton_driver."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "newton_driver"), "façade missing 'newton_driver' method"
        assert callable(facade.newton_driver)
        bundle = _make_test_bundle()

        ctx_direct = EmissionContext()
        emit_newton_driver(ctx_direct, bundle)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.newton_driver(ctx_facade, bundle)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_aggregates_explicit_driver_emission(self) -> None:
        """Façade delegates explicit_driver to emit_explicit_driver."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "explicit_driver"), "façade missing 'explicit_driver' method"
        assert callable(facade.explicit_driver)
        bundle = _make_test_bundle()

        ctx_direct = EmissionContext()
        emit_explicit_driver(ctx_direct, bundle)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.explicit_driver(ctx_facade, bundle)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_aggregates_validate_mesh_emission(self) -> None:
        """Façade delegates validate_mesh to emit_validate_mesh (ctx-only, no bundle)."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "validate_mesh"), "façade missing 'validate_mesh' method"
        assert callable(facade.validate_mesh)

        ctx_direct = EmissionContext()
        emit_validate_mesh(ctx_direct)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.validate_mesh(ctx_facade)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_aggregates_postprocess_emission(self) -> None:
        """Façade delegates postprocess to emit_postprocess."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "postprocess"), "façade missing 'postprocess' method"
        assert callable(facade.postprocess)
        bundle = _make_test_bundle()

        ctx_direct = EmissionContext()
        emit_postprocess(ctx_direct, bundle)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.postprocess(ctx_facade, bundle)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_aggregates_main_emission(self) -> None:
        """Façade delegates main to emit_main."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "main"), "façade missing 'main' method"
        assert callable(facade.main)
        bundle = _make_test_bundle()

        ctx_direct = EmissionContext()
        emit_main(ctx_direct, bundle)
        direct_output = ctx_direct.get_source()

        ctx_facade = EmissionContext()
        facade.main(ctx_facade, bundle)
        facade_output = ctx_facade.get_source()

        assert facade_output == direct_output
        assert facade_output.strip()  # non-empty

    @pytest.mark.unit
    def test_facade_make_context_returns_emission_context(self) -> None:
        """Façade.make_context() returns a fresh EmissionContext instance."""
        facade = TaichiCodegenFacade()
        assert hasattr(facade, "make_context"), "façade missing 'make_context' method"
        assert callable(facade.make_context)

        ctx = facade.make_context()
        assert isinstance(ctx, EmissionContext), (
            f"make_context() returned {type(ctx).__name__!r}, expected EmissionContext"
        )
        # Each call should return a fresh (independent) context
        ctx2 = facade.make_context()
        assert ctx is not ctx2, "make_context() returned the same object on repeated calls"


class TestP5_3FacadeSnapshot:
    """P5-3-c1: Snapshot equality — output unchanged after façade wrapping."""

    @pytest.mark.unit
    def test_facade_emission_matches_direct_emission(self) -> None:
        """Output from façade emission equals output from direct emitter calls.

        This verifies that the new façade layer is a pure wrapper with no
        changes to the emitted code. The acceptance bar is snapshot equality.
        """
        bundle = _make_test_bundle()
        direct_source = emit(bundle)
        facade = TaichiCodegenFacade()
        facade_source = facade.emit_all(bundle)
        assert facade_source == direct_source, (
            "Façade emit_all() output differs from direct emit() — "
            "façade must be a pure pass-through wrapper"
        )

    @pytest.mark.unit
    def test_facade_deterministic_output(self) -> None:
        """Façade produces deterministic output — same input → same output."""
        bundle = _make_test_bundle()
        facade = TaichiCodegenFacade()
        source_a = facade.emit_all(bundle)
        source_b = facade.emit_all(bundle)
        assert source_a == source_b, "TaichiCodegenFacade.emit_all() is not deterministic"

    @pytest.mark.unit
    def test_svk_vs_j2_still_differ_through_facade(self) -> None:
        """Different material models still produce different façade output."""
        svk_bundle = _make_test_bundle()
        j2_bundle = _make_j2_bundle()
        facade = TaichiCodegenFacade()
        svk_source = facade.emit_all(svk_bundle)
        j2_source = facade.emit_all(j2_bundle)
        assert svk_source != j2_source, (
            "SVK and J2 bundles produced identical façade output — "
            "material-model distinction was lost"
        )


class TestP5_3BackendStability:
    """P5-3-c1: Underlying emitters remain unchanged — backward compatibility."""

    @pytest.mark.unit
    def test_emit_preamble_callable_and_signature_unchanged(self) -> None:
        """emit_preamble signature remains compatible with prior usage.

        Asserts callable, that 'ctx' and 'bundle' are present, and that the
        minimum required arity is 2 — but allows optional kwargs to be added
        in future without breaking this test.
        """
        sig = inspect.signature(emit_preamble)
        params = sig.parameters
        assert "ctx" in params, f"emit_preamble missing 'ctx' parameter: {list(params)}"
        assert "bundle" in params, f"emit_preamble missing 'bundle' parameter: {list(params)}"
        required = [p for p in params.values() if p.default is inspect.Parameter.empty]
        assert len(required) >= 2, (
            f"emit_preamble must have at least 2 required params (ctx + bundle), got {len(required)}"
        )

    @pytest.mark.unit
    def test_emit_constants_callable_and_signature_unchanged(self) -> None:
        """emit_constants signature remains compatible with prior usage.

        Asserts callable, that 'ctx' and 'bundle' are present, and that the
        minimum required arity is 2 — but allows optional kwargs to be added
        in future without breaking this test.
        """
        sig = inspect.signature(emit_constants)
        params = sig.parameters
        assert "ctx" in params, f"emit_constants missing 'ctx' parameter: {list(params)}"
        assert "bundle" in params, f"emit_constants missing 'bundle' parameter: {list(params)}"
        required = [p for p in params.values() if p.default is inspect.Parameter.empty]
        assert len(required) >= 2, (
            f"emit_constants must have at least 2 required params (ctx + bundle), got {len(required)}"
        )

    @pytest.mark.unit
    def test_emit_field_declarations_callable_and_signature_unchanged(self) -> None:
        """emit_field_declarations signature remains compatible with prior usage.

        Asserts callable, that 'ctx' and 'bundle' are present, and that the
        minimum required arity is 2 — but allows optional kwargs to be added
        in future without breaking this test.
        """
        sig = inspect.signature(emit_field_declarations)
        params = sig.parameters
        assert "ctx" in params, f"emit_field_declarations missing 'ctx' parameter: {list(params)}"
        assert "bundle" in params, (
            f"emit_field_declarations missing 'bundle' parameter: {list(params)}"
        )
        required = [p for p in params.values() if p.default is inspect.Parameter.empty]
        assert len(required) >= 2, (
            f"emit_field_declarations must have at least 2 required params (ctx + bundle), "
            f"got {len(required)}"
        )

    @pytest.mark.unit
    def test_emit_constitutive_update_callable_and_signature_unchanged(self) -> None:
        """emit_constitutive_update signature remains compatible with prior usage.

        Asserts callable, that 'ctx' and 'bundle' are present, and that the
        minimum required arity is 2 — but allows optional kwargs to be added
        in future without breaking this test.
        """
        sig = inspect.signature(emit_constitutive_update)
        params = sig.parameters
        assert "ctx" in params, f"emit_constitutive_update missing 'ctx' parameter: {list(params)}"
        assert "bundle" in params, (
            f"emit_constitutive_update missing 'bundle' parameter: {list(params)}"
        )
        required = [p for p in params.values() if p.default is inspect.Parameter.empty]
        assert len(required) >= 2, (
            f"emit_constitutive_update must have at least 2 required params (ctx + bundle), "
            f"got {len(required)}"
        )

    @pytest.mark.unit
    def test_emitters_still_callable_via_direct_import(self) -> None:
        """Direct imports of emitter functions continue to work."""
        # All the imports at the top of this module already exercise this.
        # Additionally verify they are callable and present on the module.
        for name in (
            "emit_preamble",
            "emit_constants",
            "emit_field_declarations",
            "emit_constitutive_update",
            "emit_internal_force_kernel",
            "emit_tangent_matvec_kernel",
            "emit_newton_driver",
            "emit_explicit_driver",
            "emit_validate_mesh",
            "emit_postprocess",
            "emit_main",
            "emit",
        ):
            assert hasattr(tp, name), f"module-level function '{name}' missing"
            assert callable(getattr(tp, name)), f"'{name}' is not callable"


# ---------------------------------------------------------------------------
# P5-3-c2: Deliverables present at surfaces
# ---------------------------------------------------------------------------


class TestP5_3ExportSurface:
    """P5-3-c2: Façade is exported at package level."""

    @pytest.mark.unit
    def test_facade_exported_from_taichi_printer(self) -> None:
        """Façade is exported from mechdsl.codegen.taichi_printer module."""
        from mechdsl.codegen import taichi_printer

        assert hasattr(taichi_printer, "TaichiCodegenFacade"), (
            "TaichiCodegenFacade not found on mechdsl.codegen.taichi_printer"
        )

    @pytest.mark.unit
    def test_facade_accessible_via_package_import(self) -> None:
        """Façade can be imported from mechdsl.codegen (or broader)."""
        from mechdsl.codegen import TaichiCodegenFacade as _F

        assert _F is TaichiCodegenFacade

    @pytest.mark.unit
    def test_facade_has_design_doc_aligned_api(self) -> None:
        """Façade API aligns with design document style (v1.0 codegen spec)."""
        facade = TaichiCodegenFacade()
        # Verify the expected method names for the design-doc-aligned API
        expected_methods = [
            "make_context",
            "preamble",
            "constants",
            "field_declarations",
            "constitutive_update",
            "internal_force_kernel",
            "tangent_matvec_kernel",
            "newton_driver",
            "explicit_driver",
            "validate_mesh",
            "postprocess",
            "main",
            "emit_all",
        ]
        for method in expected_methods:
            assert hasattr(facade, method), (
                f"TaichiCodegenFacade missing design-doc method: '{method}'"
            )
            assert callable(getattr(facade, method)), (
                f"TaichiCodegenFacade.{method} is not callable"
            )


class TestP5_3FileDeliverables:
    """P5-3-c2: All deliverables are in place."""

    @pytest.mark.unit
    def test_taichi_printer_contains_facade_definition(self) -> None:
        """taichi_printer.py contains the façade class/object definition."""
        import inspect

        source = inspect.getsource(tp)
        assert "class TaichiCodegenFacade" in source, (
            "TaichiCodegenFacade class definition not found in taichi_printer.py"
        )

    @pytest.mark.unit
    def test_package_init_exports_facade(self) -> None:
        """Package __init__.py exports the façade for public API."""
        import mechdsl.codegen as codegen_pkg

        assert hasattr(codegen_pkg, "TaichiCodegenFacade"), (
            "TaichiCodegenFacade not in mechdsl.codegen namespace"
        )
        # Also verify it appears in __all__ if defined
        if hasattr(codegen_pkg, "__all__"):
            assert "TaichiCodegenFacade" in codegen_pkg.__all__, (
                "TaichiCodegenFacade not in mechdsl.codegen.__all__"
            )

    @pytest.mark.unit
    def test_facade_has_docstring_explaining_role(self) -> None:
        """Façade has docstring documenting its role as aggregator."""
        doc = TaichiCodegenFacade.__doc__
        assert doc is not None, "TaichiCodegenFacade has no docstring"
        assert len(doc.strip()) > 0, "TaichiCodegenFacade docstring is empty"
        # Verify the docstring mentions façade/aggregation intent
        doc_lower = doc.lower()
        assert any(
            keyword in doc_lower
            for keyword in ("façade", "facade", "aggregat", "design-doc", "wrapper", "delegate")
        ), "TaichiCodegenFacade docstring does not describe its façade/aggregation role"
