"""P2-3 verification — spot-check three recovery-plan task JSONs.

P2-3 inspects the JSONs Plan-2-Tasks produced from the amended recovery
plan. Spot-check by *content*, not just by ID: in case Plan-2-Tasks
splits or merges Phase 3 differently, the ProblemIR-enrichment task may
not literally be `P3-1`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
RP_JSON = REPO_ROOT / "dev" / "tasks" / "recovery_plan_latex_contract" / "json"

STATUS_VOCAB = {"done", "deferred", "implemented-via-substitute", "not_started"}


def _require_jsons() -> list[Path]:
    if not RP_JSON.is_dir():
        pytest.skip(
            "recovery_plan_latex_contract/json/ not yet generated — run "
            "/Aut_Faciam tasks dev/plans/recovery_plan_latex_contract.md"
        )
    files = sorted(RP_JSON.glob("P*.json"))
    if not files:
        pytest.skip("recovery_plan_latex_contract/json/ has no P*.json files yet")
    return files


def _flatten(data: object) -> str:
    """Cheap stringification of a JSON document for substring checks."""
    return json.dumps(data, ensure_ascii=False)


class TestTaskP2_3:
    """
    Tests for Task P2-3: Spot-check three generated task JSONs
    Acceptance criteria covered: 1, 2, 3, 4, 5
    """

    @pytest.mark.audit
    def test_status_vocabulary_task_present(self) -> None:
        files = _require_jsons()
        # find the Phase-1 task whose acceptance/implementation mentions all four
        # status values (the recovery-plan namespace's tracker-vocabulary task).
        for f in files:
            if not f.name.startswith("P1-"):
                continue
            blob = _flatten(json.loads(f.read_text(encoding="utf-8")))
            if all(v in blob for v in STATUS_VOCAB):
                return
        pytest.fail(
            f"no Phase-1 recovery-plan task references all four status values "
            f"{sorted(STATUS_VOCAB)}"
        )

    @pytest.mark.audit
    def test_compile_latex_facade_task_present(self) -> None:
        files = _require_jsons()
        # find the Phase-2 task whose deliverables list mechdsl/__init__.py and
        # frontend/__init__.py and whose acceptance mentions LaTeX-string entry.
        for f in files:
            if not f.name.startswith("P2-"):
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            deliverables = " ".join(data.get("deliverables", []))
            accept = " ".join(data.get("acceptance_criteria", []))
            if (
                "mechdsl/__init__.py" in deliverables
                and "frontend/__init__.py" in deliverables
                and re.search(r"latex", accept, flags=re.IGNORECASE)
            ):
                return
        pytest.fail(
            "no Phase-2 recovery-plan task lists both __init__ files in deliverables "
            "with a LaTeX-string acceptance criterion"
        )

    @pytest.mark.audit
    def test_problem_ir_serialization_task_present(self) -> None:
        files = _require_jsons()
        # find the Phase-3 task whose deliverables include mechanics_ir.py and
        # whose implementation_steps explicitly add to_dict/from_dict to ProblemIR.
        for f in files:
            if not f.name.startswith("P3-"):
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            deliverables = " ".join(data.get("deliverables", []))
            steps = " ".join(data.get("implementation_steps", []))
            if (
                "mechanics_ir.py" in deliverables
                and "ProblemIR" in steps
                and ("to_dict" in steps or "from_dict" in steps)
            ):
                return
        pytest.fail(
            "no Phase-3 recovery-plan task lists mechanics_ir.py in deliverables "
            "with ProblemIR.to_dict/from_dict in implementation_steps"
        )
