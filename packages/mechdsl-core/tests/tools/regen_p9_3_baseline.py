"""Regenerate golden/template_family_emission_baseline.json.

Usage (from repo root):

    uv run python packages/mechdsl-core/tests/tools/regen_p9_3_baseline.py

Writes the baseline JSON to the golden directory adjacent to this tools dir.
All 16 realisable HEX8 triples are timed; skipped combos are omitted.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path
from unittest import mock

# Make the package importable when run as a script without editable install.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SRC = _REPO_ROOT / "packages" / "mechdsl-core" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mechdsl.codegen.artifact import ArtifactBundle  # noqa: E402
from mechdsl.codegen.mfem_printer import emit as mfem_emit  # noqa: E402
from mechdsl.codegen.moose_printer import emit as moose_emit  # noqa: E402
from mechdsl.codegen.taichi_printer import emit as taichi_emit  # noqa: E402
from mechdsl.ir.mechanics_ir import (  # noqa: E402
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize  # noqa: E402

_GOLDEN_PATH = (
    Path(__file__).resolve().parent.parent / "golden" / "template_family_emission_baseline.json"
)

_N_TRIALS = 5
_RATIO_TOLERANCE = 1.2

_BACKEND_EMIT = {
    "taichi": taichi_emit,
    "mfem": mfem_emit,
    "moose": moose_emit,
}

_MATERIAL_PARAMS: dict[str, dict[str, float]] = {
    "svk": {"E": 200e3, "nu": 0.3},
    "j2_power_law": {"E": 200e3, "nu": 0.3},
    "perzyna": {"E": 200e3, "nu": 0.3},
    "lemaitre": {"E": 200e3, "nu": 0.3},
}

# (element_str, formulation, material, backend) — only realisable combos.
_REALISABLE = [
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "svk", "taichi"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "svk", "mfem"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "svk", "moose"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "j2_power_law", "taichi"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "j2_power_law", "moose"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "perzyna", "moose"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "lemaitre", "taichi"),
    (ElementType.HEX8, Formulation.TOTAL_LAGRANGIAN, "lemaitre", "moose"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "svk", "taichi"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "svk", "mfem"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "svk", "moose"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "j2_power_law", "taichi"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "j2_power_law", "moose"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "perzyna", "moose"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "lemaitre", "taichi"),
    (ElementType.HEX8, Formulation.UPDATED_LAGRANGIAN, "lemaitre", "moose"),
]


def _make_bundle(elt: ElementType, form: Formulation, mat: str) -> ArtifactBundle:
    params = _MATERIAL_PARAMS[mat]
    problem_ir = ProblemIR(
        dim=3,
        formulation=form,
        element_type=elt,
        material=MaterialSpec(model=mat, params=params),
        boundaries=(BoundaryCondition(name="fix_root", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


def _measure(emit_fn, bundle: ArtifactBundle, family_on: bool) -> float:
    flag = "1" if family_on else "0"
    times: list[float] = []
    for _ in range(_N_TRIALS):
        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": flag}):
            t0 = time.perf_counter()
            emit_fn(bundle)
            times.append(time.perf_counter() - t0)
    return statistics.median(times)


def main() -> None:
    triples: dict[str, dict] = {}

    print(f"Measuring {len(_REALISABLE)} triples, {_N_TRIALS} trials each...")
    for elt, form, mat, backend in _REALISABLE:
        key = f"{elt.value}-{form.value}-{mat}-{backend}"
        print(f"  {key} ...", end=" ", flush=True)
        bundle = _make_bundle(elt, form, mat)
        emit_fn = _BACKEND_EMIT[backend]
        med_tier = _measure(emit_fn, bundle, family_on=False)
        med_family = _measure(emit_fn, bundle, family_on=True)
        ratio = med_family / med_tier if med_tier > 0.0 else 1.0
        triples[key] = {
            "tier_only_median_s": round(med_tier, 6),
            "family_median_s": round(med_family, 6),
            "ratio": round(ratio, 4),
        }
        status = "OK" if ratio <= _RATIO_TOLERANCE else f"WARN ratio={ratio:.3f}"
        print(f"ratio={ratio:.4f} ({status})")

    payload = {
        "generated_at": str(date.today()),
        "ratio_tolerance": _RATIO_TOLERANCE,
        "trials": _N_TRIALS,
        "note": (
            "Median family-ON emission time divided by median family-OFF (legacy / tier-only). "
            "Target <= 1.2. Regenerate by running: "
            "uv run python packages/mechdsl-core/tests/tools/regen_p9_3_baseline.py"
        ),
        "triples": triples,
    }

    _GOLDEN_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {_GOLDEN_PATH}")

    worst = max(v["ratio"] for v in triples.values())
    avg = sum(v["ratio"] for v in triples.values()) / len(triples)
    print(f"Worst ratio: {worst:.4f}  Average ratio: {avg:.4f}  Tolerance: {_RATIO_TOLERANCE}")
    if worst > _RATIO_TOLERANCE:
        print("WARNING: worst-case ratio exceeds tolerance — investigate before committing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
