# Phase 1 Context Summary: Boundary-directive flow into emitted code

**Plan:** `dev/plans/post_recovery_plan.md`

## Conventions

- **Index convention:** lowercase `i,j,k` for spatial indices on traction vector; surface tag is a string identifier matching mesh sideset names.
- **Voigt ordering:** unscaled shears `[xx, yy, zz, xy, xz, yz]` (07-CONVENTIONS).
- **Sign:** tension-positive — Neumann traction is applied as written, not negated.
- **JIT budget:** emitted f_ext kernel must respect ≤ 2000 unrolled lines per `@ti.kernel`; mesh indices stay as runtime loops.

## Key Principles

- **IR discipline:** ProblemIR is the semantic center; BoundaryCondition extension lives in `mechdsl.ir.problem`. Lowering passes consume the extended IR — they do not invent new BC fields.
- **Façade back-compat:** `compile_latex` return shape is preserved; `f_ext_kernel` is added as an optional field defaulting to None.
- **Plan B continuity:** `BoundaryCondition` IR dataclass is extended, not replaced — no parallel BC type introduced.
- **Surface tagging:** Neumann BCs reference mesh surface sets by tag; mesh adapter must support tag-based lookup.

## Pre-resolved Design Decisions

- BoundaryCondition gains `traction: Vec3` and `surface_tag: str` fields with defaults preserving back-compat (P1-1).
- Directive grammar: `% mechanics boundary load --type neumann --traction "x y z" [--surface tag]` (P1-2).
- Lowering produces per-node force contributions (P1-3); codegen emits a kernel that initializes f_ext from those (P1-4).
- Phase 3 docstring is sequenced after Phase 1 so the contract reflects post-Phase-1 reality (plan line 184-185).

## Allowed Deviations

- None beyond the optional façade field. The plan calls out façade signature stability explicitly (lines 116-117).

## Downstream Impact

- **Phase 3 (P3-1)** depends on Phase 1 closure — docstring paragraph references the BC handoff contract that lands here.
- **Phase 7 (P7-3)** removes the obsolete traction-string-gap comment in test_p7_2.py once Phase 1 lands (item 9 supersession).
- Future plans consuming Neumann BCs will rely on the extended `BoundaryCondition` slots and the optional `f_ext_kernel` facade field.
