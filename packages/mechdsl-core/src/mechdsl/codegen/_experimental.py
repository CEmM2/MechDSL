"""Experimental-backend infrastructure for mechdsl.codegen.

Defines the shared :class:`ExperimentalBackendWarning` that each non-stable
printer emits on first use, and documents the ``__experimental__`` flag
convention used across the codegen package.

Convention
----------
Every experimental backend module exposes a module-level constant::

    __experimental__: bool = True

This allows tooling and tests to detect experimental status
programmatically (e.g. ``import mechdsl.codegen.mfem_printer as m;
assert m.__experimental__``) rather than parsing docstrings.  Stable
backends (currently only :mod:`mechdsl.codegen.taichi_printer`) do **not**
set this flag.

At runtime, each experimental printer emits one
:class:`ExperimentalBackendWarning` per Python session on the first call to
its public ``emit`` function.  The warning is filterable with the standard
:mod:`warnings` machinery::

    import warnings
    warnings.filterwarnings("ignore", category=ExperimentalBackendWarning)
"""

from __future__ import annotations

import warnings

__all__ = ["ExperimentalBackendWarning", "warn_experimental_backend_once"]


class ExperimentalBackendWarning(UserWarning):
    """Warning raised on the first call to an experimental codegen backend.

    Experimental backends (MFEM, MOOSE) are preserved in-tree but are not
    part of the MVP stable contract.  This warning signals that the caller
    is using a surface outside the stable Taichi compile path.

    Filter with::

        import warnings
        warnings.filterwarnings("ignore", category=ExperimentalBackendWarning)
    """


def warn_experimental_backend_once(state: dict, backend_name: str) -> None:
    """Emit an ExperimentalBackendWarning the first time this is called for the given state.

    Idempotent: subsequent calls with the same state dict are no-ops.

    Parameters
    ----------
    state : dict
        Module-level dict tracking warning state. Caller passes a single shared
        dict (e.g. ``_warn_state``); this function flips ``state["warned"]`` to True.
    backend_name : str
        Human-readable backend name (e.g. "MFEM", "MOOSE") for the warning message.
    """
    if state.get("warned"):
        return
    warnings.warn(
        f"{backend_name} backend is experimental — its API may change without "
        f"deprecation notice. Suppress with "
        f"warnings.filterwarnings('ignore', category=ExperimentalBackendWarning).",
        ExperimentalBackendWarning,
        stacklevel=3,
    )
    state["warned"] = True
