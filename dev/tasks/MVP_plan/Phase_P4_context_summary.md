# Phase 4 — IR and Lowering: Context Summary

## Must Know

### Conventions
- **IR discipline**: All information flows through Mechanics IR → Element IR → Einsum IR. Never bypass a layer. Ref: CLAUDE.md "IR discipline".
- **IRs are immutable**: Frozen dataclasses. Validation at construction time.
- **Unsupported constructs**: Must raise with the specific plan phase that adds support (e.g., "Updated Lagrangian is planned for Plan B phase B1").
- **Hex8 element convention**: Follows MFEM/VTK node ordering. Ref: `07-CONVENTIONS.md §8`.

### Key Principles
- This phase builds the **semantic center** of the compiler pipeline. ProblemIR is the canonical representation of the physics problem.
- ElementIR encodes everything needed for code generation: basis functions, quadrature, geometry mapping.
- The lowering pass (P4.3) is the most complex task — it bridges symbolic mechanics to concrete FE operations.
- P4.1 and P4.2 are **parallel-safe** if IR contracts are agreed first.

### Pre-resolved Design Decisions
- **ProblemIR fields**: dim, formulation (total_lagrangian only), element_type (hex8 only), material, boundaries, coordinates.
- **ElementIR fields**: basis (trilinear), gradients, quadrature (2x2x2 Gauss), geometry_map (isoparametric), convected_metrics.
- **Einsum extraction**: The FE localization pass extracts einsum strings for internal force and tangent operations.
- **Artifact bundle**: Stores IR + contraction plans + emitted source. Serializable for golden comparisons.

## Should Know

### Downstream Impact
- P4.1/P4.2 feed P5.1 (einsum optimizer needs IR schemas to understand contraction shapes).
- P4.3 feeds P5.2 (optimizer integration) and P6.2 (Taichi printer needs localized IR).
- P4.4 feeds P5.2 and P6.2 (artifact bundle carries all pipeline state to codegen).
- Phase 4 blocks Phase 5 entirely and most of Phase 6.
- IR schema changes after this phase are expensive — they cascade through Phases 5, 6, 7, 8.
