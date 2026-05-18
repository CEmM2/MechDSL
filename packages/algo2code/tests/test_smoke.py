"""Smoke tests — verify the package structure imports correctly."""

import importlib

import pytest

SUBPACKAGES = [
    "algo2code",
    "algo2code.backends",
]


def test_version():
    import algo2code

    assert algo2code.__version__ == "0.1.0"


@pytest.mark.parametrize("pkg", SUBPACKAGES)
def test_subpackage_import(pkg: str):
    """Each subpackage should be importable."""
    importlib.import_module(pkg)


def test_public_api_exports():
    """The documented API symbols must be importable."""
    from algo2code import (
        Algorithm,
        VarType,
        generate_taichi,
        infer_types,
        parse_algorithm,
        parse_latex_expr,
        transpile,
    )

    assert callable(transpile)
    assert callable(parse_algorithm)
    assert callable(parse_latex_expr)
    assert callable(infer_types)
    assert callable(generate_taichi)
    assert Algorithm is not None
    assert VarType is not None
