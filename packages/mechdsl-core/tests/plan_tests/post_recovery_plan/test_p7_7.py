"""Tests for Task P7-7: add CI baseline-stability smoke job.

Acceptance:
1. .github/workflows/*.yml contains a job confirming the algo2code
   workspace install yields zero import failures.
2. Workflow YAML parses (syntactically valid).
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".github" / "workflows").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _workflow_files() -> list[Path]:
    root = _repo_root()
    wf = root / ".github" / "workflows"
    return sorted(wf.glob("*.yml")) + sorted(wf.glob("*.yaml"))


class TestTaskP7_7:
    @pytest.mark.integration
    def test_baseline_stability_job_present(self) -> None:
        """At least one workflow file mentions a baseline-stability /
        algo2code-import smoke job."""
        found = False
        for f in _workflow_files():
            text = f.read_text(encoding="utf-8")
            if (
                "baseline-stability" in text
                or "baseline_stability" in text
                or ("algo2code" in text and "import" in text and "collect-only" in text)
            ):
                found = True
                break
        assert found, (
            "no workflow under .github/workflows/ adds the post_recovery_plan "
            "P7-7 baseline-stability smoke job"
        )

    @pytest.mark.integration
    def test_all_workflow_yaml_parses(self) -> None:
        if _yaml is None:
            pytest.skip("PyYAML not available; workflow YAML parse skipped")
        for f in _workflow_files():
            text = f.read_text(encoding="utf-8")
            try:
                _yaml.safe_load(text)
            except _yaml.YAMLError as exc:
                pytest.fail(f"{f.name} failed YAML parse: {exc}")
