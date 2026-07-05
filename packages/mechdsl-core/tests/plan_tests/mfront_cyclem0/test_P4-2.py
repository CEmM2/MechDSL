"""Plan-tests for Task P4-2: equivalence gate (emitted SwiftVoce vs Cycle 0 class).

Plan: dev/plans/mfront_cycleM0.md (lines 117-119) — MFront-mimic Cycle M0, Phase 4.
Deliverable under test: NumerixWeave
libs/ticonstit/tests/generated/test_swift_voce_equivalence.py.

⚠️ CROSS-REPO / R3: the equivalence gate compares the *emitted* SwiftVoce against
Cycle 0's hand-authored SwiftVoce (and, at K=0, VoceHardeningModel) to rtol=1e-10.
Both classes are Taichi @ti.func code that lives in NumerixWeave and can only be
instantiated inside the NumerixWeave uv venv — importing ticonstit eagerly loads
Taichi (Cycle 0 P1-2). It therefore CANNOT run inside the MechDSL venv, so this
MechDSL-side entry is a documentation/skip marker only. The real assertions live in
the NumerixWeave test file above and are exercised by:

    cd /Users/shmuelosovski/Github/Personal/NumerixWeave \\
      && uv run pytest libs/ticonstit/tests/generated/test_swift_voce_equivalence.py -v

The comparison is NUMERICAL (rtol=1e-10), not byte/AST — batched CSE reorganizes
derivative structure (Phase-2 handoff note 2) while staying numerically equal.
"""

from __future__ import annotations

import pytest


class TestTaskP4_2:
    """Equivalence gate marker. Real gate runs in NumerixWeave venv. AC covered: 1-4."""

    @pytest.mark.integration
    def test_equivalence_gate_runs_in_numerixweave(self) -> None:
        """Verifies (cross-repo): emitted SwiftVoce matches the hand-authored class
        for R/H/Q at N=20 sample points, at K=0 matches VoceHardeningModel, and the
        source_hash is stable across two compile runs — all to rtol=1e-10.
        Passes when: the NumerixWeave equivalence test passes (run there, not here)."""
        pytest.skip("stub — cross-repo gate; runs in NumerixWeave .venv (R3)")
