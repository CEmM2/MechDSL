"""End-to-end proof of the LaTeX-to-code constitutive slice for SVK.

Authors SVK as a LaTeX strain energy, derives the symbolic PK2 stress
(symbolic/energy.py), emits a Taichi @ti.func (codegen/energy_emitter.py),
JIT-compiles and runs it, and asserts the generated function reproduces the
hand-coded svk.py oracle at random deformation gradients. This is the closing
link: LaTeX Psi -> generated code -> correct numbers.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from mechdsl.codegen.energy_emitter import emit_constitutive_func
from mechdsl.symbolic.energy import derive_from_energy
from mechdsl.symbolic.models.svk import SVKMaterial, pk2_stress

_LAM = 115384.6153846154  # E=200e3, nu=0.3
_MU = 76923.07692307692

_SVK_ENERGY = r"""
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \lambda \mu --const
\Psi = \frac{\lambda}{2} E^{I}_{I} E^{J}_{J} + \mu E^{I J} E_{I J}
"""


def test_emitted_source_is_structurally_sound():
    """Fast check (no JIT): the emitted func has the expected signature and
    one assignment per stress component."""
    model = derive_from_energy(_SVK_ENERGY)
    src = emit_constitutive_func(model)
    assert "@ti.func" in src
    assert "def constitutive_update(F, aleph, mu):" in src
    for i in range(3):
        for j in range(3):
            assert f"S[{i}, {j}] =" in src


def _param_names(model) -> list[str]:
    return sorted(s.name for s in model.pk2.free_symbols if not s.name.startswith("EDD"))


def _build_runner_module(model, path: Path) -> str:
    """Compose a self-contained Taichi module: the derived constitutive
    @ti.func, an argpack of the material parameters (cached across calls per
    the Taichi argpack contract), and a kernel that forwards them. Written to
    a real file so Taichi's source introspection can find the kernel."""
    names = _param_names(model)
    func_src = emit_constitutive_func(model)
    pack_fields = ", ".join(f"{n}=ti.f64" for n in names)
    forward = ", ".join(f"params.{n}" for n in names)
    src = (
        "import taichi as ti\n\n"
        f"ParamPack = ti.types.argpack({pack_fields})\n"
        "F_in = ti.Matrix.field(3, 3, ti.f64, shape=())\n"
        "S_out = ti.Matrix.field(3, 3, ti.f64, shape=())\n\n"
        f"{func_src}\n"
        "@ti.kernel\n"
        "def run(params: ParamPack):\n"
        f"    S_out[None] = constitutive_update(F_in[None], {forward})\n"
    )
    path.write_text(src)
    return src


@pytest.mark.slow
def test_generated_svk_func_matches_oracle(tmp_path):
    """JIT-compile the generated SVK stress func and match svk.py at random F.

    Material parameters are passed via a ``ti.types.argpack`` (Taichi caches
    unchanged kernel parameters across calls)."""
    ti = pytest.importorskip("taichi")
    ti.init(arch=ti.cpu, default_fp=ti.f64)

    model = derive_from_energy(_SVK_ENERGY)
    module_path = tmp_path / "generated_svk.py"
    _build_runner_module(model, module_path)

    spec = importlib.util.spec_from_file_location("generated_svk", module_path)
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    params = gen.ParamPack(aleph=_LAM, mu=_MU)
    mat = SVKMaterial(lam=_LAM, mu=_MU)
    rng = np.random.default_rng(20260603)
    for _ in range(10):
        F = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
        gen.F_in[None] = F.tolist()
        gen.run(params)
        S_generated = gen.S_out[None].to_numpy()

        E = 0.5 * (F.T @ F - np.eye(3))
        S_oracle = pk2_stress(mat, E)
        assert np.allclose(S_generated, S_oracle, atol=1e-8, rtol=1e-10)


def test_example_tex_file_round_trips():
    """The committed dev/examples/svk_energy.tex compiles through the slice."""
    tex = Path(__file__).resolve().parents[3] / "dev" / "examples" / "svk_energy.tex"
    model = derive_from_energy(tex.read_text())
    assert {orig for orig in model.parameters.values()} == {"lambda"}
    src = emit_constitutive_func(model)
    assert "constitutive_update" in src
