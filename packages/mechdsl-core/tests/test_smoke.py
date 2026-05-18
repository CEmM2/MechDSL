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
    import mechdsl

    assert mechdsl.__version__ == "0.1.0"


@pytest.mark.parametrize("pkg", SUBPACKAGES)
def test_subpackage_import(pkg: str):
    """Each subpackage should be importable."""
    importlib.import_module(pkg)
