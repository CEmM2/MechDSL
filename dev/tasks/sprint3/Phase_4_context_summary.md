# Phase 4 Context Summary: Full Pipeline Test & CI Nightly

**Plan:** `dev/plans/sprint3.md`
**Original plan phase name:** Phase 4

## Conventions
- 6 compiler layers: frontend -> symbolic -> mechanics IR -> element IR/lowering -> einsum optimizer -> Taichi codegen
- CI tiers: fast (every commit, < 2 min), slow (every PR, < 10 min), nightly e2e (< 60 min)
- Artifact bundle completeness: problem_ir_dict, element_ir_summary, contraction_plans (3), emitted_source

## Key Principles
- Full pipeline test exercises ALL layers, not just codegen
- CI tiers separate fast feedback from comprehensive validation
- Benchmark failures create issues (non-blocking); compiler failures block merge

## Pre-resolved Design Decisions
- Reuse _make_elastic_problem_ir() / _make_plastic_problem_ir() patterns from test_e2e.py
- Nightly cron: '0 3 * * *' (3 AM UTC)
- Failure protocol via actions/github-script@v7 with benchmark-regression label

## Allowed Deviations
- None

## Downstream Impact
- CI configuration affects all future development workflow
- test_full_pipeline.py becomes the ultimate regression test
