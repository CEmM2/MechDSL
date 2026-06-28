"""Tests for Task P4-1: Mooney-Rivlin through the wired pipeline + NH reduction.

A LaTeX-authored Mooney-Rivlin strain energy

    Psi = C1(Ibar1 - 3) + C2(Ibar2 - 3) + (kappa/2)(Jdet - 1)^2

flows through the *real* production codegen path

    ProblemIR(derived_energy=...)
        -> localise_and_optimize
        -> ArtifactBundle.from_pipeline
        -> taichi_printer.emit_constitutive_update

and the derived PK2 stress / rank-4 tangent reproduce the hand-coded oracle
``models/mooney_rivlin.py`` to < 1e-8 at N random deformation gradients.

Authoring (see ``dev/examples/mooney_rivlin_energy.tex``): the three named
invariants ``Ibar1``, ``Ibar2``, ``Jdet`` are all already registered in
``symbolic/energy.py`` (``Ibar2`` added in P2-1), so P4-1 is pure repetition
of the proven P3-3 Neo-Hookean path — no engine change. The Mooney
coefficients are authored as greek tokens (nrpylatex scans only known
commands): ``\\alpha == C1``, ``\\beta == C2`` (sanitised to ``aleph``,
mirroring SVK's ``\\lambda -> aleph``), ``\\kappa == bulk``.

Acceptance criteria:
- AC-1: Mooney-Rivlin matches mooney_rivlin.py < 1e-8 (stress); tangent within
  documented method tolerance (here exact, < 1e-8).
- AC-2: Reduces to Neo-Hookean (mu = 2*C1) when C2 = 0.
- AC-3: AD oracle + tangent symmetry pass.

Implementation pattern mirrors test_P3-3.py: the JIT test lifts the constitutive
``@ti.func`` verbatim from the PRODUCTION emission (``emit_constitutive_update``
off an ``ArtifactBundle.from_pipeline``), wraps it in an argpack runner written
to a real file, JIT-compiles, and matches the oracle.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import sympy as sp

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.einsum_optimizer import MAX_LINES_TI_FUNC
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
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
from mechdsl.symbolic.models.mooney_rivlin import (
    MooneyRivlinMaterial,
    material_tangent_voigt,
    pk2_stress,
)
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
)
from mechdsl.symbolic.models.neo_hookean import (
    pk2_stress as nh_pk2_stress,
)
from mechdsl.symbolic.voigt import tangent_to_voigt_66

_EXAMPLES_DIR = Path(__file__).resolve().parents[5] / "dev" / "examples"
_MR_TEX = _EXAMPLES_DIR / "mooney_rivlin_energy.tex"

# Material parameters (must match across every comparison). C1, C2 are the
# Mooney coefficients (authored as alpha, beta); kappa the bulk modulus.
_C1 = 0.6
_C2 = 0.2
_KAPPA = 50.0

_N_SAMPLES = 15


@pytest.fixture(scope="module")
def mooney_rivlin_energy() -> EnergyModel:
    """Derive the Mooney-Rivlin EnergyModel once (nrpylatex + sympy)."""
    return derive_from_energy(_MR_TEX.read_text())


def _sorted_params(model: EnergyModel) -> list[sp.Symbol]:
    """Derived parameter symbols (free symbols of the PK2 stress that are not
    strain components), sorted by sanitised name — the SAME order the emitter
    uses for the ``constitutive_update`` signature."""
    return sorted(
        (s for s in model.pk2.free_symbols if not s.name.startswith("EDD")),
        key=lambda s: s.name,
    )


def _value_by_sanitised(model: EnergyModel, *, c2: float = _C2) -> dict[str, float]:
    """Map each sanitised parameter name to its numeric value, resolving the
    sanitised->original-LaTeX rename (``aleph`` -> ``beta`` == C2). ``c2`` is a
    knob so the C2=0 reduction test can zero the second coefficient."""
    by_original = {"alpha": _C1, "beta": c2, "kappa": _KAPPA}
    out: dict[str, float] = {}
    for sym in _sorted_params(model):
        original = model.parameters.get(sym, sym.name)
        out[sym.name] = by_original[original]
    return out


def _lambdified_stress(model: EnergyModel):
    params = _sorted_params(model)
    strain = model.strain_symbols
    flat = [strain[i][j] for i in range(3) for j in range(3)]
    return sp.lambdify((*flat, *params), model.pk2, "numpy"), params


def _lambdified_tangent(model: EnergyModel):
    params = _sorted_params(model)
    strain = model.strain_symbols
    flat = [strain[i][j] for i in range(3) for j in range(3)]
    return sp.lambdify((*flat, *params), model.tangent.tolist(), "numpy"), params


def _emit_constitutive_block(model: EnergyModel) -> str:
    """Emit the constitutive ``@ti.func`` through the REAL pipeline:
    ProblemIR.derived_energy -> localise_and_optimize -> ArtifactBundle ->
    emit_constitutive_update (the production surface P4-1 proves, not a direct
    call into the isolated energy_emitter)."""
    ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="mooney_rivlin", params={"alpha": _C1, "beta": _C2, "kappa": _KAPPA}
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
        derived_energy=model,
    )
    loc_result, plans = localise_and_optimize(ir)
    bundle = ArtifactBundle.from_pipeline(ir, loc_result, plans)
    ctx = EmissionContext()
    emit_constitutive_update(ctx, bundle)
    return ctx.get_source()


def _extract_ti_func(block: str) -> list[str]:
    lines = block.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "@ti.func")
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "return S")
    return lines[start : end + 1]


def _build_runner_module(model: EnergyModel, block: str, path: Path) -> str:
    """Compose a self-contained Taichi module around the PRODUCTION-emitted
    constitutive @ti.func, mirroring test_P3-3.py. Params pass via an argpack
    in the same sorted order as the emitted signature."""
    func_src = "\n".join(_extract_ti_func(block))
    names = [s.name for s in _sorted_params(model)]
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


class TestTaskP4_1:
    """Tests for Task P4-1: Mooney-Rivlin derive/emit/diff + NH reduction.
    AC covered: 1, 2, 3."""

    # ------------------------------------------------------------------
    # AC-1a: Emitted source is structurally sound (fast, no JIT)
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_emitted_mooney_rivlin_source_is_structurally_sound(
        self, mooney_rivlin_energy: EnergyModel
    ):
        """Verifies: the derived Mooney-Rivlin energy emits valid Taichi source
        through the production pipeline.
        AC: AC-1 (compiles to Taichi).
        Passes when: the block carries the derived banner, a constitutive
        signature, one assignment per stress component, the volumetric
        ``ti.sqrt`` (never host ``math.sqrt``), and stays within the JIT budget."""
        block = _emit_constitutive_block(mooney_rivlin_energy)

        assert "derived from LaTeX energy" in block
        assert "@ti.func" in block
        # Pin the exact derived signature (sorted sanitised param names; beta is
        # sanitised to aleph) so a wrong param name/order is caught structurally.
        names = ", ".join(s.name for s in _sorted_params(mooney_rivlin_energy))
        assert f"def constitutive_update(F, {names}):" in block
        for i in range(3):
            for j in range(3):
                assert f"S[{i}, {j}] =" in block
        assert "ti.sqrt" in block
        assert "math.sqrt" not in block
        assert len(_extract_ti_func(block)) <= MAX_LINES_TI_FUNC

    # ------------------------------------------------------------------
    # AC-1b: Symbolic stress matches oracle at random F (fast, no JIT)
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_mooney_rivlin_matches_oracle_stress(self, mooney_rivlin_energy: EnergyModel):
        """Verifies: symbolic PK2 stress derived from LaTeX matches the oracle.
        AC: AC-1 (< 1e-8 stress).
        Passes when: lambdified derived stress agrees with mooney_rivlin.py
        ``pk2_stress`` at N random F to < 1e-8."""
        model = mooney_rivlin_energy
        pk2_fn, params = _lambdified_stress(model)
        vals = _value_by_sanitised(model)
        pvals = [vals[p.name] for p in params]

        mat = MooneyRivlinMaterial(C1=_C1, C2=_C2, kappa=_KAPPA)
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = 0.5 * (F.T @ F - np.eye(3))
            args = [E[i, j] for i in range(3) for j in range(3)]
            S_derived = np.array(pk2_fn(*args, *pvals), dtype=np.float64)
            S_oracle = pk2_stress(mat, E)
            scale = max(1.0, float(np.max(np.abs(S_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(S_derived - S_oracle)) / scale))
        assert max_rel < 1e-8, f"derived vs oracle stress max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-2: C2 = 0 reduces to Neo-Hookean (mu = 2*C1)
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_c2_zero_reduces_to_neo_hookean(self, mooney_rivlin_energy: EnergyModel):
        """Verifies: Mooney-Rivlin with C2 = 0 reduces to compressible
        Neo-Hookean with mu = 2*C1 (same volumetric term, kappa shared).
        AC: AC-2.
        Passes when: derived stress with C2 = 0 equals neo_hookean.py
        ``pk2_stress`` (mu = 2*C1) at N random F to < 1e-8."""
        model = mooney_rivlin_energy
        pk2_fn, params = _lambdified_stress(model)
        vals0 = _value_by_sanitised(model, c2=0.0)
        pvals0 = [vals0[p.name] for p in params]

        nh = NeoHookeanMaterial(mu=2.0 * _C1, kappa=_KAPPA)
        rng = np.random.default_rng(424242)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = 0.5 * (F.T @ F - np.eye(3))
            args = [E[i, j] for i in range(3) for j in range(3)]
            S_derived = np.array(pk2_fn(*args, *pvals0), dtype=np.float64)
            S_nh = nh_pk2_stress(nh, E)
            scale = max(1.0, float(np.max(np.abs(S_nh))))
            max_rel = max(max_rel, float(np.max(np.abs(S_derived - S_nh)) / scale))
        assert max_rel < 1e-8, f"C2=0 vs Neo-Hookean max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-3: Derived rank-4 tangent matches oracle (Voigt) + symmetry
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_derived_tangent_matches_oracle_and_is_symmetric(
        self, mooney_rivlin_energy: EnergyModel
    ):
        """Verifies: the symbolic rank-4 tangent derived from LaTeX, reduced to
        6x6 Voigt the SAME way as the oracle (``tangent_to_voigt_66``), matches
        ``mooney_rivlin.py`` ``material_tangent_voigt`` and is minor-/major-
        symmetric.
        AC: AC-3 (AD oracle + tangent symmetry).
        Passes when: derived tangent matches the oracle 6x6 Voigt < 1e-8 and the
        rank-4 tangent satisfies minor (IJ, KL) and major (IJKL=KLIJ) symmetry."""
        model = mooney_rivlin_energy
        tan_fn, params = _lambdified_tangent(model)
        vals = _value_by_sanitised(model)
        pvals = [vals[p.name] for p in params]

        mat = MooneyRivlinMaterial(C1=_C1, C2=_C2, kappa=_KAPPA)
        rng = np.random.default_rng(20260604)
        max_rel = 0.0
        for _ in range(_N_SAMPLES):
            F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
            E = 0.5 * (F.T @ F - np.eye(3))
            args = [E[i, j] for i in range(3) for j in range(3)]
            C4 = np.array(tan_fn(*args, *pvals), dtype=np.float64)

            # Minor symmetry: C_IJKL == C_JIKL == C_IJLK.
            assert np.allclose(C4, C4.transpose(1, 0, 2, 3), atol=1e-10)
            assert np.allclose(C4, C4.transpose(0, 1, 3, 2), atol=1e-10)
            # Major symmetry: C_IJKL == C_KLIJ.
            assert np.allclose(C4, C4.transpose(2, 3, 0, 1), atol=1e-10)

            D_derived = tangent_to_voigt_66(C4)
            D_oracle = material_tangent_voigt(mat, E)
            scale = max(1.0, float(np.max(np.abs(D_oracle))))
            max_rel = max(max_rel, float(np.max(np.abs(D_derived - D_oracle)) / scale))
        assert max_rel < 1e-8, f"derived vs oracle tangent max rel-err {max_rel:.3e} >= 1e-8"

    # ------------------------------------------------------------------
    # AC-1c: JIT-run the production-emitted kernel against the oracle (slow)
    # ------------------------------------------------------------------

    @pytest.mark.slow
    def test_generated_mooney_rivlin_kernel_jit_matches_oracle(
        self, mooney_rivlin_energy: EnergyModel, tmp_path
    ):
        """Verifies: the PRODUCTION-emitted Mooney-Rivlin constitutive @ti.func
        JIT-compiles and reproduces the oracle at random F.
        AC: AC-1 (< 1e-8) + JIT-run.
        The @ti.func is taken from the real pipeline (``emit_constitutive_update``
        off an ``ArtifactBundle.from_pipeline``), wrapped in an argpack runner,
        JIT-compiled, and matched against ``models/mooney_rivlin.py`` ``pk2_stress``."""
        ti = pytest.importorskip("taichi")
        ti.init(arch=ti.cpu, default_fp=ti.f64)

        model = mooney_rivlin_energy
        block = _emit_constitutive_block(model)
        module_path = tmp_path / "generated_mr.py"
        _build_runner_module(model, block, module_path)

        spec = importlib.util.spec_from_file_location("generated_mr", module_path)
        assert spec and spec.loader
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)

        vals = _value_by_sanitised(model)
        params = gen.ParamPack(**vals)
        mat = MooneyRivlinMaterial(C1=_C1, C2=_C2, kappa=_KAPPA)
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
        assert max_rel < 1e-8, f"JIT MR vs oracle max rel-err {max_rel:.3e} >= 1e-8"
