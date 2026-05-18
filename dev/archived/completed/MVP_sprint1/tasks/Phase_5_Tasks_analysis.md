# Phase 5 Task Analysis

## Task Scoring

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P5-T1 | Rename emit stub + add emit_postprocess() | 2 | 2 | 4 | P4-T2 (done) | P5-T2 | Sonnet 4.6 |
| P5-T2 | Add emit_main() function | 2 | 1 | 3 | P5-T1 | P5-T3 | Sonnet 4.6 |
| P5-T3 | Wire emit chain + regen golden files + tests | 3 | 3 | 6 | P5-T2 | P6-T1 | Sonnet 4.6 |

## Execution Order

Strict sequential: P5-T1 → P5-T2 → P5-T3. Each depends on the previous.
P5-T1 and P5-T2 add functions without wiring them. P5-T3 wires + regenerates goldens.
