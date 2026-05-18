"""Tests for Phase 1: ConstitutiveModel ABC and wrapper classes.

Covers tasks P1-T1 (ABC), P1-T2 (SVKModel), P1-T3 (J2Model), P1-T5 (integration).
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.constitutive import ConstitutiveModel
from mechdsl.symbolic.models.j2_power_law import J2Model, J2PowerLawMaterial, radial_return
from mechdsl.symbolic.models.svk import (
    SVKMaterial,
    SVKModel,
    material_tangent_4th,
    material_tangent_voigt,
    pk2_stress,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def svk_mat() -> SVKMaterial:
    """Standard SVK material: E=200e3, nu=0.3."""
    return SVKMaterial.from_E_nu(200e3, 0.3)


@pytest.fixture()
def svk_strain() -> np.ndarray:
    """Fixed-seed random symmetric 3x3 Green-Lagrange strain for SVK tests."""
    rng = np.random.default_rng(42)
    A = rng.standard_normal((3, 3))
    return 0.01 * (A + A.T)


@pytest.fixture()
def j2_mat() -> J2PowerLawMaterial:
    """Standard J2 material: E=200e3, nu=0.3, sigma_y0=250, K=500, n=1."""
    return J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=1.0)


@pytest.fixture()
def j2_strain() -> np.ndarray:
    """Small uniaxial strain above yield threshold for J2 tests."""
    return 0.01 * np.eye(3)


# ============================================================================
# P1-T1: ConstitutiveModel ABC
# ============================================================================


class TestConstitutiveModelABC:
    """Tests for Task P1-T1: Implement ConstitutiveModel ABC.

    Acceptance criteria covered: AC1 (importable), AC2 (5 abstract methods),
    AC3 (cannot instantiate directly).
    """

    def test_import_constitutive_model(self):
        """Verifies: ConstitutiveModel is importable from mechdsl.symbolic.constitutive.

        Acceptance criterion: ConstitutiveModel is importable
        Passes when: import succeeds without error.
        """
        # Import already happened at module level; reaching here means it succeeded.
        assert ConstitutiveModel is not None

    def test_abc_cannot_be_instantiated(self):
        """Verifies: ConstitutiveModel cannot be instantiated directly.

        Acceptance criterion: ABC cannot be instantiated directly (raises TypeError)
        Passes when: ConstitutiveModel() raises TypeError.
        """
        with pytest.raises(TypeError):
            ConstitutiveModel()  # type: ignore[abstract]

    def test_abc_defines_five_abstract_methods(self):
        """Verifies: ABC defines pk2_stress, material_tangent, voigt_tangent,
        state_variables, is_dissipative.

        Acceptance criterion: ABC defines all 5 abstract methods with correct signatures
        Passes when: all 5 names are in ABC.__abstractmethods__.
        """
        expected = {
            "pk2_stress",
            "material_tangent",
            "voigt_tangent",
            "state_variables",
            "is_dissipative",
        }
        assert expected == ConstitutiveModel.__abstractmethods__


# ============================================================================
# P1-T2: SVKModel wrapper
# ============================================================================


class TestSVKModelWrapper:
    """Tests for Task P1-T2: Add SVKModel wrapper class.

    Acceptance criteria covered: SVKModel importable, wraps existing functions
    with identical output, state_variables=(), is_dissipative=False.
    """

    def test_svk_stress_matches_standalone(self, svk_mat: SVKMaterial, svk_strain: np.ndarray):
        """Verifies: SVKModel.pk2_stress produces identical output to standalone pk2_stress.

        Acceptance criterion: SVKModel wraps existing functions, producing identical numerical output
        Passes when: np.array_equal(model.pk2_stress(E), pk2_stress(mat, E)).
        """
        model = SVKModel(svk_mat)
        assert np.array_equal(model.pk2_stress(svk_strain), pk2_stress(svk_mat, svk_strain))

    def test_svk_tangent_matches_standalone(self, svk_mat: SVKMaterial, svk_strain: np.ndarray):
        """Verifies: SVKModel.material_tangent produces identical output to material_tangent_4th.

        Acceptance criterion: SVKModel wraps existing functions, producing identical numerical output
        Passes when: np.array_equal(model.material_tangent(E), material_tangent_4th(mat)).
        """
        model = SVKModel(svk_mat)
        assert np.array_equal(model.material_tangent(svk_strain), material_tangent_4th(svk_mat))

    def test_svk_voigt_tangent_matches_standalone(
        self, svk_mat: SVKMaterial, svk_strain: np.ndarray
    ):
        """Verifies: SVKModel.voigt_tangent produces identical output to material_tangent_voigt.

        Acceptance criterion: SVKModel wraps existing functions, producing identical numerical output
        Passes when: np.array_equal(model.voigt_tangent(E), material_tangent_voigt(mat)).
        """
        model = SVKModel(svk_mat)
        assert np.array_equal(model.voigt_tangent(svk_strain), material_tangent_voigt(svk_mat))

    def test_svk_state_variables(self, svk_mat: SVKMaterial):
        """Verifies: SVKModel.state_variables returns empty tuple.

        Acceptance criterion: state_variables == ()
        Passes when: model.state_variables == ().
        """
        model = SVKModel(svk_mat)
        assert model.state_variables == ()

    def test_svk_is_not_dissipative(self, svk_mat: SVKMaterial):
        """Verifies: SVKModel.is_dissipative returns False.

        Acceptance criterion: is_dissipative == False
        Passes when: model.is_dissipative is False.
        """
        model = SVKModel(svk_mat)
        assert model.is_dissipative is False


# ============================================================================
# P1-T3: J2Model wrapper
# ============================================================================


class TestJ2ModelWrapper:
    """Tests for Task P1-T3: Add J2Model wrapper class.

    Acceptance criteria covered: J2Model importable, wraps radial_return
    with identical output, state_variables=('alpha',), is_dissipative=True.
    """

    def test_j2_stress_matches_radial_return(
        self, j2_mat: J2PowerLawMaterial, j2_strain: np.ndarray
    ):
        """Verifies: J2Model.pk2_stress produces identical stress to radial_return().stress.

        Acceptance criterion: J2Model wraps radial_return, producing identical numerical output
        Passes when: np.array_equal(model.pk2_stress(E, alpha=a), radial_return(mat, E, a).stress).
        """
        alpha = 0.01
        model = J2Model(j2_mat)
        expected = radial_return(j2_mat, j2_strain, alpha).stress
        assert np.array_equal(model.pk2_stress(j2_strain, alpha=alpha), expected)

    def test_j2_tangent_matches_radial_return(
        self, j2_mat: J2PowerLawMaterial, j2_strain: np.ndarray
    ):
        """Verifies: J2Model.material_tangent produces identical tangent to radial_return().tangent.

        Acceptance criterion: J2Model wraps radial_return, producing identical numerical output
        Passes when: np.array_equal(model.material_tangent(E, alpha=a), radial_return(mat, E, a).tangent).
        """
        alpha = 0.01
        model = J2Model(j2_mat)
        expected = radial_return(j2_mat, j2_strain, alpha).tangent
        assert np.array_equal(model.material_tangent(j2_strain, alpha=alpha), expected)

    def test_j2_handles_alpha_state(self, j2_mat: J2PowerLawMaterial):
        """Verifies: J2Model correctly passes alpha state variable through to radial_return.

        Acceptance criterion: J2Model handles alpha state variable correctly
        Passes when: model.pk2_stress(E, alpha=0.5) gives different result than alpha=0.0.
        """
        # Use a shear-dominated strain that has a non-zero deviatoric component
        # and exceeds yield, so alpha influences the stress state.
        E_shear = np.array(
            [[0.02, 0.01, 0.0], [0.01, -0.01, 0.0], [0.0, 0.0, -0.01]],
            dtype=np.float64,
        )
        model = J2Model(j2_mat)
        stress_low = model.pk2_stress(E_shear, alpha=0.0)
        stress_high = model.pk2_stress(E_shear, alpha=0.5)
        # Higher pre-existing plastic strain (alpha=0.5) raises the yield stress,
        # resulting in a different (larger) stress state under the same strain.
        assert not np.array_equal(stress_low, stress_high)

    def test_j2_state_variables(self, j2_mat: J2PowerLawMaterial):
        """Verifies: J2Model.state_variables returns ('alpha',).

        Acceptance criterion: state_variables == ('alpha',)
        Passes when: model.state_variables == ('alpha',).
        """
        model = J2Model(j2_mat)
        assert model.state_variables == ("alpha",)

    def test_j2_is_dissipative(self, j2_mat: J2PowerLawMaterial):
        """Verifies: J2Model.is_dissipative returns True.

        Acceptance criterion: is_dissipative == True
        Passes when: model.is_dissipative is True.
        """
        model = J2Model(j2_mat)
        assert model.is_dissipative is True


# ============================================================================
# P1-T5: Cross-model integration (ABC contract verification)
# ============================================================================


class TestConstitutiveABCIntegration:
    """Tests for Task P1-T5: Cross-model ABC contract verification.

    Acceptance criteria covered: both models satisfy ABC, numerical identity,
    shape validation.
    """

    def test_svk_is_instance_of_abc(self, svk_mat: SVKMaterial):
        """Verifies: SVKModel is a subclass of ConstitutiveModel.

        Acceptance criterion: Tests cover both elastic (SVK) and dissipative (J2) models
        Passes when: isinstance(SVKModel(mat), ConstitutiveModel) is True.
        """
        assert isinstance(SVKModel(svk_mat), ConstitutiveModel)

    def test_j2_is_instance_of_abc(self, j2_mat: J2PowerLawMaterial):
        """Verifies: J2Model is a subclass of ConstitutiveModel.

        Acceptance criterion: Tests cover both elastic (SVK) and dissipative (J2) models
        Passes when: isinstance(J2Model(mat), ConstitutiveModel) is True.
        """
        assert isinstance(J2Model(j2_mat), ConstitutiveModel)

    def test_shape_validation_wrong_strain(self, svk_mat: SVKMaterial):
        """Verifies: Wrong strain tensor shape raises ValueError.

        Acceptance criterion: Shape validation errors
        Passes when: model.pk2_stress(np.zeros((2,2))) raises ValueError.
        """
        model = SVKModel(svk_mat)
        with pytest.raises(ValueError):
            model.pk2_stress(np.zeros((2, 2)))
