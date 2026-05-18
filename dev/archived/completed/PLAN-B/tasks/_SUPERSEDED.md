# ⚠️ Superseded

This task folder corresponds to PLAN-B (`dev/design_docs/PLAN-B.md` and friends), which has been **superseded for the active execution flow** by [`dev/plans/recovery_plan_latex_contract.md`](../../plans/recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5).

The active execution source for the LaTeX-input contract recovery is the recovery plan; the active task folder is [`dev/tasks/recovery_plan_latex_contract/`](../recovery_plan_latex_contract/) and the active tracker is [`dev/tracking/tasks-tracker_recovery_plan_latex_contract.md`](../../tracking/tasks-tracker_recovery_plan_latex_contract.md).

This folder is retained for historical reference only. Do not start new work from these task JSONs.

## Runtime-active vs archived sub-deliverables

post_recovery_plan Phase 7 (P7-5). Plan-B's task index covers pre-recovery deliverables; some of those still ship runtime code in `packages/mechdsl-core/`, others are pure planning artifacts. This sub-section pins the bucket each one falls into so future readers can tell at a glance whether to expect live code under `src/` or just historical task JSONs.

### Runtime-active (code still ships under `packages/mechdsl-core/src/`)

- **B0 / B1 / B2 / B3 — frontend, symbolic, IR, lowering scaffolding.** The compiler-pipeline layer split (`mechdsl.frontend` → `mechdsl.symbolic` → `mechdsl.ir` → `mechdsl.lowering`) landed during Plan-B and remains the load-bearing structure. See `.claude/CLAUDE.md` "Architecture (mechdsl-core)".
- **B5 codegen baseline.** The Taichi printer at `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` derives from Plan-B Phase 5; subsequent recovery + post-recovery work extends it without rewriting.
- **B6 J2 plasticity reference path.** `mechdsl.symbolic.models.j2_power_law.radial_return` is the imported reference now wrapped by `mechdsl.lib.plasticity` (post_recovery_plan P5-3); the Plan-B implementation is still active code.
- **B7-B9 SVK + verification harness.** Patch tests, MMS convergence checks, and reference kernels in `packages/mechdsl-core/tests/ref/` and `tests/golden/` originated under Plan-B and remain the regression baseline.

### Archived (planning artifacts only — no live code)

- **Plan-B handoffs (`Handoff_Phase_3.md` … `Handoff_Phase_11.md`).** Historical phase-to-phase context. Not consumed by any runtime path.
- **Plan-B scaffold validations (`Phase_*_Scaffold_Validation.md`).** Pre-execution audits for Plan-B phases. Captured here for traceability only.
- **Plan-B-only Hex20 / TET10 localisation tasks.** Per `.claude/CLAUDE.md` MVP scope ("3D Hex8 ... only"), these element families are not implemented in the runtime; tests under `test_template_family_budget.py` skip them with a Plan-B reference. The skip messages are the only runtime touchpoint.
- **Plan-B governance / acceptance reports.** `_FINAL_REPORT.md`, exit-criteria matrices, and similar artefacts under `dev/tasks/PLAN-B/` are reference-only.

When in doubt, check `dev/tracking/tasks-tracker_PLAN-B.md` for status; new work should land under the recovery plan or post_recovery_plan trackers, never directly under `dev/tasks/PLAN-B/`.
