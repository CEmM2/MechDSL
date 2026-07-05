"""Plan-tests for Task P4-3: document release ordering (cross-repo build edge).

Plan: dev/plans/mfront_cycleM0.md (lines 120-122) — MFront-mimic Cycle M0, Phase 4.
Deliverables under test:
  * MechDSL: RELEASE_ORDER.md (repo root) — the 3-step release runbook.
  * NumerixWeave: libs/ticonstit/src/ticonstit/generated/GENERATED.md — committed-
    artifacts seam note linking back to RELEASE_ORDER.md.

The MechDSL-checkable piece is that RELEASE_ORDER.md exists and documents the three
steps (compile -> commit artifacts -> NumerixWeave verifies source_hash). The DAG
guard (python tools/check_dependency_graph.py exits 0; no mechdsl/sympy runtime
import) runs in NumerixWeave (R3), so that half is a cross-repo skip marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]


class TestTaskP4_3:
    """Release-ordering docs + cross-repo DAG guard. AC covered: 1-4."""

    @pytest.mark.integration
    def test_release_order_md_exists_with_three_steps(self) -> None:
        """Verifies: MechDSL RELEASE_ORDER.md exists and lists the 3 release steps.
        AC1: exact CLI commands for compile -> commit artifacts -> verify source_hash.
        Passes when: RELEASE_ORDER.md is present and names all three steps."""
        pytest.skip("stub — implement after Task P4-3")

    @pytest.mark.integration
    def test_dependency_graph_guard_runs_in_numerixweave(self) -> None:
        """Verifies (cross-repo): NumerixWeave stays free of any mechdsl/sympy runtime
        import — python tools/check_dependency_graph.py exits 0.
        Passes when: the DAG guard passes in NumerixWeave (run there, not here)."""
        pytest.skip("stub — cross-repo DAG guard; runs in NumerixWeave (R3)")
