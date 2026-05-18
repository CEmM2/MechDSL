"""Example: Run the MechDSL compilation pipeline (ProblemIR -> Taichi source).

This script demonstrates the full compiler pipeline from a manually
constructed ProblemIR through lowering, einsum optimisation, and Taichi
code emission.  This is the workflow that the LaTeX parser (Phase 2) will
automate once implemented.

Usage:
    uv run python dev/examples/run_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize


def build_elastic_problem() -> ProblemIR:
    """Construct ProblemIR for a 3D SVK cantilever beam."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="svk",
            params={"E": 200e3, "nu": 0.3},
        ),
        boundaries=(
            BoundaryCondition(
                name="fix",
                bc_type=BCType.DIRICHLET,
                field_name="u",
                components=(0, 1, 2),
                value=0.0,
            ),
            BoundaryCondition(
                name="load",
                bc_type=BCType.NEUMANN,
                field_name="u",
                traction="0 0 -1000",
            ),
        ),
    )


def build_plastic_problem() -> ProblemIR:
    """Construct ProblemIR for a 3D J2 necking bar."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={
                "E": 200e3,
                "nu": 0.3,
                "sigma_y0": 250.0,
                "K": 1000.0,
                "n": 1.0,
            },
        ),
        boundaries=(
            BoundaryCondition(
                name="fix",
                bc_type=BCType.DIRICHLET,
                field_name="u",
                components=(0, 1, 2),
                value=0.0,
            ),
            BoundaryCondition(
                name="pull",
                bc_type=BCType.DIRICHLET,
                field_name="u",
                components=(2,),
                value=0.1,
            ),
        ),
    )


def run_pipeline(problem_ir: ProblemIR, label: str) -> str:
    """Run the full compilation pipeline and return emitted source."""

    # Step 1: Lower ProblemIR -> ElementIR + einsum specs + contraction plans
    loc_result, plans = localise_and_optimize(problem_ir)

    print(f"[{label}] Localisation complete:")
    print(f"  Element type: {loc_result.element_ir.element_type}")
    print(f"  Quadrature points: {loc_result.element_ir.quadrature.n_points}")
    print(f"  Einsum specs: {len(loc_result.einsum_specs)}")
    print(f"  Contraction plans: {len(plans)}")

    for plan in plans:
        print(f"    {plan.einsum_string}: tier {plan.tier}, ~{plan.estimated_flops} flops")

    # Step 2: Build artifact bundle
    bundle = ArtifactBundle.from_pipeline(
        problem_ir=problem_ir,
        localisation=loc_result,
        contraction_plans=plans,
    )

    # Step 3: Emit Taichi source code
    source = emit(bundle)
    print(f"  Emitted source: {len(source)} chars, {source.count(chr(10))} lines")

    return source


def main() -> None:
    # --- Elastic problem ---
    elastic_ir = build_elastic_problem()
    elastic_source = run_pipeline(elastic_ir, "SVK Elastic")

    # --- Plastic problem ---
    plastic_ir = build_plastic_problem()
    plastic_source = run_pipeline(plastic_ir, "J2 Plastic")

    # --- Optionally write to files ---
    out_dir = Path("dev/examples/_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    elastic_path = out_dir / "cantilever_svk.py"
    elastic_path.write_text(elastic_source, encoding="utf-8")
    print(f"\nElastic source written to: {elastic_path}")

    plastic_path = out_dir / "necking_j2.py"
    plastic_path.write_text(plastic_source, encoding="utf-8")
    print(f"Plastic source written to: {plastic_path}")

    # --- Verify emitted source is valid Python ---
    import ast

    ast.parse(elastic_source)
    ast.parse(plastic_source)
    print("\nBoth emitted sources parse as valid Python.")

    return None


if __name__ == "__main__":
    main()
    sys.exit(0)
