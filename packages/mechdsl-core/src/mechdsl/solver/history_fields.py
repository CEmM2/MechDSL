"""History field lifecycle management for constitutive models.

Provides a general-purpose two-buffer (current / old) storage for state
variables.  On a converged Newton step the caller invokes ``commit()`` to
snapshot current → old.  On non-convergence, ``rollback()`` restores
current ← old.

Task P8.3 — production replacement for the ad-hoc ``HistoryFields`` class
in ``tests/ref/ref_hex8_plastic.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass
class HistoryFields:
    """Manages state variables for constitutive models.

    Stores current and old (converged) buffers for each registered field.
    On a converged Newton step, call ``commit()`` to update old = current.
    On non-convergence, call ``rollback()`` to restore current = old.
    """

    _fields: dict[str, dict[str, NDArray]] = field(default_factory=dict)
    # Each entry: {"current": array, "old": array}

    def register(self, name: str, shape: tuple[int, ...]) -> None:
        """Register a new history field with given *shape*, initialised to zero."""
        if name in self._fields:
            raise ValueError(f"History field '{name}' already registered")
        self._fields[name] = {
            "current": np.zeros(shape, dtype=np.float64),
            "old": np.zeros(shape, dtype=np.float64),
        }

    def get_current(self, name: str) -> NDArray:
        """Return the current (possibly uncommitted) buffer for *name*."""
        if name not in self._fields:
            raise KeyError(f"History field '{name}' not registered. Available: {self.field_names}")
        return self._fields[name]["current"]

    def get_old(self, name: str) -> NDArray:
        """Return the last committed (converged) buffer for *name*."""
        if name not in self._fields:
            raise KeyError(f"History field '{name}' not registered. Available: {self.field_names}")
        return self._fields[name]["old"]

    def set_current(self, name: str, value: NDArray) -> None:
        """Update the current buffer for *name* **in-place** (copy into existing array)."""
        if name not in self._fields:
            raise KeyError(f"History field '{name}' not registered. Available: {self.field_names}")
        self._fields[name]["current"][:] = value

    def commit(self) -> None:
        """Copy current → old for **all** registered fields.  Call on converged step."""
        for f in self._fields.values():
            f["old"][:] = f["current"]

    def rollback(self) -> None:
        """Restore current ← old for **all** registered fields.  Call on non-convergence."""
        for f in self._fields.values():
            f["current"][:] = f["old"]

    @property
    def field_names(self) -> list[str]:
        """Return a list of registered field names."""
        return list(self._fields.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._fields


def create_j2_history(n_elem: int, n_qp: int = 8) -> HistoryFields:
    """Create history fields for J2 plasticity.

    Registers:

    - ``"alpha"``: equivalent plastic strain ``(n_elem, n_qp)``
    - ``"plastic_strain"``: plastic strain tensor in Voigt ``(n_elem, n_qp, 6)``
    """
    h = HistoryFields()
    h.register("alpha", (n_elem, n_qp))
    h.register("plastic_strain", (n_elem, n_qp, 6))
    return h


def create_lemaitre_history(n_elem: int, n_qp: int = 8) -> HistoryFields:
    """Create history fields for Lemaitre damage coupled to J2 power-law plasticity.

    Extends :func:`create_j2_history` with two additional fields specific to
    the damage branch (Plan B phase B6, task P6-2):

    - ``"alpha"``: equivalent plastic strain ``(n_elem, n_qp)``
    - ``"plastic_strain"``: plastic strain tensor in Voigt ``(n_elem, n_qp, 6)``
    - ``"damage_D"``: scalar damage ``(n_elem, n_qp)`` in ``[0, 1 - 1e-6]``
    - ``"is_deleted"``: per-element deletion flag ``(n_elem,)`` — 0/1 stored as
      float (same dtype as the other history fields); once set to 1 it stays
      set and the element is skipped in the assembly loop.

    All fields are initialised to zero: undamaged, pristine material with
    all elements active.
    """
    h = HistoryFields()
    h.register("alpha", (n_elem, n_qp))
    h.register("plastic_strain", (n_elem, n_qp, 6))
    h.register("damage_D", (n_elem, n_qp))
    h.register("is_deleted", (n_elem,))
    return h
