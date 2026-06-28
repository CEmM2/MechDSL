# Constitutive models

MechDSL ships a catalog of constitutive models under
`mechdsl.symbolic.models` (and `mechdsl.lib.plasticity*` for the algo2code-transpiled
plasticity variants). Every model follows the same shape:

- a frozen `*Material` dataclass holding the parameters,
- standalone `pk2_stress(...)` / `material_tangent_voigt(...)` functions (hyperelastic),
  or a `radial_return(...)` function (dissipative),
- a `*Model` class implementing the shared `ConstitutiveModel` interface
  (`pk2_stress`, `material_tangent`, `voigt_tangent`, `state_variables`,
  `is_dissipative`).

!!! info "Stress and strain measures"
    All models work in the **Total Lagrangian** setting: PK2 stress **S** as a function
    of Green–Lagrange strain **E**. Tangents are returned either as a 4th-order tensor
    `(3,3,3,3)` or in `6×6` tensorial Voigt form (`[xx, yy, zz, xy, xz, yz]`, unscaled
    shears).

## Model matrix

| Model | Module | Class | Category | Tier |
|---|---|---|---|---|
| St. Venant–Kirchhoff | `models.svk` | `SVKMaterial` | Linear-elastic (large-rotation) | **MVP-stable** |
| Neo-Hookean | `models.neo_hookean` | `NeoHookeanMaterial` | Hyperelastic | MVP-stable |
| Mooney-Rivlin | `models.mooney_rivlin` | `MooneyRivlinMaterial` | Hyperelastic | experimental |
| Ogden | `models.ogden` | `OgdenMaterial` | Hyperelastic (spectral) | experimental |
| HGO | `models.hgo` | `HGOMaterial` / `HGOModel` | Anisotropic hyperelastic | experimental |
| J2 power-law | `models.j2_power_law` | `J2PowerLawMaterial` | Plasticity (isotropic hardening) | MVP-stable |
| J2 kinematic | `lib.plasticity_kinematic` | `J2KinematicMaterial` | Plasticity (kinematic hardening) | experimental |
| J2 mixed | `lib.plasticity_mixed` | `J2MixedMaterial` | Plasticity (mixed hardening) | experimental |
| Perzyna | `models.perzyna` | `PerzynaMaterial` | Viscoplasticity | experimental |
| Johnson-Cook | `models.johnson_cook` | `JohnsonCookMaterial` | Rate/temp viscoplasticity | experimental |
| Lemaitre | `models.lemaitre` | `LemaitreMaterial` | Continuum damage | experimental |

---

## Hyperelastic models

These have a stored energy Ψ; stress and tangent come from differentiating it.

### St. Venant–Kirchhoff

```python
import numpy as np
from mechdsl.symbolic.models.svk import SVKMaterial, pk2_stress, material_tangent_voigt

mat = SVKMaterial(E=200e3, nu=0.3)
E_strain = np.diag([0.01, -0.003, -0.003])
S = pk2_stress(mat, E_strain)                 # PK2 stress (3×3)
C_voigt = material_tangent_voigt(mat)         # constant tangent (6×6 Voigt)
```

### Neo-Hookean

```python
import numpy as np
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial, pk2_stress, material_tangent_voigt,
)

mat = NeoHookeanMaterial.from_E_nu(E=200e3, nu=0.3)
E_strain = np.diag([0.1, -0.03, -0.03])       # uniaxial stretch
S = pk2_stress(mat, E_strain)                 # PK2 stress (3×3)
C_voigt = material_tangent_voigt(mat, E_strain)
```

### Mooney-Rivlin & Ogden

```python
import numpy as np
from mechdsl.symbolic.models.mooney_rivlin import MooneyRivlinMaterial, pk2_stress

mr = MooneyRivlinMaterial(C1=80.0, C2=20.0, kappa=1.0e5)
S = pk2_stress(mr, np.diag([0.15, -0.04, -0.04]))
```

Ogden uses a spectral (principal-stretch) derivation and the same `pk2_stress` /
`material_tangent_voigt` surface via `OgdenMaterial`.

### HGO (fiber-reinforced / anisotropic) { #hgo-anisotropic }

```python
import numpy as np
from mechdsl.symbolic.models.hgo import HGOMaterial, HGOModel

mat = HGOMaterial(mu=10.0, k1=2.36, k2=0.84, kappa=1000.0, fiber_dispersion=0.1)
a1 = np.array([1.0, 0.0, 0.0])    # fiber family 1
a2 = np.array([0.0, 1.0, 0.0])    # fiber family 2

model = HGOModel(mat, fiber_dirs=(a1, a2))
E_strain = np.diag([0.2, -0.05, -0.05])
S = model.pk2_stress(E_strain)
C_voigt = model.voigt_tangent(E_strain)
```

