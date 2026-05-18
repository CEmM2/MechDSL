# Phase 8 Context Summary: MFEM and MOOSE backend printers

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B8 MFEM and MOOSE backend printers

## Conventions

- **Voigt conversion is required** at every backend boundary. MVP uses **tensorial** Voigt `[xx, yy, zz, xy, xz, yz]` with unscaled shears. MFEM and MOOSE use engineering Voigt (`γ_xy = 2 ε_xy`). Provide a dedicated conversion helper per backend; never do it ad hoc inside the printer.
- File extensions: Taichi = `.py`, MFEM = `.cpp` + `CMakeLists.txt`, MOOSE = `.C` + `.h` + `.i` input file.
- Backend printers live at `mechdsl.codegen.<backend>_printer` and expose an `emit(bundle) -> str` entry point mirroring `taichi_printer.emit`.

## Key Principles

- **Three backends, one IR.** MFEM and MOOSE printers consume the exact same `ArtifactBundle` as the Taichi printer. No backend-specific extensions to Mechanics IR or Element IR — if a backend needs something, push it through the IR, don't patch it at the printer.
- **Generated C++ compiles without editing.** The emitted file plus the shipped `CMakeLists.txt` / `Makefile.app` must build with the upstream MFEM or MOOSE install. No "hand-edit step required" — that's what Plan A worked hard to avoid.
- **Cross-backend equivalence is the acceptance criterion.** Three backends, same problem, displacement fields within 1e-8 max absolute difference.
- **MFEM and MOOSE installs are heavyweight.** Local dev machines don't have them; tests must skip gracefully rather than fail. CI uses a Docker image with both pre-installed.
- **Generated MFEM code targets `ParNonlinearForm`** (MPI-parallel) by default. Serial mode is a follow-up.
- **Generated MOOSE code inherits from `ComputeStressBase`** and uses `RankTwoTensor` / `RankFourTensor` for tensor ops.

## Pre-resolved Design Decisions

- Each printer emits ONE file per problem, not a module tree. The file is self-contained (plus the CMakeLists / Makefile template).
- libclang is the parse-checker for emitted C++ in unit tests — no need to compile the code, just parse it.
- Cross-backend verification test is `@pytest.mark.slow` AND marked `@pytest.mark.nightly` (runs once per day, not per commit).

## Allowed Deviations

- Tet10 and Hex20 support in MFEM/MOOSE printers is scoped to the same set as Plan A: Hex8 only for MVP. Higher-order elements in the C++ backends are a post-MVP follow-up.

## Downstream Impact

- **Phase 9 (template tuning)** depends on Phase 8 because the template family abstraction needs multiple backends to motivate it.
- **P10 benchmarks** primarily use the Taichi backend; MFEM/MOOSE runs are limited to the cross-backend verification test P8-3.
- The backend abstraction set up in Phase 8 is extensible: future backends (deal.II, FEniCS) can hook into the same template family mechanism introduced in Phase 9.
