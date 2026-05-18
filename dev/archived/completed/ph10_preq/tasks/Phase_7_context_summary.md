# Phase 7 Context Summary: Taylor Impact Runtime Surface

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E7 Taylor Impact Runtime Surface

## Must Know

- This phase is runtime enablement only; do not expose the public Taylor benchmark runner yet.
- Use existing `JohnsonCookMaterial`, Johnson-Cook return mapping, reduced Hex8, and Flanagan-Belytschko hourglass force.
- Do not change Johnson-Cook or hourglass implementations unless focused tests prove a real defect.
- Required runtime pieces are explicit update, rigid-wall contact, hourglass boundedness, and state output.

## Should Know

- Postprocessing must eventually provide final length, mushroom radius, and equivalent plastic strain.
- Keep this phase independent from MMS and cantilever.

## Allowed Deviations

- None. Runtime shortcuts must be recorded as blockers rather than hidden inside benchmark tolerances.

## Downstream Impact

- Completion unlocks the public Taylor impact benchmark phase.

