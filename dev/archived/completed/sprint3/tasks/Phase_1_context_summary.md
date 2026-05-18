# Phase 1 Context Summary: Cantilever Upgrade + MMS Extension + Marker Cleanup

**Plan:** `dev/plans/sprint3.md`
**Original plan phase name:** Phase 1

## Conventions
- Test markers: `@pytest.mark.e2e` for nightly benchmarks, `@pytest.mark.slow` for JIT/heavy tests
- Material parameters: E=1000, nu=0.3 for cantilever (soft material for visible deflection)
- Euler-Bernoulli reference: delta = P*L^3 / (3*E*I), I = b*h^3/12
- MMS manufactured displacement: u*(X) = A*sin(pi*X1/L)*cos(pi*X2/L)*sin(pi*X3/L)

## Key Principles
- Mesh refinement drives accuracy: 40x8x4 needed for 5% EB tolerance (coarse 4x2x1 gives 0.25-2.0x)
- MMS convergence requires proper 2x refinement ratios: [2,4,8,16] not [2,3,4]
- SVK in Total Lagrangian gives E=0 for pure rotation regardless of angle (frame-indifferent in reference config)

## Pre-resolved Design Decisions
- Keep existing coarse-mesh tests as fast regression checks
- Generate mesh on-the-fly (no .npz files) using generate_hex8_mesh
- Use cg_max_iter=5000 for 40x8x4 mesh
- Fallback to [2,4,8] if 16^3 MMS mesh is prohibitively slow

## Allowed Deviations
- MMS may use [2,4,8] instead of [2,4,8,16] if 16^3 is too slow

## Downstream Impact
- All e2e-marked tests feed into Phase 4 CI nightly tier
- Phase 4 P4-1 (full pipeline test) depends on all Phase 1 tasks
