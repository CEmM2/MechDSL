"""JIT-run proof of the anisotropic (HGO) LaTeX-to-code constitutive slice (#288).

Exercises the second backend capability added in ``codegen/anisotropic_emitter.py``:
emission of a fiber-reinforced ``constitutive_update(F, a, *params)`` that

1. takes a per-element fiber direction ``a`` as an argument (the field-gather
   the straight-line emitter could not express -- today's signature is
   ``(F, scalar_params...)`` with no field/vector args); and
2. adds the fiber stress through a **data-dependent branch** gated by the
   Macaulay bracket ``<Ibar4 - 1>`` (active only in tension, ``Ibar4 > 1``).

The emitted func is matched to the :class:`AnisotropicEnergyModel` NumPy oracle
across fiber-tension, fiber-compression, and random deformations -- so both
sides of the gate are verified, closing LaTeX Psi -> generated Taichi ->
correct numbers for HGO.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import numpy as np
import pytest

from mechdsl.codegen.anisotropic_emitter import (
    anisotropic_param_names,
    emit_anisotropic_constitutive_func,
)
from mechdsl.symbolic.anisotropic_energy import derive_from_anisotropic_energy

if TYPE_CHECKING:
    from pathlib import Path

# Single-family HGO, the committed example energy (dev/examples/hgo_energy.tex).
_HGO_ENERGY = r"""
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \mu \kappa --const
\Psi = \frac{\mu}{2} (\mathrm{Ibar1} - 3) + \frac{\kappa}{2} (\mathrm{Jdet} - 1)^{2} + \frac{\mathrm{k1}}{2 \mathrm{k2}} (\exp{\mathrm{k2} (\mathrm{Ibar4} - 1)^{2}} - 1)
"""

_PARAMS = {"mu": 100.0, "kappa": 1000.0, "k1": 50.0, "k2": 5.0}
# Non-unit fiber direction (exercises the in-emitter normalisation), aligned with x.
_FIBER = np.array([2.0, 0.0, 0.0], dtype=np.float64)


def test_emitted_anisotropic_source_is_structurally_sound():
    """Fast (no JIT): the emitted func has the fiber-vector argument, a tension
    gate, the always-on isotropic stress, and the conditional fiber add."""
    model = derive_from_anisotropic_energy(_HGO_ENERGY)
    src = emit_anisotropic_constitutive_func(model, param_names=anisotropic_param_names(model))
    # param names sorted: k1, k2, kappa, mu.
    assert "def constitutive_update(F, a, k1, k2, kappa, mu):" in src
    assert "ibar4 =" in src
    assert "if ibar4 > 1.0:" in src
    assert "S[0, 0] =" in src  # always-on isotropic assignment
    assert "S[0, 0] +=" in src  # conditional fiber contribution


def _build_hgo_module(model, path: Path) -> None:
    """Self-contained Taichi module: emitted HGO constitutive_update + an
    argpack-parameterised kernel that forwards a fiber-direction vector field."""
    names = anisotropic_param_names(model)
    func_src = emit_anisotropic_constitutive_func(model, param_names=names)
    pack_fields = ", ".join(f"{n}=ti.f64" for n in names)
    forward = ", ".join(f"params.{n}" for n in names)
    src = (
        "import taichi as ti\n\n"
        f"ParamPack = ti.types.argpack({pack_fields})\n"
        "F_in = ti.Matrix.field(3, 3, ti.f64, shape=())\n"
        "a_in = ti.Vector.field(3, ti.f64, shape=())\n"
        "S_out = ti.Matrix.field(3, 3, ti.f64, shape=())\n\n"
        f"{func_src}\n"
        "@ti.kernel\n"
        "def run(params: ParamPack):\n"
        f"    S_out[None] = constitutive_update(F_in[None], a_in[None], {forward})\n"
    )
    path.write_text(src)


@pytest.mark.slow
def test_emitted_hgo_matches_anisotropic_oracle(tmp_path):
    """JIT-compile the emitted HGO constitutive func and match the derived
    AnisotropicEnergyModel oracle across fiber tension (gate open), fiber
    compression (gate closed), and random deformations."""
    ti = pytest.importorskip("taichi")
    ti.init(arch=ti.cpu, default_fp=ti.f64)

    model = derive_from_anisotropic_energy(_HGO_ENERGY)
    module_path = tmp_path / "generated_hgo.py"
    _build_hgo_module(model, module_path)
    spec = importlib.util.spec_from_file_location("generated_hgo", module_path)
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    params = gen.ParamPack(**_PARAMS)
    gen.a_in[None] = _FIBER.tolist()

    deformations = [
        np.diag([1.25, 0.95, 0.95]),  # stretch along fiber -> Ibar4 > 1 (active)
        np.diag([0.85, 1.05, 1.05]),  # contraction along fiber -> Ibar4 < 1 (inactive)
    ]
    rng = np.random.default_rng(20260617)
    deformations += [np.eye(3) + 0.05 * rng.standard_normal((3, 3)) for _ in range(8)]

    # Sanity: the chosen explicit cases really do span both sides of the gate.
    gates = []
    for f in deformations[:2]:
        e_strain = 0.5 * (f.T @ f - np.eye(3))
        a_unit = _FIBER / np.linalg.norm(_FIBER)
        gates.append(
            float(model._ibar4_fn(*[e_strain[i, j] for i in range(3) for j in range(3)], *a_unit))
        )
    assert gates[0] > 1.0 and gates[1] < 1.0, f"test cases must straddle the gate, got {gates}"

    for f in deformations:
        gen.F_in[None] = f.tolist()
        gen.run(params)
        s_gen = gen.S_out[None].to_numpy()

        e_strain = 0.5 * (f.T @ f - np.eye(3))
        s_oracle = model.pk2_stress(e_strain, (_FIBER,), _PARAMS)
        assert np.allclose(s_gen, s_oracle, atol=1e-8, rtol=1e-8)
