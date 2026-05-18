"""Compile the elastic cantilever MVP example via the programmatic API."""

from __future__ import annotations

from mechdsl import compile
from mechdsl.frontend import build_context
from mechdsl.ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)


def problem_ir_from_context(ctx: dict) -> ProblemIR:
    """Adapt a Layer 1 frontend context into the immutable Mechanics IR."""
    boundaries = tuple(
        BoundaryCondition(
            name=raw.get("name", raw.get("face", f"bc_{index}")),
            bc_type=BCType(raw["type"]),
            components=tuple(raw.get("dofs", (0, 1, 2))),
            value=raw.get("value", 0.0),
            traction=raw.get("traction"),
        )
        for index, raw in enumerate(ctx["boundaries"])
    )
    return ProblemIR(
        dim=ctx["dim"],
        formulation=Formulation(ctx["formulation"]),
        element_type=ElementType(ctx["cell_type"]),
        material=MaterialSpec(model=ctx["material_type"], params=ctx["params"]),
        boundaries=boundaries,
    )


def build_example_context() -> dict:
    """Construct the elastic cantilever frontend context."""
    return build_context(
        dim=3,
        cell_type="hex8",
        formulation="total_lagrangian",
        material_type="svk",
        params={"E": 200e3, "nu": 0.3},
        boundaries=[
            {"name": "fix", "face": "x0", "type": "dirichlet", "dofs": [0, 1, 2], "value": 0.0},
            {"name": "load", "face": "x1", "type": "neumann", "traction": "t_bar"},
        ],
    )


def main() -> None:
    ctx = build_example_context()
    problem_ir = problem_ir_from_context(ctx)
    bundle = compile(problem_ir)

    print("Compilation summary")
    print("example: elastic_cantilever")
    print(f"material: {problem_ir.material.model}")
    print(f"boundaries: {[bc.name for bc in problem_ir.boundaries]}")
    print(f"contraction_plans: {len(bundle.contraction_plans)}")
    print(f"emitted_lines: {bundle.emitted_source.count(chr(10)) + 1}")
    print(f"content_hash: {bundle.content_hash()}")


if __name__ == "__main__":
    main()
