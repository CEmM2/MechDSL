"""JIT-run proof of the spectral (Ogden) LaTeX-to-code constitutive slice (#288).

Exercises the two backend capabilities added in ``codegen/spectral_emitter.py``:

1. the symmetric 3x3 Jacobi eigensolver ``sym_eig_3x3`` -- verified against
   ``numpy.linalg.eigh`` on a battery of spectra including repeated and
   near-degenerate eigenvalues (where closed-form Cardano eigenvectors break);
2. the emitted spectral ``constitutive_update``, which eigendecomposes
   ``C = F^T F``, evaluates the LaTeX-derived principal PK2 stresses
   ``S_i(lambda)`` and reassembles ``S = sum_i S_i N_i (x) N_i`` -- matched to
   the :class:`SpectralEnergyModel` NumPy oracle (which uses the same symbolic
   principal stresses), closing LaTeX Psi -> generated Taichi -> correct numbers.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import numpy as np
import pytest

from mechdsl.codegen.spectral_emitter import (
    SYM_EIG_3X3_SOURCE,
    emit_spectral_constitutive_func,
    spectral_param_names,
)
from mechdsl.symbolic.spectral_energy import derive_from_spectral_energy

if TYPE_CHECKING:
    from pathlib import Path

# Two-term compressible Ogden, the committed example energy (dev/examples/ogden_energy.tex).
_OGDEN_ENERGY = r"""
% declare metric gDD --dim 3
% declare EDD --dim 3
% declare \mu \alpha \nu \eta \kappa --const
\Psi = \frac{\mu}{\alpha}\left(\mathrm{lbar1}^{\alpha} + \mathrm{lbar2}^{\alpha} + \mathrm{lbar3}^{\alpha} - 3\right) + \frac{\nu}{\eta}\left(\mathrm{lbar1}^{\eta} + \mathrm{lbar2}^{\eta} + \mathrm{lbar3}^{\eta} - 3\right) + \frac{\kappa}{2}\left(\mathrm{Jdet} - 1\right)^{2}
"""

# Rubber-like two-term Ogden parameters, keyed by sanitised symbol name.
_PARAMS = {"mu": 80.0, "alpha": 1.3, "nu": 20.0, "eta": -2.0, "kappa": 1000.0}


def test_emitted_spectral_source_is_structurally_sound():
    """Fast (no JIT): the eigensolver + constitutive sources have the expected
    shape -- a sym_eig_3x3 call, one principal stress per stretch, and a
    projector reassembly term per eigenvector."""
    assert "@ti.func" in SYM_EIG_3X3_SOURCE
    assert "def sym_eig_3x3(A):" in SYM_EIG_3X3_SOURCE

    model = derive_from_spectral_energy(_OGDEN_ENERGY)
    src = emit_spectral_constitutive_func(model, param_names=spectral_param_names(model))
    # param_symbols are sorted by name: alpha, eta, kappa, mu, nu.
    assert "def constitutive_update(F, alpha, eta, kappa, mu, nu):" in src
    assert "sym_eig_3x3(C)" in src
    for i in range(3):
        assert f"sprin{i} =" in src
        assert f"n{i} = ti.Vector(" in src
        assert f"S += sprin{i} * n{i}.outer_product(n{i})" in src


def _build_eig_module(path: Path) -> None:
    """Self-contained Taichi module: the eigensolver @ti.func + a kernel that
    runs it on a scalar matrix field. Written to a real file so Taichi's source
    introspection can find the kernel."""
    src = (
        "import taichi as ti\n\n"
        "A_in = ti.Matrix.field(3, 3, ti.f64, shape=())\n"
        "EV_out = ti.Matrix.field(3, 4, ti.f64, shape=())\n\n"
        f"{SYM_EIG_3X3_SOURCE}\n"
        "@ti.kernel\n"
        "def run():\n"
        "    EV_out[None] = sym_eig_3x3(A_in[None])\n"
    )
    path.write_text(src)


def _eig_cases(rng: np.random.Generator) -> list[np.ndarray]:
    """A battery of symmetric matrices: random SPD, exactly-repeated,
    fully-degenerate, near-degenerate, and a rotated repeated block."""
    cases: list[np.ndarray] = []
    for _ in range(8):  # well-separated random SPD
        m = rng.standard_normal((3, 3))
        cases.append(m @ m.T + 3.0 * np.eye(3))
    cases.append(np.diag([2.0, 2.0, 5.0]))  # two equal (diagonal)
    cases.append(4.0 * np.eye(3))  # fully degenerate
    cases.append(np.diag([1.0, 1.0 + 1e-9, 3.0]))  # near-degenerate
    q, _ = np.linalg.qr(rng.standard_normal((3, 3)))
    cases.append(q @ np.diag([2.0, 2.0, 7.0]) @ q.T)  # repeated block, non-diagonal
    return cases


@pytest.mark.slow
def test_jacobi_eigensolver_matches_numpy(tmp_path):
    """JIT-compile sym_eig_3x3 and verify eigenvalues, orthonormality, and
    spectral reconstruction against numpy on the full battery (order/sign-safe
    invariants, since Jacobi and eigh need not agree on ordering or sign)."""
    ti = pytest.importorskip("taichi")
    ti.init(arch=ti.cpu, default_fp=ti.f64)

    module_path = tmp_path / "generated_eig.py"
    _build_eig_module(module_path)
    spec = importlib.util.spec_from_file_location("generated_eig", module_path)
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    i3 = np.eye(3)
    for a in _eig_cases(np.random.default_rng(20260617)):
        a = 0.5 * (a + a.T)
        gen.A_in[None] = a.tolist()
        gen.run()
        ev = gen.EV_out[None].to_numpy()
        vecs, vals = ev[:, 0:3], ev[:, 3]

        assert np.allclose(np.sort(vals), np.sort(np.linalg.eigvalsh(a)), atol=1e-10, rtol=1e-10)
        assert np.allclose(vecs.T @ vecs, i3, atol=1e-10), "eigenvectors must be orthonormal"
        recon = vecs @ np.diag(vals) @ vecs.T
        assert np.allclose(recon, a, atol=1e-9), "V diag(e) V^T must reconstruct A"


def _build_ogden_module(model, path: Path) -> None:
    """Self-contained Taichi module: eigensolver + emitted spectral
    constitutive_update + an argpack-parameterised kernel that runs it."""
    names = spectral_param_names(model)
    func_src = emit_spectral_constitutive_func(model, param_names=names)
    pack_fields = ", ".join(f"{n}=ti.f64" for n in names)
    forward = ", ".join(f"params.{n}" for n in names)
    src = (
        "import taichi as ti\n\n"
        f"ParamPack = ti.types.argpack({pack_fields})\n"
        "F_in = ti.Matrix.field(3, 3, ti.f64, shape=())\n"
        "S_out = ti.Matrix.field(3, 3, ti.f64, shape=())\n\n"
        f"{SYM_EIG_3X3_SOURCE}\n"
        f"{func_src}\n"
        "@ti.kernel\n"
        "def run(params: ParamPack):\n"
        f"    S_out[None] = constitutive_update(F_in[None], {forward})\n"
    )
    path.write_text(src)


@pytest.mark.slow
def test_emitted_ogden_matches_spectral_oracle(tmp_path):
    """JIT-compile the emitted Ogden constitutive func and match the derived
    SpectralEnergyModel oracle at random deformation gradients."""
    ti = pytest.importorskip("taichi")
    ti.init(arch=ti.cpu, default_fp=ti.f64)

    model = derive_from_spectral_energy(_OGDEN_ENERGY)
    module_path = tmp_path / "generated_ogden.py"
    _build_ogden_module(model, module_path)
    spec = importlib.util.spec_from_file_location("generated_ogden", module_path)
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    params = gen.ParamPack(**_PARAMS)
    rng = np.random.default_rng(20260617)
    for _ in range(10):
        f = np.eye(3) + 0.05 * rng.standard_normal((3, 3))
        gen.F_in[None] = f.tolist()
        gen.run(params)
        s_gen = gen.S_out[None].to_numpy()

        e_strain = 0.5 * (f.T @ f - np.eye(3))
        s_oracle = model.pk2_stress(e_strain, _PARAMS)
        assert np.allclose(s_gen, s_oracle, atol=1e-8, rtol=1e-8)
