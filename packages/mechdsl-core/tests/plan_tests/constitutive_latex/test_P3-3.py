"""Tests for Task P3-3: E2E Neo-Hookean through the production pipeline + JIT verify.

This is the GATE that unblocks Phases 4 & 5. It proves a LaTeX-authored
Neo-Hookean strain energy flows through the *real* production codegen path

    ProblemIR(derived_energy=...)
        -> localise_and_optimize
        -> ArtifactBundle.from_pipeline
        -> taichi_printer.emit_constitutive_update

and that the JIT-compiled ``constitutive_update`` @ti.func reproduces the
hand-coded oracle ``models/neo_hookean.py`` (``pk2_stress``) to < 1e-8 at N
random well-conditioned deformation gradients.

Acceptance criteria:
- AC-1: LaTeX NH compiles through the real pipeline to Taichi matching
  neo_hookean.py < 1e-8 (stress).
- AC-2: Existing SVK/J2/Lemaitre emission and golden tests still pass.
- AC-3: Generated constitutive @ti.func ≤ 512 lines (JIT budget).
- AC-4: JIT-run (@pytest.mark.slow) passes with the generated kernel.

Scope reality (layer A vs layer B). The production emission path
(``ProblemIR.derived_energy`` carrier -> bundle channel -> emitter) was wired
by P3-1; this task proves it end-to-end with a JIT-run match. The
``compile_latex`` *façade* producer (auto-deriving ``derived_energy`` from an
energy block authored inside a ``% mechanics`` problem) is a separate frontend
feature (energy-block capture in ``parse_compile_context``) and is documented
as remaining wiring — see the module docstring of this file and the task report.

Implementation pattern: mirrors test_energy_codegen_svk.py
- The constitutive @ti.func is taken from the PRODUCTION emission
  (``emit_constitutive_update``), not the isolated ``energy_emitter``.
- Material parameters are passed via ``ti.types.argpack`` (cached across calls,
  per the established slice convention — NOT 0-d fields).
- The generated module is written to a real file so Taichi's source
  introspection can find the kernel, then imported with importlib.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.einsum_optimizer import MAX_LINES_TI_FUNC
from mechdsl.codegen.energy_emitter import emit_tangent_func
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    emit,
    emit_constitutive_update,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize
from mechdsl.symbolic.energy import EnergyModel, derive_from_energy
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
    material_tangent_voigt,
    pk2_stress,
)

_EXAMPLES_DIR = Path(__file__).resolve().parents[5] / "dev" / "examples"
_NH_TEX = _EXAMPLES_DIR / "neo_hookean_energy.tex"

# Material parameters (must match across all comparisons). mu = shear modulus,
# kappa = bulk modulus — both well inside the > 0 validity domain.
_MU = 80.0
_KAPPA = 160.0

# Number of random deformation gradients sampled in the numeric comparisons.
_N_SAMPLES = 15


@pytest.fixture(scope="module")
def neo_hookean_energy() -> EnergyModel:
    """Derive the Neo-Hookean EnergyModel once for the module (nrpylatex+sympy)."""
    return derive_from_energy(_NH_TEX.read_text())


def _param_names(model: EnergyModel) -> list[str]:
    """Sorted derived parameter names (everything in the PK2 stress that is not
    a strain component). For Neo-Hookean this is ``['kappa', 'mu']`` — note this
    differs from SVK's ``(F, aleph, mu)``."""
    return sorted(s.name for s in model.pk2.free_symbols if not s.name.startswith("EDD"))


