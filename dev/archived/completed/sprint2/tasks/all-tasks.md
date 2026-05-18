# Sprint 2 — J2 Plasticity Runtime & Verification Hardening

Generated on: 2026-04-04
Plan source: `dev/plans/sprint2.md`

## Task Index

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-T1 | 1 | Fix emit_main E/nu → Lamé conversion | — | P1-T5, P1-T6 | 21–25 |
| P1-T2 | 1 | Implement convected coordinate functions | — | P1-T3, P1-T4 | 27–32 |
| P1-T3 | 1 | Write convected coordinate tests | P1-T2 | — | 34–39 |
| P1-T4 | 1 | Update convected exports | P1-T2 | — | 41–43 |
| P1-T5 | 1 | Regenerate golden files after emit_main fix | P1-T1 | P4-T7 | 45–47 |
| P1-T6 | 1 | Write emit_main Lamé conversion test | P1-T1 | — | 49–50 |
| P2-T1 | 2 | Implement patch_test_reference() | — | P2-T5, P3-T4 | 60–64 |
| P2-T2 | 2 | Implement rigid_body_reference() | — | P2-T5, P3-T4 | 66–69 |
| P2-T3 | 2 | Implement cantilever_euler_bernoulli() | — | P2-T5 | 71–74 |
| P2-T4 | 2 | Implement uniaxial_tension_hardening() | — | P2-T5, P4-T5 | 76–80 |
| P2-T5 | 2 | Write analytical solution tests | P2-T1, P2-T2, P2-T3, P2-T4 | — | 82–87 |
| P2-T6 | 2 | Implement frontend.build_context() | — | P2-T7, P2-T8 | 89–94 |
| P2-T7 | 2 | Implement build_context validation | P2-T6 | P2-T8 | 96–99 |
| P2-T8 | 2 | Write frontend tests | P2-T6, P2-T7 | — | 101–106 |
| P3-T1 | 3 | Implement check_convergence_rate() | — | P3-T3 | 116–120 |
| P3-T2 | 3 | Implement MMS driver | — | P3-T3 | 122–129 |
| P3-T3 | 3 | Write convergence rate test | P3-T1, P3-T2 | — | 131–135 |
| P3-T4 | 3 | Implement run_patch_test() and run_rigid_body_test() | P2-T1, P2-T2 | P3-T5 | 137–146 |
| P3-T5 | 3 | Write patch test | P3-T4 | — | 148–152 |
| P4-T1 | 4 | Audit J2 constitutive emission | — | P4-T5 | 162–172 |
| P4-T2 | 4 | Validate FD tangent for J2 | — | P4-T5 | 174–178 |
| P4-T3 | 4 | Verify history field emission | — | P4-T5 | 180–185 |
| P4-T4 | 4 | Verify numerical safeguards | — | P4-T5 | 187–193 |
| P4-T5 | 4 | Create test_e2e_plastic.py | P4-T1, P4-T2, P4-T3, P4-T4, P2-T4 | P4-T6 | 195–208 |
| P4-T6 | 4 | Compare generated vs reference | P4-T5 | P4-T7 | 210–214 |
| P4-T7 | 4 | Validate/update golden file | P4-T6, P1-T5 | — | 216–219 |
| P5-T1 | 5 | Audit symbolic (S1-S9) + parser (P1-P6) | P1-T3, P2-T8 | P5-T4 | 229–234 |
| P5-T2 | 5 | Audit IR (M1-M6), Element (E1-E6), Einsum (N1-N5) | — | P5-T4 | 236–240 |
| P5-T3 | 5 | Audit Backend (T1-T4), BC (B1-B5), Artifact (A1-A3), Emission (C1-C3) | P4-T6 | P5-T4 | 242–246 |
| P5-T4 | 5 | Create verification matrix | P5-T1, P5-T2, P5-T3 | — | 248–252 |
| P6-T1 | 6 | Full regression suite | P5-T4 | P6-T2 | 262–265 |
| P6-T2 | 6 | Verify sprint exit criteria | P6-T1 | P6-T3 | 267–278 |
| P6-T3 | 6 | Sprint 2 completion handoff | P6-T2 | — | 280–281 |
