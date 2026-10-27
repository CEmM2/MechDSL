"""The bundled algorithm sources are package data readable by name."""

from __future__ import annotations

from importlib import resources

import pytest

from algo2code.library import (
    ALGORITHM_SOURCES,
    algorithm_source,
    algorithm_source_path,
)
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
from algo2code.library.radial_return_j2_kinematic import RADIAL_RETURN_J2_KINEMATIC_LATEX
from algo2code.library.radial_return_j2_mixed import RADIAL_RETURN_J2_MIXED_LATEX


@pytest.mark.parametrize("name", ALGORITHM_SOURCES)
def test_every_listed_source_loads(name: str) -> None:
    text = algorithm_source(name)
    assert text.strip(), f"{name} is empty"
    assert "\\begin{algorithmic}" in text, f"{name} does not look like algpseudocode"
    assert algorithm_source_path(name).is_file()


def test_listed_sources_match_bundled_files() -> None:
    bundled = sorted(
        entry.name
        for entry in resources.files("algo2code.library").joinpath("algorithms").iterdir()
        if entry.name.endswith(".tex")
    )
    assert bundled == sorted(ALGORITHM_SOURCES)


def test_module_constants_are_the_bundled_text() -> None:
    assert algorithm_source("radial_return_j2.tex") == RADIAL_RETURN_J2_LATEX
    assert algorithm_source("radial_return_j2_kinematic.tex") == RADIAL_RETURN_J2_KINEMATIC_LATEX
    assert algorithm_source("radial_return_j2_mixed.tex") == RADIAL_RETURN_J2_MIXED_LATEX


def test_unknown_source_is_an_actionable_error() -> None:
    with pytest.raises(FileNotFoundError, match=r"no bundled algorithm source named 'nope.tex'"):
        algorithm_source("nope.tex")
    with pytest.raises(FileNotFoundError, match=r"Available sources: .*pcg\.tex"):
        algorithm_source("nope.tex")
