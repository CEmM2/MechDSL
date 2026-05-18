# Phase 7 — Nonlinear Solve Runtime (Elastic End-to-End): Context Summary

## Must Know

### Conventions
- **Newton convergence**: `||R|| < 1e-8 * ||R_0||`. Ref: `07-CONVENTIONS.md §6`.
- **CG convergence**: `||r|| < 1e-10 * ||r_0||`. Ref: `07-CONVENTIONS.md §6`.
- **Hex8 node ordering**: MFEM/VTK conventions. Ref: `07-CONVENTIONS.md §8`.
- **Outward normal**: Outward-pointing; traction `t = sigma * n` on Neumann boundary.

### Key Principles
- This phase produces a **working elastic solver** — the first time end-to-end LaTeX-to-solution runs.
- P7.2/P7.3 are **parallel-safe** and can start early (only need P0.2), but P7.1 depends on Phase 6.
- The Newton driver (P7.1) is a critical integration point: it wires force kernel, tangent matvec, linear solver, and BCs together.
- Adaptive load stepping (P7.4) must work for both elastic and plastic (Phase 8) — design with plasticity in mind.

### Pre-resolved Design Decisions
- **Linear solver**: Via `LinearSolverInterface` (P0.4). Matrix-free: tangent is provided as a matvec function.
- **Mesh**: Structured Hex8 only for MVP. No unstructured mesh support.
- **BC enforcement**: Dirichlet via zeroing rows/cols + prescribed values. Neumann via surface traction integral.
- **Cantilever benchmark**: 40x8x4 Hex8 mesh, elastic SVK, tip displacement within 5% of EB beam theory.

## Should Know

### Downstream Impact
- P7.1 (Newton driver) feeds P7.4 (load stepping) and P9.1 (e2e test).
- P7.2 (BC codegen) is used by both elastic (Phase 7) and plastic (Phase 8) solvers.
- P7.3 (mesh I/O) provides structured meshes for all benchmarks in Phase 9.
- P7.4 (load stepping) is critical for plasticity — step cutback is essential for convergence near yield.
- This phase's elastic cantilever result is the first physical validation of the generated code.
