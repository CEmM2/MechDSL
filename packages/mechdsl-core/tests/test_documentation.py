"""Tests for Sprint 3 Phase 5 documentation, examples, and roadmap guidance."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

from mechdsl.codegen import compile as compile_api
from mechdsl.codegen.taichi_printer import emit
from mechdsl.frontend import build_context
from mechdsl.ir.element_ir import ElementIR
from mechdsl.ir.mechanics_ir import ProblemIR
from mechdsl.solver.newton import newton_solve

_ROOT = Path(__file__).resolve().parents[3]
_README = _ROOT / "README.md"
_CHANGELOG = _ROOT / "CHANGELOG.md"
_EXAMPLES = _ROOT / "dev" / "examples"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _example_path(name: str) -> Path:
    return _EXAMPLES / f"{name}.py"


def _example_source(name: str) -> str:
    return _read_text(_example_path(name))


def _run_example(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "python", f"dev/examples/{name}.py"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_docstring_sections(obj: object, *sections: str) -> str:
    doc = inspect.getdoc(obj)
    assert doc is not None
    for section in sections:
        assert section in doc
    return doc


class TestTaskP5T1:
    """Tests for Task P5-1: Update README with installation, quickstart, architecture."""

    def test_readme_has_installation_section(self):
        """
        Verifies: README documents the supported installation workflow.
        Acceptance criterion: README has installation section.
        Passes when: README contains a clear installation section using uv.
        """
        text = _read_text(_README)
        assert "## Installation" in text
        assert "git clone https://github.com/SOSOVSKI/MechDSL.git" in text
        assert "uv sync" in text

    def test_readme_has_quickstart_section(self):
        """
        Verifies: README includes a quickstart guide for the public API.
        Acceptance criterion: README has quickstart section.
        Passes when: README shows a minimal build_context/compile workflow.
        """
        text = _read_text(_README)
        assert "## Quickstart" in text
        assert "build_context(" in text
        assert "compile(" in text
        assert "ProblemIR" in text

    def test_readme_has_architecture_overview_and_design_doc_links(self):
        """
        Verifies: README explains the compiler architecture and links to design docs.
        Acceptance criterion: README has architecture overview.
        Passes when: architecture summary and design-doc references are present.
        """
        text = _read_text(_README)
        assert "## Architecture" in text
        assert "Layer 1  Frontend" in text
        assert "Layer 6  Codegen" in text
        assert "dev/design_docs/00-OVERVIEW.md" in text
        assert "dev/design_docs/PLAN-B.md" in text


class TestTaskP5T2:
    """Tests for Task P5-2: Create 5 example Python scripts."""

    def test_elastic_cantilever_script_exists(self):
        """
        Verifies: dev/examples/elastic_cantilever.py exists.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: the elastic cantilever example file is present.
        """
        assert _example_path("elastic_cantilever").exists()

    def test_elastic_cantilever_script_uses_programmatic_api(self):
        """
        Verifies: elastic_cantilever example uses build_context() and compile().
        Acceptance criterion: each demonstrates the programmatic API.
        Passes when: the script constructs a problem and calls compile().
        """
        source = _example_source("elastic_cantilever")
        assert "build_context(" in source
        assert "ProblemIR(" in source
        assert "compile(" in source

    def test_elastic_cantilever_script_runs(self):
        """
        Verifies: elastic_cantilever example runs without error.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: uv run python dev/examples/elastic_cantilever.py exits successfully.
        """
        result = _run_example("elastic_cantilever")
        assert result.returncode == 0, result.stderr
        assert "Compilation summary" in result.stdout

    def test_plastic_uniaxial_script_exists(self):
        """
        Verifies: dev/examples/plastic_uniaxial.py exists.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: the plastic uniaxial example file is present.
        """
        assert _example_path("plastic_uniaxial").exists()

    def test_plastic_uniaxial_script_uses_programmatic_api(self):
        """
        Verifies: plastic_uniaxial example uses build_context() and compile().
        Acceptance criterion: each demonstrates the programmatic API.
        Passes when: the script constructs a problem and calls compile().
        """
        source = _example_source("plastic_uniaxial")
        assert "build_context(" in source
        assert "ProblemIR(" in source
        assert "compile(" in source

    def test_plastic_uniaxial_script_runs(self):
        """
        Verifies: plastic_uniaxial example runs without error.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: uv run python dev/examples/plastic_uniaxial.py exits successfully.
        """
        result = _run_example("plastic_uniaxial")
        assert result.returncode == 0, result.stderr
        assert "Compilation summary" in result.stdout

    def test_cook_membrane_script_exists(self):
        """
        Verifies: dev/examples/cook_membrane.py exists.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: the Cook's membrane example file is present.
        """
        assert _example_path("cook_membrane").exists()

    def test_cook_membrane_script_uses_programmatic_api(self):
        """
        Verifies: cook_membrane example uses build_context() and compile().
        Acceptance criterion: each demonstrates the programmatic API.
        Passes when: the script constructs a problem and calls compile().
        """
        source = _example_source("cook_membrane")
        assert "build_context(" in source
        assert "ProblemIR(" in source
        assert "compile(" in source

    def test_cook_membrane_script_runs(self):
        """
        Verifies: cook_membrane example runs without error.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: uv run python dev/examples/cook_membrane.py exits successfully.
        """
        result = _run_example("cook_membrane")
        assert result.returncode == 0, result.stderr
        assert "Compilation summary" in result.stdout

    def test_necking_bar_script_exists(self):
        """
        Verifies: dev/examples/necking_bar.py exists.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: the necking bar example file is present.
        """
        assert _example_path("necking_bar").exists()

    def test_necking_bar_script_uses_programmatic_api(self):
        """
        Verifies: necking_bar example uses build_context() and compile().
        Acceptance criterion: each demonstrates the programmatic API.
        Passes when: the script constructs a problem and calls compile().
        """
        source = _example_source("necking_bar")
        assert "build_context(" in source
        assert "ProblemIR(" in source
        assert "compile(" in source

    def test_necking_bar_script_runs(self):
        """
        Verifies: necking_bar example runs without error.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: uv run python dev/examples/necking_bar.py exits successfully.
        """
        result = _run_example("necking_bar")
        assert result.returncode == 0, result.stderr
        assert "Compilation summary" in result.stdout

    def test_patch_test_script_exists(self):
        """
        Verifies: dev/examples/patch_test.py exists.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: the patch_test example file is present.
        """
        assert _example_path("patch_test").exists()

    def test_patch_test_script_uses_programmatic_api(self):
        """
        Verifies: patch_test example uses build_context() and compile().
        Acceptance criterion: each demonstrates the programmatic API.
        Passes when: the script constructs a problem and calls compile().
        """
        source = _example_source("patch_test")
        assert "build_context(" in source
        assert "ProblemIR(" in source
        assert "compile(" in source

    def test_patch_test_script_runs(self):
        """
        Verifies: patch_test example runs without error.
        Acceptance criterion: all 5 scripts runnable with uv run python.
        Passes when: uv run python dev/examples/patch_test.py exits successfully.
        """
        result = _run_example("patch_test")
        assert result.returncode == 0, result.stderr
        assert "Compilation summary" in result.stdout


class TestTaskP5T3:
    """Tests for Task P5-3: Add docstrings to public API functions."""

    def test_compile_public_api_has_numpy_style_docstring(self):
        """
        Verifies: compile() has a complete numpy-style docstring.
        Acceptance criterion: public API parameters, returns, and exceptions are documented.
        Passes when: compile() docstring includes parameter and return sections.
        """
        doc = _assert_docstring_sections(compile_api, "Parameters", "Returns", "Raises")
        assert "ArtifactBundle" in doc

    def test_build_context_public_api_has_numpy_style_docstring(self):
        """
        Verifies: build_context() has a complete numpy-style docstring.
        Acceptance criterion: public API parameters, returns, and exceptions are documented.
        Passes when: build_context() docstring includes parameter, return, and raises sections.
        """
        doc = _assert_docstring_sections(build_context, "Parameters", "Returns", "Raises")
        assert "coord_system" in doc

    def test_problem_ir_and_element_ir_have_public_docstrings(self):
        """
        Verifies: ProblemIR and ElementIR public types are documented.
        Acceptance criterion: public API parameters, returns, and exceptions are documented.
        Passes when: the public IR types describe their construction contract and semantics.
        """
        problem_doc = _assert_docstring_sections(ProblemIR, "Parameters", "Raises")
        element_doc = _assert_docstring_sections(ElementIR, "Parameters", "Raises")
        assert "declared_regions" in problem_doc
        assert "quadrature" in element_doc

    def test_emit_public_api_has_numpy_style_docstring(self):
        """
        Verifies: emit() has a complete numpy-style docstring.
        Acceptance criterion: public API parameters, returns, and exceptions are documented.
        Passes when: emit() docstring covers parameters and return value.
        """
        doc = _assert_docstring_sections(emit, "Parameters", "Returns", "Raises")
        assert "ArtifactBundle" in doc

    def test_newton_solve_public_api_has_numpy_style_docstring(self):
        """
        Verifies: newton_solve() has a complete numpy-style docstring.
        Acceptance criterion: public API parameters, returns, and exceptions are documented.
        Passes when: newton_solve() docstring documents solver inputs, outputs, and failure modes.
        """
        doc = _assert_docstring_sections(newton_solve, "Parameters", "Returns", "Raises")
        assert "linear_solver" in doc


class TestTaskP5T4:
    """Tests for Task P5-4: Update CHANGELOG for MVP release."""

    def test_changelog_has_mvp_release_entry(self):
        """
        Verifies: CHANGELOG contains an MVP release entry.
        Acceptance criterion: CHANGELOG lists all MVP features.
        Passes when: the release entry summarizes the supported MVP scope.
        """
        text = _read_text(_CHANGELOG)
        assert "## [0.1.0] - 2026-04-12" in text
        assert "3D Hex8 Total Lagrangian" in text
        assert "SVK elasticity and J2 power-law plasticity" in text
        assert "deterministic source emission" in text
        assert "patch test, rigid body, cantilever, Cook's membrane, necking bar" in text


class TestTaskP5T5:
    """Tests for Task P5-5: Review UnsupportedError messages reference Plan B phases."""

    def test_plan_b_phase_references_are_correct_across_target_files(self):
        """
        Verifies: UnsupportedError and related user-facing guard messages point to the right Plan B phase.
        Acceptance criterion: every UnsupportedError message names the correct Plan B phase.
        Passes when: frontend, mechanics_ir, and lowering messages all match the intended roadmap phase.

        Plan B §B1.3 promoted Updated Lagrangian from rejected to supported, so the
        literal string "Plan B phase B1" is no longer expected in the rejection surface
        of these files. The Plan B §B1.3 docstring on Configuration pins the concept
        instead. Plan B §B3 (viscoplasticity) and §B4 (advanced hyperelasticity) are
        now done too, so mechanics_ir and fe_localise no longer name them in the
        unknown-material message — only "B6 (damage)" remains. The frontend still
        preserves the full B3/B4/B6 roadmap message because its material allowlist
        enumerates every supported family explicitly; the phase markers there act
        as forward references for users who haven't followed the Plan B cadence.
        """
        frontend = _read_text(_ROOT / "packages/mechdsl-core/src/mechdsl/frontend/__init__.py")
        mechanics_ir = _read_text(_ROOT / "packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py")
        localise = _read_text(_ROOT / "packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py")

        # Frontend still rejects non-MVP dim, non-MVP cell type, non-MVP materials.
        assert "Plan B phase B2" in frontend
        assert "Plan B phase B5" in frontend
        assert "B3 (viscoplasticity), B4 (advanced hyperelasticity), and B6 (damage)." in frontend
        # mechanics_ir.py: subset guards for dim and cell type remain; B1.3 docstring
        # pins the Configuration concept to Plan B phase B1. After P4-5, the
        # hyperelastic families are in the allowlist, so the unknown-material
        # message is scoped to "B6 (damage)" only.
        assert "Plan B phase B2" in mechanics_ir
        assert "Plan B §B1.3" in mechanics_ir
        assert "Plan B phase B5" in mechanics_ir
        assert "B6 (damage)" in mechanics_ir
        # fe_localise still rejects Tet4/Tet10 and unknown materials; B1.3 threading
        # is documented alongside. Same B3/B4 promotion applies.
        assert "Plan B §B1.3" in localise
        assert "Plan B phase B5" in localise
        assert "B6 (damage)" in localise