def _make_nh_ir(derived_energy: EnergyModel) -> ProblemIR:
    """Build the production ProblemIR carrying the derived Neo-Hookean energy."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="neo_hookean", params={"mu": _MU, "kappa": _KAPPA}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
        derived_energy=derived_energy,
    )


def _emit_constitutive_block(model: EnergyModel) -> str:
    """Emit the constitutive ``@ti.func`` block through the REAL pipeline:
    ProblemIR.derived_energy -> localise_and_optimize -> ArtifactBundle ->
    emit_constitutive_update. This is the production surface P3-3 gates, NOT a
    direct call into the isolated energy_emitter."""
    ir = _make_nh_ir(model)
    loc_result, plans = localise_and_optimize(ir)
    bundle = ArtifactBundle.from_pipeline(ir, loc_result, plans)
    ctx = EmissionContext()
    emit_constitutive_update(ctx, bundle)
    return ctx.get_source()


def _extract_ti_func(block: str) -> list[str]:
    """Return the lines of the emitted ``constitutive_update`` @ti.func, from the
    ``@ti.func`` decorator through the closing ``return S`` — the unrolled body
    that the Taichi JIT budget counts."""
    lines = block.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "@ti.func")
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "return S")
    return lines[start : end + 1]


def _build_runner_module(model: EnergyModel, block: str, path: Path) -> str:
    """Compose a self-contained Taichi module around the PRODUCTION-emitted
    constitutive @ti.func: an argpack of the material parameters (cached across
    calls per the Taichi argpack contract) and a kernel that forwards them.

    The @ti.func is lifted verbatim from the production ``emit_constitutive_update``
    output, so this exercises the real emitted source — not a re-emission. Written
    to a real file so Taichi's source introspection can find the kernel.
    """
    func_lines = _extract_ti_func(block)
    func_src = "\n".join(func_lines)
    names = _param_names(model)
    pack_fields = ", ".join(f"{n}=ti.f64" for n in names)
    forward = ", ".join(f"params.{n}" for n in names)
    src = (
        "import math\n"
        "import taichi as ti\n\n"
        f"ParamPack = ti.types.argpack({pack_fields})\n"
        "F_in = ti.Matrix.field(3, 3, ti.f64, shape=())\n"
        "S_out = ti.Matrix.field(3, 3, ti.f64, shape=())\n\n"
        f"{func_src}\n\n"
        "@ti.kernel\n"
        "def run(params: ParamPack):\n"
        f"    S_out[None] = constitutive_update(F_in[None], {forward})\n"
    )
    path.write_text(src)
    return src


def _extract_tangent_ti_func(block: str) -> list[str]:
    """Return the lines of the emitted ``tangent_update`` @ti.func, from the
    ``@ti.func`` decorator through the closing ``return D`` — the unrolled body
    the Taichi JIT budget counts for the 6x6 Voigt tangent."""
    lines = block.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "@ti.func")
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "return D")
    return lines[start : end + 1]


def _build_tangent_runner_module(model: EnergyModel, block: str, path: Path) -> str:
    """Compose a self-contained Taichi module around the emitted tangent
    @ti.func: an argpack of the material parameters and a kernel that forwards
    them, returning the 6x6 Voigt tangent. Mirrors :func:`_build_runner_module`.

    The tangent @ti.func is lifted verbatim from ``emit_tangent_func``, so this
    exercises the real emitted source. Written to a real file so Taichi's source
    introspection can find the kernel.
    """
    func_lines = _extract_tangent_ti_func(block)
    func_src = "\n".join(func_lines)
    names = _param_names(model)
    pack_fields = ", ".join(f"{n}=ti.f64" for n in names)
    forward = ", ".join(f"params.{n}" for n in names)
    src = (
        "import math\n"
        "import taichi as ti\n\n"
        f"ParamPack = ti.types.argpack({pack_fields})\n"
        "F_in = ti.Matrix.field(3, 3, ti.f64, shape=())\n"
        "D_out = ti.Matrix.field(6, 6, ti.f64, shape=())\n\n"
        f"{func_src}\n\n"
        "@ti.kernel\n"
        "def run_tangent(params: ParamPack):\n"
        f"    D_out[None] = tangent_update(F_in[None], {forward})\n"
    )
    path.write_text(src)
    return src


class TestTaskP3_3:
    """Tests for Task P3-3: E2E Neo-Hookean through the real pipeline + JIT verify.
    AC covered: 1, 2, 3, 4."""

    # ------------------------------------------------------------------
    # math.* -> ti.* rewrite: known calls/constants translate, unknown fails loud
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_to_taichi_math_translates_calls_and_constants(self):
        """pycode math.* tokens rewrite to Taichi; unknown math.* fails loudly.

        Guards the single translation point Phase 4/5 energies rely on: known
        functions (sqrt) and constants (pi, e) map to their Taichi forms
        (ti.pi does NOT exist — the constants live under ti.math), and an
        unregistered math.* raises rather than emitting non-compiling source.
        """
        from mechdsl.codegen.energy_emitter import _to_taichi_math

        assert _to_taichi_math("math.sqrt(math.pi * x)") == "ti.sqrt(ti.math.pi * x)"
        assert _to_taichi_math("math.e") == "ti.math.e"
        # Overlapping names must not collide (math.tan vs math.tanh).
        assert _to_taichi_math("math.tanh(math.tan(x))") == "ti.tanh(ti.tan(x))"
        with pytest.raises(NotImplementedError, match=r"math\.gamma"):
            _to_taichi_math("math.gamma(x)")

    # ------------------------------------------------------------------
    # AC-1a: Emitted source is structurally sound (fast check, no JIT)
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_emitted_neo_hookean_source_is_structurally_sound(
        self, neo_hookean_energy: EnergyModel
    ):
        """Verifies: The derived Neo-Hookean energy emits valid Taichi source
        through the production pipeline.
        AC: AC-1 (compiles to Taichi).
        Passes when: emitted block carries the derived banner, the derived
        signature ``(F, kappa, mu)``, one assignment per stress component, and
        no leftover host ``math.`` call (Taichi rejects those inside @ti.func)."""
        block = _emit_constitutive_block(neo_hookean_energy)

        # Routed through the derived branch, not the named-model SVK/J2 switch.
        assert "derived from LaTeX energy" in block
        assert "@ti.func" in block
        # Derived signature differs from SVK's (F, aleph, mu).
        assert "def constitutive_update(F, kappa, mu):" in block
        # One assignment per stress component.
        for i in range(3):
            for j in range(3):
                assert f"S[{i}, {j}] =" in block
        # The volumetric (Jdet) term emits a square root: it must be the Taichi
        # intrinsic, never the host math.sqrt that crashes the JIT.
        assert "ti.sqrt" in block
        assert "math.sqrt" not in block

    # ------------------------------------------------------------------
    # AC-1b: Symbolic derivation matches oracle at random F (fast, no JIT)
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_generated_neo_hookean_func_matches_oracle_fast(self, neo_hookean_energy: EnergyModel):
        """Verifies: Symbolic derivation of Neo-Hookean from LaTeX matches the
        oracle without paying the JIT cost.
        AC: AC-1 (< 1e-8 stress match).
        Passes when: lambdified derived PK2 stress agrees with neo_hookean.py
        ``pk2_stress`` at N random F to < 1e-8."""
        import sympy as sp

        model = neo_hookean_energy
        strain = model.strain_symbols
        params = sorted(
            (s for s in model.pk2.free_symbols if not s.name.startswith("EDD")),
            key=lambda s: s.name,
        )
        flat_strain = [strain[i][j] for i in range(3) for j in range(3)]
        pk2_fn = sp.lambdify((*flat_strain, *params), model.pk2, "numpy")

        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        param_vals = {"kappa": _KAPPA, "mu": _MU}
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = 0.5 * (F.T @ F - np.eye(3))
            S_derived = np.array(
                pk2_fn(
                    *(E[i, j] for i in range(3) for j in range(3)),
                    *(param_vals[p.name] for p in params),
                ),
                dtype=np.float64,
            )
            S_oracle = pk2_stress(mat, E)
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(S_derived - S_oracle)) / scale))
        assert max_rel < 1e-8, f"derived vs oracle max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-3: Emitted constitutive @ti.func respects the JIT budget (≤ 512 lines)
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_emitted_constitutive_func_within_jit_budget(self, neo_hookean_energy: EnergyModel):
        """Verifies: The generated constitutive @ti.func stays within the
        512-line JIT budget (07-CONVENTIONS §9).
        AC: AC-3 (≤ 512 lines).
        Passes when: the unrolled @ti.func (decorator..return S) is ≤
        MAX_LINES_TI_FUNC lines.

        Note: the production derived branch emits only the PK2-stress
        ``constitutive_update`` (no tangent @ti.func yet — derived-tangent
        emission is Phase 4/5 wiring), so the budget assertion targets the
        emitted stress func, which is the @ti.func the JIT compiles today."""
        block = _emit_constitutive_block(neo_hookean_energy)
        func_lines = _extract_ti_func(block)
        assert len(func_lines) <= MAX_LINES_TI_FUNC, (
            f"emitted constitutive @ti.func has {len(func_lines)} lines, "
            f"exceeding the {MAX_LINES_TI_FUNC}-line JIT budget"
        )

    # ------------------------------------------------------------------
    # AC-4: JIT-run against oracle (slow, requires Taichi) — the gate
    # ------------------------------------------------------------------

    @pytest.mark.slow
    def test_generated_neo_hookean_kernel_jit_matches_oracle(
        self, neo_hookean_energy: EnergyModel, tmp_path
    ):
        """Verifies: the PRODUCTION-emitted Neo-Hookean constitutive @ti.func
        JIT-compiles and reproduces the oracle at random F.
        AC: AC-1 (< 1e-8) + AC-4 (JIT-run passes).

        This is the gate: the @ti.func is taken from the real pipeline
        (``emit_constitutive_update`` off an ``ArtifactBundle.from_pipeline``),
        wrapped in an argpack runner, JIT-compiled, and matched against
        ``models/neo_hookean.py`` ``pk2_stress`` to < 1e-8."""
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        block = _emit_constitutive_block(neo_hookean_energy)
        module_path = tmp_path / "generated_nh.py"
        _build_runner_module(neo_hookean_energy, block, module_path)

        spec = importlib.util.spec_from_file_location("generated_nh", module_path)
        assert spec and spec.loader
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)

        params = gen.ParamPack(kappa=_KAPPA, mu=_MU)
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            gen.F_in[None] = F.tolist()
            gen.run(params)
            S_generated = gen.S_out[None].to_numpy()

            E = 0.5 * (F.T @ F - np.eye(3))
            S_oracle = pk2_stress(mat, E)
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(S_generated - S_oracle)) / scale))
            assert np.allclose(S_generated, S_oracle, atol=1e-8, rtol=1e-10)
        assert max_rel < 1e-8, f"JIT NH vs oracle max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-5a: Emitted tangent @ti.func is structurally sound + within budget
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_emitted_tangent_source_is_sound_and_within_budget(
        self, neo_hookean_energy: EnergyModel
    ):
        """Verifies: the derived Neo-Hookean tangent emits a valid 6x6 Voigt
        @ti.func that stays within the 512-line JIT budget.
        AC: tangent emission (6x6 Voigt) + ≤ MAX_LINES_TI_FUNC.
        Passes when: emitted block carries the derived signature ``(F, kappa,
        mu)``, one assignment per Voigt entry (6x6 = 36), the volumetric
        ``ti.sqrt`` (never host ``math.sqrt``), and the unrolled @ti.func is ≤
        the budget."""
        block = emit_tangent_func(neo_hookean_energy)

        assert "@ti.func" in block
        assert "def tangent_update(F, kappa, mu):" in block
        assert "D = ti.Matrix.zero(ti.f64, 6, 6)" in block
        # One assignment per Voigt tangent entry (full 6x6, not just upper tri).
        for a in range(6):
            for b in range(6):
                assert f"D[{a}, {b}] =" in block
        assert "return D" in block
        # Volumetric term carries a square root: must be the Taichi intrinsic.
        assert "ti.sqrt" in block
        assert "math.sqrt" not in block

        func_lines = _extract_tangent_ti_func(block)
        assert len(func_lines) <= MAX_LINES_TI_FUNC, (
            f"emitted tangent @ti.func has {len(func_lines)} lines, "
            f"exceeding the {MAX_LINES_TI_FUNC}-line JIT budget"
        )

    # ------------------------------------------------------------------
    # AC-5b: Derived tangent matches oracle 6x6 Voigt at random F (fast, no JIT)
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_tangent_matches_oracle_voigt_fast(self, neo_hookean_energy: EnergyModel):
        """Verifies: the symbolic rank-4 tangent derived from LaTeX, reduced to
        6x6 Voigt the SAME way as the oracle (``tangent_to_voigt_66``), matches
        ``neo_hookean.py`` ``material_tangent_voigt`` without paying the JIT cost.
        AC: derived C_IJKL matches oracle < 1e-8 (compared in Voigt 6x6).
        Passes when: lambdified derived tangent agrees with the oracle 6x6 Voigt
        at N random F to < 1e-8."""
        import sympy as sp

        from mechdsl.symbolic.voigt import tangent_to_voigt_66

        model = neo_hookean_energy
        strain = model.strain_symbols
        params = sorted(
            {
                s
                for i in range(3)
                for j in range(3)
                for k in range(3)
                for el in range(3)
                for s in model.tangent[i, j, k, el].free_symbols
                if not s.name.startswith("EDD")
            },
            key=lambda s: s.name,
        )
        flat_strain = [strain[i][j] for i in range(3) for j in range(3)]
        # Lambdify the full rank-4 tangent; sympy returns a nested list -> array.
        tan_fn = sp.lambdify((*flat_strain, *params), model.tangent.tolist(), "numpy")

        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        param_vals = {"kappa": _KAPPA, "mu": _MU}
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = 0.5 * (F.T @ F - np.eye(3))
            C4_derived = np.array(
                tan_fn(
                    *(E[i, j] for i in range(3) for j in range(3)),
                    *(param_vals[p.name] for p in params),
                ),
                dtype=np.float64,
            )
            D_derived = tangent_to_voigt_66(C4_derived)
            D_oracle = material_tangent_voigt(mat, E)
            scale = max(1.0, float(np.max(np.abs(D_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(D_derived - D_oracle)) / scale))
        assert max_rel < 1e-8, f"derived vs oracle tangent max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-5c: JIT-run tangent against oracle (slow, requires Taichi)
    # ------------------------------------------------------------------

    @pytest.mark.slow
    def test_generated_tangent_kernel_jit_matches_oracle(
        self, neo_hookean_energy: EnergyModel, tmp_path
    ):
        """Verifies: the emitted Neo-Hookean tangent @ti.func JIT-compiles and
        reproduces the oracle 6x6 Voigt tangent at random F.
        AC: derived tangent < 1e-8 (JIT-run) + ≤ 512-line budget.

        The @ti.func is taken from ``emit_tangent_func`` off the real-pipeline
        ``EnergyModel`` (``derive_from_energy(neo_hookean_energy.tex)``), wrapped
        in the same argpack runner pattern as the stress JIT test, JIT-compiled,
        and matched against ``neo_hookean.py`` ``material_tangent_voigt`` at the
        SAME N random F used by the stress test (identical seed/sampling)."""
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        block = emit_tangent_func(neo_hookean_energy)
        # Budget assertion on the @ti.func the JIT actually compiles.
        assert len(_extract_tangent_ti_func(block)) <= MAX_LINES_TI_FUNC

        module_path = tmp_path / "generated_nh_tangent.py"
        _build_tangent_runner_module(neo_hookean_energy, block, module_path)

        spec = importlib.util.spec_from_file_location("generated_nh_tangent", module_path)
        assert spec and spec.loader
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)

        params = gen.ParamPack(kappa=_KAPPA, mu=_MU)
        mat = NeoHookeanMaterial(mu=_MU, kappa=_KAPPA)
        # SAME seed and sampling as the stress JIT test -> identical F sequence.
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            gen.F_in[None] = F.tolist()
            gen.run_tangent(params)
            D_generated = gen.D_out[None].to_numpy()

            E = 0.5 * (F.T @ F - np.eye(3))
            D_oracle = material_tangent_voigt(mat, E)
            scale = max(1.0, float(np.max(np.abs(D_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(D_generated - D_oracle)) / scale))
            assert np.allclose(D_generated, D_oracle, atol=1e-8, rtol=1e-10)
        assert max_rel < 1e-8, f"JIT NH tangent vs oracle max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-2: Existing named-model emission unchanged (SVK / J2 / Lemaitre)
    # ------------------------------------------------------------------

    @staticmethod
    def _emit_named(material: MaterialSpec) -> str:
        ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=material,
            boundaries=(
                BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
                BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
            ),
        )
        loc_result, plans = localise_and_optimize(ir)
        bundle = ArtifactBundle.from_pipeline(ir, loc_result, plans)
        return emit(bundle)

    @pytest.mark.integration
    def test_existing_svk_emission_still_passes(self):
        """Verifies: SVK named-model emission is unchanged (no derived energy ->
        hand-coded closed form, no ti.sqrt rewrite touches it).
        AC: AC-2 (SVK/J2/Lemaitre golden tests still pass)."""
        source = self._emit_named(MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}))
        assert "def constitutive_update(" in source
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in source
        assert "derived from LaTeX energy" not in source

    @pytest.mark.integration
    def test_existing_j2_emission_still_passes(self):
        """Verifies: J2 power-law plasticity emission unchanged.
        AC: AC-2 (SVK/J2/Lemaitre golden tests still pass)."""
        source = self._emit_named(
            MaterialSpec(
                model="j2_power_law",
                params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 100.0, "n": 0.2},
            )
        )
        assert "def constitutive_update_plastic(" in source
        assert "derived from LaTeX energy" not in source

    @pytest.mark.integration
    def test_existing_lemaitre_emission_still_passes(self):
        """Verifies: Lemaitre viscoplasticity (J2 + damage) emission unchanged.
        AC: AC-2 (SVK/J2/Lemaitre golden tests still pass)."""
        source = self._emit_named(
            MaterialSpec(
                model="lemaitre",
                params={
                    "E": 200e3,
                    "nu": 0.3,
                    "sigma_y0": 250.0,
                    "K": 100.0,
                    "n": 0.2,
                    "S": 1.0,
                    "s": 1.0,
                    "D_crit": 0.5,
                },
            )
        )
        assert "def constitutive_update_plastic(" in source
        assert "derived from LaTeX energy" not in source
