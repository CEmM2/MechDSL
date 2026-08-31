"""Smoke tests — verify the package structure imports correctly."""

import importlib

import pytest

SUBPACKAGES = [
    "mechdsl.frontend",
    "mechdsl.symbolic",
    "mechdsl.symbolic.models",
    "mechdsl.ir",
    "mechdsl.lowering",
    "mechdsl.codegen",
    "mechdsl.solver",
    "mechdsl.lib",
    "mechdsl.verify",
]


def test_version():
    # Compare against the installed distribution metadata instead of a
    # hardcoded literal, so version bumps can't break this test while
    # __init__.__version__ <-> pyproject drift still fails it.
    from importlib.metadata import version

    import mechdsl

    assert mechdsl.__version__ == version("mechdsl-core")


@pytest.mark.parametrize("pkg", SUBPACKAGES)
def test_subpackage_import(pkg: str):
    """Each subpackage should be importable."""
    importlib.import_module(pkg)
