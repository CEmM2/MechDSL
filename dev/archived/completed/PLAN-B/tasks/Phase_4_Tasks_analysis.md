# Phase 4 Tasks Analysis

Branch: `plan-b_phase-4` (off `plan-b_phase-3`; all Phase 1-3 infrastructure present)

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined | Blocked By | Blocks | Model tier |
|---------|-------|------------------|------------|----------|------------|--------|-----------|
| P4-1 | Neo-Hookean hyperelastic model | 2 | 2 | 4 | P1-1 (done) | P4-5, P10-2 | Sonnet OK |
| P4-2 | Mooney-Rivlin hyperelastic model | 2 | 2 | 4 | P1-1 (done) | P4-5 | Sonnet OK |
| P4-3 | Ogden hyperelastic (spectral + repeated eigenvalues) | 4 | 4 | 8 | P1-1 (done) | P4-5 | **Opus only** |
| P4-4 | HGO anisotropic (per-element fiber directions) | 3 | 3 | 6 | P1-1 (done) | P4-5, P10-9 | Sonnet / Opus |
| P4-5 | AD oracle + uniaxial acceptance | 3 | 2 | 5 | P4-1..P4-4 | — | Sonnet / Opus |

## Execution order

Sequential: P4-1 → P4-2 → P4-3 → P4-4 → P4-5.

Rationale for not parallelising P4-1/P4-2: although file scopes are disjoint, **P4-2 AC-2 requires NH to be importable** (`MR at C2=0 == NH with mu=2*C1`). Running them sequentially keeps the test oracle deterministic and avoids branch-merge coordination under auto mode. Marginal time savings from parallel don't outweigh the clarity cost.

## Pre-execution warnings (from prior gate history + context summary)

1. **Ogden spectral tangent (P4-3) — HIGH risk.** Repeated eigenvalues give 0/0. Context summary explicitly flags silent divide-by-zero as HIGH-risk; must use L'Hopital limit from Holzapfel §6.5 when `|lambda_i - lambda_j| < 1e-6`. Use `numpy.linalg.eigh` (symmetric), not `eig` (general).
2. **AD oracle near-degenerate eigenvalues (P4-5).** Per task risk note: skip states with `|lambda_i - lambda_j| < 1e-4` for Ogden oracle; document the exclusion.
3. **Hyperelastic tangent pattern is `sympy.diff(Psi)`, NOT Simo-Hughes Box 3.5.** Phase 3 (dissipative) used the algorithmic tangent pattern; Phase 4 is non-dissipative — use symbolic differentiation of Psi directly. Handoff_Phase_4.md calls this out explicitly.
4. **Unicode en-dash trap (from CI memory).** Prefer plain hyphens in docstrings/comments to avoid RUF002/RUF003 in pre-commit.
5. **Budget reference-solver time for new goldens** (from memory). Phase 4 doesn't introduce new goldens but P4-5 uniaxial FD comparisons at 100 states can be slow — cap N where sensible.