In the LaTeX path, fiber directions come from `% mechanics fiber --family "..."`
directives ([see the directive reference](latex-directives.md#fiber-fiber-directions-anisotropic-materials)).

### User-defined energies { #user-defined-energies }

Any energy you can write in LaTeX can be compiled without touching the model code. Write
Ψ and point a `constitutive` directive at it — the symbolic layer differentiates it to
**S = ∂Ψ/∂E** and **C = ∂²Ψ/∂E²**:

```latex
% mechanics constitutive Psi --strain_energy
\Psi = \frac{\mu}{2}\left(\bar{I}_1 - 3\right) + \frac{\kappa}{2}\left(J - 1\right)^2
```

The example energy snippets in
[`dev/examples/`](https://github.com/SOSOVSKI/MechDSL/tree/main/dev/examples)
(`neo_hookean_energy.tex`, `mooney_rivlin_energy.tex`, `ogden_energy.tex`,
`hgo_energy.tex`, `svk_energy.tex`) show the exact LaTeX the parser accepts.

---

## Dissipative models

These have **no** usable stored energy for the stress. Stress and the *algorithmic
consistent tangent* come from a return-mapping algorithm. The J2 family's scalar
return-maps are authored as `algpseudocode` and transpiled by
[algo2code](../algo2code/index.md); the surrounding tensor algebra (deviatoric split, von Mises,
back-stress) lives in the Python orchestration wrappers.

### J2 plasticity — power-law isotropic hardening

Yield surface `f = σ_eq − σ_y(α)` with `σ_y(α) = σ_y0 + K·α^n`.

```python
import numpy as np
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial, radial_return

mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.5)
E_strain = np.diag([0.003, -0.001, -0.001])
res = radial_return(mat, E_strain, alpha_old=0.0)

res.stress         # updated PK2 stress (3×3)
res.alpha_new      # updated accumulated plastic strain
res.is_plastic     # did it yield this step?
res.tangent        # algorithmic consistent tangent (3,3,3,3)
```

### J2 plasticity — kinematic (Prager) hardening

Yield on the **relative** stress `‖dev(S) − β‖` with a linear back-stress β. This is the
model that exhibits the **Bauschinger effect** (reverse-yield below the forward yield
magnitude) the isotropic model cannot.

```python
import numpy as np
from mechdsl.lib.plasticity_kinematic import J2KinematicMaterial, radial_return_kinematic

mat = J2KinematicMaterial(E=200e3, nu=0.3, sigma_y0=250.0, H_kin=20_000.0)
res = radial_return_kinematic(
    mat,
    E_strain=np.diag([0.003, -0.001, -0.001]),
    plastic_strain_old=np.zeros((3, 3)),
    back_stress_old=np.zeros((3, 3)),
)
res.stress, res.back_stress, res.plastic_strain
```

### J2 plasticity — mixed hardening

Isotropic power-law **and** linear kinematic combined. It reduces to the isotropic model
when the kinematic modulus is 0, and to the kinematic model when the isotropic modulus is
0 — both reductions are part of the test suite.

```python
import numpy as np
from mechdsl.lib.plasticity_mixed import J2MixedMaterial, radial_return_mixed

mat = J2MixedMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=500.0, n=0.5, H_kin=20_000.0)
res = radial_return_mixed(
    mat,
    E_strain=np.diag([0.003, -0.001, -0.001]),
    alpha_old=0.0,
    plastic_strain_old=np.zeros((3, 3)),
    back_stress_old=np.zeros((3, 3)),
)
res.stress, res.alpha_new, res.back_stress
```

### Viscoplasticity & damage

- **Perzyna** (`models.perzyna.PerzynaMaterial`, `radial_return(...)`) — rate-dependent
  overstress viscoplasticity.
- **Johnson-Cook** (`models.johnson_cook.JohnsonCookMaterial`, `radial_return(...)`) —
  strain-rate and temperature-dependent flow stress.
- **Lemaitre** (`models.lemaitre.LemaitreMaterial`, `lemaitre_return(...)`) — continuum
  damage coupled to plasticity.

These follow the same dataclass + return-mapping shape as the J2 family. They are
`experimental` tier — see [support tiers](concepts.md#support-tiers).

---

## Adding your own model

- **Has a stored energy?** Write Ψ in LaTeX and use the
  [`constitutive --strain_energy`](latex-directives.md#deriving-a-model-from-a-user-written-energy)
  path. No Python needed for the stress/tangent.
- **Dissipative (return-mapping)?** Author the scalar return-map as `algpseudocode`,
  transpile it via [algo2code](../algo2code/index.md), and add a thin Python orchestration wrapper
  (mirror `lib/plasticity_kinematic.py`). Validate against an independent reference and,
  where the model generalizes an existing one, **reduction cross-checks**.
