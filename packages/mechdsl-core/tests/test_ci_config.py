"""CI configuration tests for Sprint 3 P4-2 / P4-3."""

from __future__ import annotations

from pathlib import Path

import yaml

_CI_WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github/workflows/ci.yml"


def _load_ci_workflow() -> dict:
    return yaml.safe_load(_CI_WORKFLOW_PATH.read_text())


class TestCIConfig:
    """Tests for Task P4-2: Add nightly e2e schedule to CI.

    Acceptance criteria covered:
      1. CI has schedule trigger with cron expression
      2. e2e-benchmarks job runs pytest -m e2e
      3. Fast tests exclude both slow and e2e
      4. Slow tests exclude e2e
    """

    def test_ci_yaml_is_valid(self):
        """Parse .github/workflows/ci.yml and verify the YAML is syntactically valid."""
        workflow = _load_ci_workflow()

        assert isinstance(workflow, dict)
        assert isinstance(workflow["jobs"], dict)

    def test_ci_tier_filters_are_correct(self):
        """Verify ci.yml job filters separate fast / slow / nightly e2e correctly.

        Repo policy (see ``.claude`` memory ``feedback_ci_manual_dispatch``):
        ``schedule:`` and ``push:`` / ``pull_request:`` triggers are kept
        commented out so CI only fires on manual dispatch. Accept either an
        active schedule mapping or a commented-out block as long as the cron
        text remains preserved as documentation.
        """
        import re as _re

        workflow = _load_ci_workflow()
        trigger = workflow.get("on", workflow.get(True))

        assert trigger is not None
        if isinstance(trigger, dict) and "schedule" in trigger:
            assert trigger["schedule"] == [{"cron": "0 3 * * *"}]
        else:
            workflow_text = _CI_WORKFLOW_PATH.read_text()
            assert _re.search(r"#\s*schedule\s*:", workflow_text), (
                "ci.yml must preserve a commented `# schedule:` block as "
                "documentation when scheduling is policy-disabled."
            )
            assert _re.search(r"#.*cron\s*:\s*['\"]0 3 \* \* \*['\"]", workflow_text), (
                "ci.yml must preserve the commented `0 3 * * *` cron line so the "
                "intended cadence stays documented."
            )

        jobs = workflow["jobs"]

        test_steps = jobs["test"]["steps"]
        assert any(
            step.get("run")
            == 'uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu and not e2e" --tb=short -q'
            for step in test_steps
        )
        assert any(
            step.get("run")
            == 'uv run pytest packages/algo2code/tests/ -m "not slow and not gpu and not e2e" --tb=short -q'
            for step in test_steps
        )

        slow_steps = jobs["slow-tests"]["steps"]
        assert any(
            step.get("run")
            == 'uv run pytest packages/mechdsl-core/tests/ -m "slow and not e2e" --tb=short -q'
            for step in slow_steps
        )
        algo2code_slow_step = next(
            step for step in slow_steps if step.get("name") == "Run slow tests (algo2code)"
        )
        assert 'uv run pytest packages/algo2code/tests/ -m "slow and not e2e" --tb=short -q' in (
            algo2code_slow_step.get("run") or ""
        )
        assert 'if [ "$status" -eq 5 ]; then' in (algo2code_slow_step.get("run") or "")

        e2e_steps = jobs["e2e-benchmarks"]["steps"]
        assert jobs["e2e-benchmarks"]["if"] == "github.event_name == 'schedule'"
        assert any(
            step.get("run") == "uv run pytest packages/mechdsl-core/tests/ -m e2e --tb=short -q"
            for step in e2e_steps
        )


class TestCIFailureProtocol:
    """Tests for Task P4-3: Implement failure protocol.

    Acceptance criteria covered:
      1. Benchmark failures create issues instead of blocking merge
      2. Compiler-pass test failures still block merge
    """

    def test_benchmark_step_has_continue_on_error(self):
        """Verify the e2e benchmark step is marked continue-on-error: true.

        Verifies: inside the `e2e-benchmarks` job, the benchmark test step has
            `continue-on-error: true` set, so a failing benchmark does not fail
            the job and block merges.
        Acceptance criterion: "Benchmark failures create issues instead of blocking merge".
        Passes when: the parsed ci.yml shows continue-on-error: true on the relevant step.
        """
        workflow = _load_ci_workflow()
        e2e_steps = workflow["jobs"]["e2e-benchmarks"]["steps"]

        benchmark_step = next(
            step for step in e2e_steps if step.get("name") == "Run e2e benchmarks (mechdsl-core)"
        )

        assert benchmark_step["continue-on-error"] is True
        assert (
            benchmark_step["run"]
            == "uv run pytest packages/mechdsl-core/tests/ -m e2e --tb=short -q"
        )

    def test_github_script_issue_creation_step_present(self):
        """Verify a follow-up step creates a GitHub issue on failure.

        Verifies: the `e2e-benchmarks` job contains a step using
            `actions/github-script@v7` that runs on failure and uses the
            `benchmark-regression` label when creating the issue.
        Acceptance criterion: "Benchmark failures create issues instead of blocking merge".
        Passes when: parsed ci.yml contains a step with `uses: actions/github-script@v7`,
            `if: failure()`, and the label string `benchmark-regression`.
        """
        workflow = _load_ci_workflow()
        job = workflow["jobs"]["e2e-benchmarks"]
        e2e_steps = job["steps"]

        assert job["permissions"] == {"contents": "read", "issues": "write"}

        issue_step = next(
            step for step in e2e_steps if step.get("uses") == "actions/github-script@v7"
        )

        assert "failure()" in issue_step["if"]
        assert issue_step["continue-on-error"] is True

        script = issue_step["with"]["script"]
        assert "benchmark-regression" in script
        assert "github.rest.issues.createLabel" in script
        assert "github.rest.issues.create({" in script
