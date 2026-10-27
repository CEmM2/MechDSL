"""Wheel-install regression: every non-Taichi module must import from a clean venv.

Builds the ``mechdsl-core`` and ``algo2code`` wheels from this checkout, installs
them (and only them — no ``[verify]`` extra, no source tree on ``sys.path``) into a
fresh virtual environment, and imports every module of both packages there.

This guards the packaging contract that runtime resources ship inside the wheel:
an earlier release located the canonical algorithm ``.tex`` sources by walking up
from ``__file__`` to a repository-only directory, so ``mechdsl.lib.plasticity*``
and ``algo2code.library.radial_return_j2*`` raised ``FileNotFoundError`` at
import time for anyone installing from PyPI.

Modules whose only failure is a missing ``taichi`` / ``ti_runtime`` (the
``[verify]`` extra) are expected skips; any other exception is a failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ("mechdsl-core", "algo2code")
TOP_LEVEL_MODULES = ("mechdsl", "algo2code")
BUNDLED_TEX = (
    "jacobi.tex",
    "newmark.tex",
    "pcg.tex",
    "radial_return_j2.tex",
    "radial_return_j2_kinematic.tex",
    "radial_return_j2_mixed.tex",
)

# Runs inside the clean venv. Enumerates modules from the installed package
# directory (rather than ``pkgutil.walk_packages``) so a broken ``__init__`` in
# one subpackage cannot hide its siblings.
_IMPORT_WALK = textwrap.dedent(
    """
    import importlib
    import sys
    from pathlib import Path

    EXPECTED_MISSING = {"taichi", "ti_runtime"}

    def enumerate_modules(pkg_name):
        pkg = importlib.import_module(pkg_name)
        root = Path(pkg.__file__).parent
        for py in sorted(root.rglob("*.py")):
            parts = list(py.relative_to(root).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            yield ".".join([pkg_name, *parts])

    failures = []
    skipped = []
    imported = []
    for top in sys.argv[1:]:
        for mod in enumerate_modules(top):
            try:
                importlib.import_module(mod)
                imported.append(mod)
            except ModuleNotFoundError as exc:
                root = (exc.name or "").split(".")[0]
                if root in EXPECTED_MISSING:
                    skipped.append(f"{mod} (missing {exc.name})")
                else:
                    failures.append(f"{mod}: {type(exc).__name__}: {exc}")
            except Exception as exc:  # noqa: BLE001 - report everything
                failures.append(f"{mod}: {type(exc).__name__}: {exc}")

    # The J2 return-map sources must be readable from the installed wheel.
    from algo2code.library import ALGORITHM_SOURCES, algorithm_source
    from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
    from algo2code.library.radial_return_j2_kinematic import RADIAL_RETURN_J2_KINEMATIC_LATEX
    from algo2code.library.radial_return_j2_mixed import RADIAL_RETURN_J2_MIXED_LATEX

    for name, text in {
        "RADIAL_RETURN_J2_LATEX": RADIAL_RETURN_J2_LATEX,
        "RADIAL_RETURN_J2_KINEMATIC_LATEX": RADIAL_RETURN_J2_KINEMATIC_LATEX,
        "RADIAL_RETURN_J2_MIXED_LATEX": RADIAL_RETURN_J2_MIXED_LATEX,
        **{n: algorithm_source(n) for n in ALGORITHM_SOURCES},
    }.items():
        if not text.strip():
            failures.append(f"{name} is empty")

    print(f"imported={len(imported)} skipped={len(skipped)} failed={len(failures)}")
    for line in skipped:
        print("SKIP", line)
    for line in failures:
        print("FAIL", line)
    sys.exit(1 if failures else 0)
    """
)


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)  # type: ignore[call-overload]


@pytest.fixture(scope="module")
def built_wheels(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH; the wheel-install regression needs it to build and install")
    dist = tmp_path_factory.mktemp("dist")
    wheels: dict[str, Path] = {}
    for pkg in PACKAGES:
        _run([uv, "build", "--wheel", "--out-dir", str(dist)], cwd=REPO_ROOT / "packages" / pkg)
        matches = sorted(dist.glob(f"{pkg.replace('-', '_')}-*.whl"))
        assert len(matches) == 1, f"expected exactly one {pkg} wheel, found {matches}"
        wheels[pkg] = matches[0]
    return wheels


@pytest.mark.integration
def test_algorithm_sources_are_wheel_package_data(built_wheels: dict[str, Path]) -> None:
    """The canonical ``.tex`` sources must be inside the algo2code wheel."""
    with zipfile.ZipFile(built_wheels["algo2code"]) as whl:
        names = set(whl.namelist())
    missing = [t for t in BUNDLED_TEX if f"algo2code/library/algorithms/{t}" not in names]
    assert not missing, f"algo2code wheel is missing bundled algorithm sources: {missing}"


@pytest.mark.integration
def test_every_non_taichi_module_imports_from_clean_venv(
    built_wheels: dict[str, Path], tmp_path: Path
) -> None:
    uv = shutil.which("uv")
    assert uv is not None  # the fixture skipped otherwise
    venv = tmp_path / "venv"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    _run([uv, "venv", "--python", py_version, str(venv)])
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert python.exists(), f"venv interpreter not found at {python}"

    # Only the two wheels and their declared dependencies — no [verify] extra.
    _run([uv, "pip", "install", "--python", str(python), *map(str, built_wheels.values())])

    script = tmp_path / "import_walk.py"
    script.write_text(_IMPORT_WALK, encoding="utf-8")
    # ``-I`` (isolated) plus a cwd outside the repo: nothing from the source
    # checkout can leak onto sys.path, so only the installed wheels are exercised.
    proc = subprocess.run(
        [str(python), "-I", str(script), *TOP_LEVEL_MODULES],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"import walk over installed wheels failed:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "FAIL" not in proc.stdout, proc.stdout
