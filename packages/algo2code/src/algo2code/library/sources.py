"""Access to the canonical algorithm sources bundled with ``algo2code``.

The ``.tex`` files under ``algo2code/library/algorithms/`` are the single
source of truth for every algorithm the library exposes (and for the solver
seams in ``mechdsl-core`` that transpile them at runtime).  They ship as
package data inside the wheel, so an installed ``algo2code`` can read them
without a source checkout — nothing here depends on the repository layout.

Runtime invariant
-----------------

This module imports **only stdlib**.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

#: Names of every bundled algorithm source, as accepted by :func:`algorithm_source`.
ALGORITHM_SOURCES: tuple[str, ...] = (
    "jacobi.tex",
    "newmark.tex",
    "pcg.tex",
    "radial_return_j2.tex",
    "radial_return_j2_kinematic.tex",
    "radial_return_j2_mixed.tex",
)


def _algorithms_dir() -> Traversable:
    return resources.files("algo2code.library").joinpath("algorithms")


def _resource(name: str) -> Traversable:
    resource = _algorithms_dir().joinpath(name)
    if not resource.is_file():
        try:
            available = sorted(
                p.name for p in _algorithms_dir().iterdir() if p.name.endswith(".tex")
            )
        except (FileNotFoundError, NotADirectoryError):
            available = []
        raise FileNotFoundError(
            f"algo2code has no bundled algorithm source named {name!r} "
            f"(expected it under algo2code/library/algorithms/). "
            f"Available sources: {', '.join(available) or 'none'}. "
            "If this is an installed package, the installation is missing its "
            "package data — reinstall algo2code."
        )
    return resource


def algorithm_source(name: str) -> str:
    """Return the verbatim LaTeX text of the bundled algorithm source ``name``.

    Parameters
    ----------
    name:
        File name of the source, e.g. ``"pcg.tex"``.  See
        :data:`ALGORITHM_SOURCES` for the full list.

    Raises
    ------
    FileNotFoundError
        If no bundled source of that name exists.
    """
    return _resource(name).read_text(encoding="utf-8")


def algorithm_source_path(name: str) -> Path:
    """Return the on-disk path of the bundled algorithm source ``name``.

    Installed wheels are unpacked, so the resource is a regular file and the
    returned path can be read directly.  Prefer :func:`algorithm_source` when
    only the text is needed; this accessor exists for callers that want to
    show *where* the canonical source lives.
    """
    return Path(str(_resource(name)))


__all__ = [
    "ALGORITHM_SOURCES",
    "algorithm_source",
    "algorithm_source_path",
]
