"""Constitutive model interface: unified ABC for hyperelastic and dissipative models.

Every material model in the pipeline must implement this interface.
Hyperelastic models (SVK, neo-Hookean) derive stress from strain energy;
dissipative models (J2 plasticity) use algorithmic updates (return mapping).

The ``**state`` kwargs pattern allows flexible state variable passing:
elastic models ignore extra kwargs, J2 passes ``alpha=...``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray


class ConstitutiveModel(ABC):
    """Abstract base class for constitutive models.

    Subclasses must implement:

    - :meth:`pk2_stress` — second Piola-Kirchhoff stress from Green-Lagrange strain
    - :meth:`material_tangent` — fourth-order material tangent (3,3,3,3)
    - :meth:`voigt_tangent` — Voigt form of material tangent (6,6)
    - :attr:`state_variables` — names of internal state variables (empty for elastic)
    - :attr:`is_dissipative` — whether the model has irreversible behaviour
    """

    @abstractmethod
    def pk2_stress(self, E_strain: NDArray, **state: float) -> NDArray:
        """Compute PK2 stress from Green-Lagrange strain.

        Parameters
        ----------
        E_strain : (3, 3) NDArray
            Green-Lagrange strain tensor.
        **state : float
            Internal state variables (e.g. ``alpha`` for J2 plasticity).

        Returns
        -------
        NDArray (3, 3)
            Second Piola-Kirchhoff stress tensor.
        """

    @abstractmethod
    def material_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Compute the fourth-order material tangent.

        Parameters
        ----------
        E_strain : (3, 3) NDArray
            Green-Lagrange strain tensor.
        **state : float
            Internal state variables.

        Returns
        -------
        NDArray (3, 3, 3, 3)
            Material tangent C_IJKL.
        """

    @abstractmethod
    def voigt_tangent(self, E_strain: NDArray, **state: float) -> NDArray:
        """Compute the Voigt-form material tangent.

        Uses tensorial Voigt ordering ``[xx, yy, zz, xy, xz, yz]``
        with unscaled shears per ``07-CONVENTIONS.md``.

        Parameters
        ----------
        E_strain : (3, 3) NDArray
            Green-Lagrange strain tensor.
        **state : float
            Internal state variables.

        Returns
        -------
        NDArray (6, 6)
            Voigt material tangent.
        """

    @property
    @abstractmethod
    def state_variables(self) -> tuple[str, ...]:
        """Names of internal state variables.

        Returns an empty tuple for purely elastic models.
        """

    @property
    @abstractmethod
    def is_dissipative(self) -> bool:
        """Whether the model exhibits irreversible (dissipative) behaviour."""
