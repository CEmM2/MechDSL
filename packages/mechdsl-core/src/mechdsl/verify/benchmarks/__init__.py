"""Benchmark harness for MechDSL physical verification (Phase 10).

Public API
----------
BenchmarkResult
    Frozen dataclass: displacements, newton_iters, wallclock_s, extras.
CantileverParameters
    P10-2: elastic cantilever benchmark setup for TL/UL x material x element matrix.
run_cantilever_benchmark
    P10-2: cantilever tip displacement vs Euler-Bernoulli beam theory.
CookMembraneParameters
    P10-3: locked TL + J2 + Hex8 Cook's membrane benchmark setup.
run_cook_membrane_benchmark
    P10-3: Cook's membrane regression vs committed Hex8 reference.
PlateWithHoleParameters
    P10-5: Kirsch plate-with-hole benchmark setup for Hex8/Hex20.
run_plate_with_hole_benchmark
    P10-5: plate-with-hole stress concentration vs Kirsch K_t = 3.
run_thick_cylinder_benchmark
    P10-4: thick-walled internally-pressurised cylinder vs Lame solution.
run_necking_bar_benchmark
    Necking bar benchmark (MVP plasticity reference).
run_notched_bar_benchmark
    P10-8: notched bar with Lemaitre damage; load-displacement history and
    damage-field localisation.
build_notched_bar_mesh
    P10-8 public mesh builder (Hex8 rectangular bar + semi-circular notch).
NotchedBarMesh
    P10-8 mesh bundle (coords, connectivity, boundary sets, notch root).
run_hgo_uniaxial
    P10-9: HGO fiber-reinforced strip uniaxial stretch benchmark.
hgo_analytical_uniaxial_stress
    P10-9: closed-form HGO uniaxial PK1 stress (reference curve).
generate_strip_mesh
    P10-9: rectangular Hex8 strip mesh generator.
fiber_direction_field
    P10-9: per-element uniform fiber-direction field builder.
TaylorImpactParameters
    P8-1: public Taylor impact benchmark setup with smoke/nightly profiles.
run_taylor_impact_benchmark
    P8-1: Taylor impact runner — wraps the Phase E7 internal explicit
    runtime + JC return mapping + rigid-wall contact and packs Taylor
    metrics (final length, mushroom radius/diameter, peak PEEQ) into
    ``BenchmarkResult.extras``.
"""

from mechdsl.verify.benchmarks._core import BenchmarkResult
from mechdsl.verify.benchmarks.cantilever import (
    CantileverParameters,
    run_cantilever_benchmark,
)
from mechdsl.verify.benchmarks.cook_membrane import (
    CookMembraneParameters,
    run_cook_membrane_benchmark,
)
from mechdsl.verify.benchmarks.hgo_strip import (
    fiber_direction_field,
    generate_strip_mesh,
    hgo_analytical_uniaxial_stress,
    run_hgo_uniaxial,
)
from mechdsl.verify.benchmarks.necking_bar import (
    NeckingBarParameters,
    run_necking_bar_benchmark,
)
from mechdsl.verify.benchmarks.notched_bar import (
    NotchedBarMesh,
    build_notched_bar_mesh,
    run_notched_bar_benchmark,
)
from mechdsl.verify.benchmarks.plate_with_hole import (
    PlateWithHoleParameters,
    run_plate_with_hole_benchmark,
)
from mechdsl.verify.benchmarks.taylor_impact import (
    TaylorImpactParameters,
    run_taylor_impact_benchmark,
)
from mechdsl.verify.benchmarks.thick_cylinder import run_thick_cylinder_benchmark

__all__ = [
    "BenchmarkResult",
    "CantileverParameters",
    "CookMembraneParameters",
    "NeckingBarParameters",
    "NotchedBarMesh",
    "PlateWithHoleParameters",
    "TaylorImpactParameters",
    "build_notched_bar_mesh",
    "fiber_direction_field",
    "generate_strip_mesh",
    "hgo_analytical_uniaxial_stress",
    "run_cantilever_benchmark",
    "run_cook_membrane_benchmark",
    "run_hgo_uniaxial",
    "run_necking_bar_benchmark",
    "run_notched_bar_benchmark",
    "run_plate_with_hole_benchmark",
    "run_taylor_impact_benchmark",
    "run_thick_cylinder_benchmark",
]
