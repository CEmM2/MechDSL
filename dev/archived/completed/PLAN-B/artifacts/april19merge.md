# April 19 merge plan — open PRs #74 and #118

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). This document records a point-in-time merge plan from 2026-04-19 and is retained for historical reference only. The active execution source for the LaTeX-input contract recovery is the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

## Context

As of 2026-04-19 two PRs are open against `main`:

| PR | Title | Branch | Size | Reviews | CI |
|----|-------|--------|------|---------|-----|
| [#74](https://github.com/SOSOVSKI/MechDSL/pull/74) | Plan B Phase 1: Updated Lagrangian formulation | `plan-b_phase-1-p1-4` | +1673 / −170, 19 files, 8 commits | 5 inline comments (1 HIGH correctness) from `gemini-code-assist`, no human review | `lint: FAIL`, `test: PASS`, `slow-tests: PASS`, `budget: PASS` |
| [#118](https://github.com/SOSOVSKI/MechDSL/pull/118) | PLAN-B Phase 10: V&V benchmarks | `plan-b_phase-10` | +30115 / −1400, 100+ files | 1 review (details unread), mergeable | `lint: FAIL`, `test: FAIL`, `slow-tests: FAIL`, `budget: PASS` |

This document records (1) the merge order and why, and (2) the drafted replies to the five inline comments on PR #74. Nothing is pushed or merged by writing this file — it is a plan for the user to approve and execute.

## PRs merge sequence

**#74 first, then #118.** Non-negotiable — #118 already contains `P1-4.json`, `P1-6.json`, `P1-7.json`, `phase_1_gates.md`, and changes to `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` and `mechanics_ir.py` that logically depend on the Phase 1 UL formulation. Merging #118 before #74 would either make #74 empty (if rebased) or produce a conflict cascade.

### Step-by-step

1. **Resolve PR #74 review comments.**
   - Post the five drafted replies (below) once the user approves them.
   - Implement the two ACCEPT items (comments #1 and #3/#4) and the one pair-ACCEPT (comment #2 — numerical test that `exec`s the generated source). See "Follow-up fix commit" section.
   - Push to `plan-b_phase-1-p1-4`, wait for CI to go green (the `lint` failure must be resolved too — check what's actually failing before merging).
2. **Merge PR #74** into `main` (squash or standard merge per repo convention; prior merges on this repo used non-squash — see `git log --merges` — keep consistent).
3. **Re-run `npx gitnexus analyze`** on `main` to refresh the index (project CLAUDE.md §"Keeping the Index Fresh"). A PostToolUse hook normally handles this; verify it fired.
4. **Rebase PR #118 onto updated `main`.**
   - Expect conflicts in: `AGENTS.md`, `CLAUDE.md`, `dev/session-log.md`, `dev/skill-performance.csv`, `dev/chats/MechDSL_2026-04-16_15-45_handoff.md`, `dev/tasks/PLAN-B/gates/phase_1_gates.md`, `dev/tracking/tasks-tracker_PLAN-B.md`, `dev/tasks/PLAN-B/json/P1-{4,6,7}.json`, `dev/tasks/PLAN-B/reports/P1-{6,7}_report.md`, `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py`, `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py`.
   - Prefer the post-#74 (HEAD) version for code files unless #118 has deliberate Phase-10-era changes layered on top.
5. **Triage #118 red CI.** The `lint`, `test`, and `slow-tests` failures must be investigated before merge. Given the size (+30k lines) this likely needs its own plan. Do **not** merge while three checks are red.
6. **Separate review pass for #118.** Given its size and scope (phases 2–10 bundled), request a human review before merge. This is outside the scope of today's plan.

## PR #74 inline review comments — drafted replies

The five inline comments on PR #74 (all from `gemini-code-assist[bot]`, commit `c0cf2894`):

| # | GitHub ID | Severity | File : Line | Topic | Decision |
|---|----|----------|-----------|-------|--------|
| 1 | 3092605996 | **HIGH** | `codegen/taichi_printer.py:733` | `dsigma_geo` Hadamard vs matrix product | ACCEPT |
| 2 | 3092606024 | medium | `tests/test_taichi_printer_ul.py:285` | Test doesn't `exec` generated code | ACCEPT |
| 3 | 3092615707 | medium | `codegen/taichi_printer.py:717` | `J_det = detj / detJ0` instead of `np.linalg.det(F)` | ACCEPT |
| 4 | 3092619413 | medium | `codegen/taichi_printer.py:717` | Duplicate of #3 | ACCEPT (defer to #3's thread) |
| 5 | 3092619436 | medium | `codegen/taichi_printer.py:685` | Manual 3×3 det for `J0` | DEFER |

### Comment 1 — ACCEPT: geometric stiffness is a matrix product, not Hadamard

The reviewer is mathematically correct. With `dNdx[a, k] = ∂N_a/∂x_k` and `grad_v[i, l] = Σ_b v_{b,i} ∂N_b/∂x_l`, the geometric-stiffness contribution to the element matvec is

```
K_geo v_e[a, i] = Σ_q w_q · detj · Σ_{k,l} dNdx[a, k] σ_{kl} grad_v[i, l]
               = Σ_q w_q · detj · (dNdx @ (σ @ grad_v.T))[a, i]
```

(using Cauchy-stress symmetry `σ = σ.T`). The current `sigma * grad_v` (element-wise) only coincides for diagonal `grad_v` — any non-axial direction gives a wrong matvec. The bug was invisible to the existing tests because `test_ul_tangent_contains_geometric_stiffness_term` only string-matches the emitted source, and the rigid-rotation / cantilever tests happen to exercise near-diagonal `grad_v`.

**Draft reply:**

> Agreed — this is a correctness bug. The derivation is `K_geo v_e[a,i] = Σ_k dNdx[a,k] · Σ_l σ_{kl} · grad_v[i,l]`, which (using Cauchy symmetry) is `dNdx @ (σ @ grad_v.T)`. The current Hadamard form only coincides for diagonal velocity gradients, so it silently passes our rigid-rotation and cantilever tests (near-uniaxial states) while giving wrong matvecs for shear / mixed directions.
>
> Fixing in a follow-up commit on this branch: (a) change the emitter to `dsigma_geo = sigma @ grad_v.T`, (b) update the `_emit_ul_tangent_qp_body` docstring (the "Hadamard" comment is now wrong), (c) update `test_ul_tangent_contains_geometric_stiffness_term` to string-match the new emission, and (d) add a numerical execution test (see comment #2) that would have caught this.

### Comment 2 — ACCEPT (pair with #1): tests don't exercise generated code

`test_ul_tangent_matches_handwritten_reference` validates `tests/ref/ref_hex8_ul.py` against finite differences, but never `exec`s the emitted source. So the Hadamard bug in comment #1 is invisible to the test suite; all three UL tests pass with a broken emitter.

**Draft reply:**

> Good catch, and this is the root cause that let comment #1 slip through. Plan: add `test_ul_tangent_generated_matches_reference` that (1) builds a UL `ProblemIR`, (2) runs the full Taichi printer to produce the generated source (reusing `_make_ul_elastic_bundle`), (3) `exec`s the module, and (4) calls the emitted `tangent_matvec` on a non-trivial `v` with shear components, asserting agreement with both the handwritten reference in `tests/ref/ref_hex8_ul.py` and a central-difference tangent of the emitted `internal_force`. Shipping alongside the fix for #1.

### Comment 3 — ACCEPT: use `J_det = detj / detJ0`

`det(F) = det(j_cur) / det(J0)` identically since `F = j_cur · J0⁻¹`, and both `detj` and `detJ0` are already computed and zero-guarded right above. The extra `np.linalg.det(F)` is redundant.

**Draft reply:**

> Accepted — `det(F) = det(j_cur)/det(J0)` holds identically since `F = j_cur · J0⁻¹`, and both determinants are already computed and zero-guarded right above. Switching to `J_det = detj / detJ0` drops the per-QP `np.linalg.det(F)` call and keeps the determinant consistent with the inverses we already reused for `dNdx`.

### Comment 4 — ACCEPT (duplicate of #3)

**Draft reply:**

> Same fix as [#3092615707](https://github.com/SOSOVSKI/MechDSL/pull/74#discussion_r3092615707) — adopting `J_det = detj / detJ0` in the follow-up commit.

### Comment 5 — DEFER: manual 3×3 determinant for `J0`

Real but low-priority. The same emitted block already calls `np.linalg.inv(J0)` and `np.linalg.inv(j_cur)` in the QP loop — hand-rolling only `det` gives a marginal speedup while creating inconsistency between det and inv.

**Draft reply:**

> Noted — this is a real observation but I'd like to defer it. The surrounding block already calls `np.linalg.inv(J0)` and `np.linalg.inv(j_cur)` in the same inner loop, so hand-rolling just `det` saves a small fraction of the per-QP overhead. When we do a pass over the numpy-emission performance (or batch-vectorise it), I'd rather replace det + inv together with a single adjugate-based expansion, applied symmetrically to `J0` and `j_cur`. Tracking as a follow-up rather than mixing micro-optimisation into the correctness fix for #1.

## Posting the replies

```bash
# Replace <ID> and <BODY> per table. Post all five once approved.
gh api --method POST \
  repos/SOSOVSKI/MechDSL/pulls/74/comments/<ID>/replies \
  -f body="<BODY>"
```

Do **not** post until the user approves the drafts — these are visible on a public PR.

## Follow-up fix commit on `plan-b_phase-1-p1-4`

Implements comments #1, #2, #3/#4. No rebase required.

| File | Change |
|------|--------|
| `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | L717: `ctx.emit("J_det = detj / detJ0")`. L733: `ctx.emit("dsigma_geo = sigma @ grad_v.T")`. Update docstring of `_emit_ul_tangent_qp_body` (~L665) — remove "Hadamard" language. |
| `packages/mechdsl-core/tests/golden/generated_ul_svk.py.golden` | Regenerate — the emission now differs on two lines. Use `update-golden` skill; diff should be exactly the two lines above. |
| `packages/mechdsl-core/tests/test_taichi_printer_ul.py` | Update `test_ul_tangent_contains_geometric_stiffness_term` string-match (`sigma @ grad_v.T`). Add `test_ul_tangent_generated_matches_reference` that `exec`s the generated source and compares to `ref_hex8_ul.element_tangent_matvec_ul` on a non-trivial `v` with shear. |

## Verification (after executing this plan)

1. `uv run pytest -m "not slow and not gpu" packages/mechdsl-core/tests/test_taichi_printer_ul.py packages/mechdsl-core/tests/test_ul_equivalence.py packages/mechdsl-core/tests/test_formulation_switching.py` — all green.
2. `uv run pytest -m slow packages/mechdsl-core/tests/` — still green.
3. `gh pr checks 74` — `lint`, `test`, `slow-tests`, `budget-regression` all green (investigate what the current `lint` failure is before merge).
4. `gh api repos/SOSOVSKI/MechDSL/pulls/74/comments --paginate --jq '[.[] | {id, thread_root: (.in_reply_to_id // .id)}] | group_by(.thread_root) | map({root: .[0].thread_root, len: length})'` — each of the 5 root comment IDs has `len >= 2` (has a reply).
5. Spot-check on the PR web UI that replies render and the author can mark threads resolved.
6. After #74 merges, `npx gitnexus analyze` and confirm `gitnexus_detect_changes` shows only the expected files.

## Out of scope for this plan

- Triaging PR #118's red CI (`lint`, `test`, `slow-tests`) and its 1 existing review. Needs its own plan given the +30k-line scope.
- Deciding squash vs merge-commit for #74 — repo history uses merge commits; keep consistent unless maintainer says otherwise.
