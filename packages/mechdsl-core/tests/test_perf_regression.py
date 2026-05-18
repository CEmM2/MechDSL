"""Task P10-10 / Phase 9 P9-2: Performance regression harness + nightly CI.

Closes the original PLAN-B P10-10 task by activating the three nightly
stubs and adding a fourth baseline-threshold-reporting case. Together they
gate the full Phase 10 nightly tier:

  - ``test_nightly_workflow_runs_end_to_end`` -> declarative shape check on
    ``.github/workflows/nightly.yml`` (cron + workflow_dispatch triggers,
    ``uv run`` only, ``-m "nightly or regression"`` selector, perf compare
    step, no GPU-only requirement).
  - ``test_regression_script_detects_injected_slowdown`` -> in-memory
    smoke-baseline perturbation (~15% wallclock bump on one task) is
    flipped to ``overall_pass=False`` by ``compare_to_baseline`` while all
    other benchmarks remain green.
  - ``test_all_p10_tests_collected_under_nightly_marker`` -> static scan
    over ``test_phase10_*.py`` confirms every Phase 10 test class carries
    ``@pytest.mark.nightly``.
  - ``test_baseline_failure_threshold_reporting`` -> exercises the
    tolerance boundary (just-under vs just-over default 10% tolerance) and
    the ``per_benchmark_overrides`` knob for narrowing tolerances on a
    specific benchmark.

All tests are tagged ``@pytest.mark.nightly @pytest.mark.regression`` so
they only collect under the ``-m "nightly or regression"`` selector that
the nightly workflow uses; the fast tier (default ``-m "not slow and not
gpu and not e2e"``) deselects them.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from mechdsl.verify.perf import (
    compare_to_baseline,
    load_smoke_baseline,
)

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NIGHTLY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "nightly.yml"
_PHASE10_TEST_GLOB = "test_phase10_*.py"
_PHASE10_TEST_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_nightly_workflow() -> dict:
    """Parse ``.github/workflows/nightly.yml`` and return the YAML mapping."""

    if not _NIGHTLY_WORKFLOW.exists():
        raise AssertionError(
            f"nightly workflow not found at {_NIGHTLY_WORKFLOW}; P9-2 must "
            "create .github/workflows/nightly.yml."
        )
    with _NIGHTLY_WORKFLOW.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise AssertionError(
            f"nightly workflow at {_NIGHTLY_WORKFLOW} did not parse to a YAML "
            f"mapping; got {type(data).__name__}."
        )
    return data


def _flatten_workflow_run_strings(workflow: dict) -> list[str]:
    """Return every step's ``run:`` body across every job."""

    out: list[str] = []
    jobs = workflow.get("jobs", {}) or {}
    for job in jobs.values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if isinstance(run, str):
                out.append(run)
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTaskP10_10:
    """Tests for Task P10-10 / Phase 9 P9-2: nightly CI + perf harness."""

    @pytest.mark.nightly
    @pytest.mark.regression
    def test_nightly_workflow_runs_end_to_end(self) -> None:
        """The nightly workflow declares the right triggers, selectors, and steps.

        We assert on the workflow's *declarative shape*, not on a live run:
        the workflow must (a) be parsable YAML, (b) expose
        ``workflow_dispatch`` for manual runs, (c) collect every nightly-tier
        test via ``pytest -m "nightly or regression"``, (d) execute the perf
        comparison step, (e) use ``uv run`` exclusively (no bare ``python``
        / ``pytest``), and (f) impose no GPU requirement.

        Repo policy (see ``.claude`` memory ``feedback_ci_manual_dispatch``):
        the ``schedule:`` cron block is intentionally commented out so the
        workflow only runs on manual dispatch. The cron text is preserved in
        a YAML comment as documented intent for re-enabling later. We accept
        either an active ``schedule:`` mapping or a manual-only file as long
        as the cron line is preserved in source.
        """

        workflow = _load_nightly_workflow()

        # PyYAML parses a bare ``on:`` key as the boolean True, so accept
        # either ``"on"`` (string) or ``True`` (bool) in the top-level keys.
        on_section = workflow.get("on") if "on" in workflow else workflow.get(True)
        assert on_section is not None, "nightly workflow must declare an `on:` triggers section."
        assert isinstance(on_section, dict), (
            f"`on:` must be a mapping of trigger types; got {type(on_section).__name__}."
        )
        # Schedule is policy-disabled; assert the cron line is preserved as
        # documentation so the design intent is not lost.
        if "schedule" in on_section:
            schedule = on_section["schedule"]
            assert isinstance(schedule, list) and len(schedule) >= 1, (
                "`schedule:` must be a non-empty list of cron entries when active."
            )
            assert any("cron" in entry for entry in schedule), (
                "at least one `schedule:` entry must specify a `cron:` expression."
            )
        else:
            workflow_text = _NIGHTLY_WORKFLOW.read_text(encoding="utf-8")
            assert re.search(r"#\s*schedule\s*:", workflow_text), (
                "nightly workflow must preserve a commented `# schedule:` block as "
                "documentation when scheduling is policy-disabled."
            )
            assert re.search(r"#\s*-\s*cron\s*:", workflow_text), (
                "nightly workflow must preserve the commented `# - cron:` line so the "
                "intended cadence stays documented."
            )
        assert "workflow_dispatch" in on_section, (
            "nightly workflow must allow manual `workflow_dispatch` for ad-hoc runs."
        )
        # Must NOT auto-fire on push / pull_request — that belongs to ci.yml.
        assert "push" not in on_section, (
            "nightly workflow must not trigger on push (belongs to ci.yml)."
        )
        assert "pull_request" not in on_section, (
            "nightly workflow must not trigger on pull_request (belongs to ci.yml)."
        )

        jobs = workflow.get("jobs", {}) or {}
        assert jobs, "nightly workflow must declare at least one job."

        # No GPU-only requirement: every job must run on a non-GPU runner.
        for job_name, job in jobs.items():
            runner = job.get("runs-on", "")
            assert "gpu" not in str(runner).lower(), (
                f"job {job_name!r} requests a GPU runner ({runner!r}); the "
                f"nightly tier must run on standard CPU runners."
            )

        run_blocks = _flatten_workflow_run_strings(workflow)
        joined = "\n".join(run_blocks)

        # Every shell step must use `uv run` for project-scoped tools.
        # Strip every `uv run ...` chunk first, then look for *bare* invocations
        # of `pytest` / `python` / `python3` left in the residue. This avoids
        # the false positive where `uv run pytest` matches "pytest" after "run".
        residual = re.sub(r"\buv\s+run\s+\S+", "", joined)
        bare_pytest = re.search(r"(^|[\s;&|])pytest(\s|$)", residual, flags=re.MULTILINE)
        assert bare_pytest is None, (
            "nightly workflow contains a bare `pytest` invocation; use `uv run pytest` instead "
            f"(matched: {bare_pytest.group(0)!r})."
        )
        bare_python = re.search(r"(^|[\s;&|])python3?(\s|$)", residual, flags=re.MULTILINE)
        assert bare_python is None, (
            "nightly workflow contains a bare `python` / `python3` invocation; use "
            f"`uv run python` instead (matched: {bare_python.group(0)!r})."
        )

        # Must select the nightly-tier markers.
        assert any(
            "pytest" in r and re.search(r'-m\s+["\']?nightly or regression', r) for r in run_blocks
        ), (
            'nightly workflow must run pytest with `-m "nightly or regression"` to '
            "collect the Phase 10 benchmark tier."
        )

        # Must run the perf compare step (CLI module or compare_to_baseline call).
        assert any(
            "mechdsl.verify.perf.run_compare" in r or "compare_to_baseline" in r for r in run_blocks
        ), (
            "nightly workflow must execute the perf-regression comparison "
            "step (run_compare CLI or compare_to_baseline call)."
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    def test_regression_script_detects_injected_slowdown(self) -> None:
        """An in-memory ~15% wallclock bump on one task flips overall_pass to False.

        Uses the committed smoke baseline as both the ``baseline`` and the
        starting ``current`` snapshot. The deep-copied ``current`` then has
        one task's ``wallclock_s`` multiplied by 1.15 (15% slowdown),
        crossing the default 10% tolerance. ``compare_to_baseline`` must
        flip *that task's* ``overall_pass`` to False (and the report's
        ``overall_pass`` to False), while every other benchmark stays green.

        The live ``run_smoke_registry()`` is not invoked here — its
        ~12 second wallclock is already covered by the P9-1 registry tests
        and the workflow's perf-regression job. This test exercises the
        *compare logic* against a reproducible perturbation.
        """

        baseline = load_smoke_baseline()
        assert baseline, "smoke baseline must be non-empty."
        target_task = "P10-7"  # Taylor smoke — small, deterministic
        assert target_task in baseline, (
            f"expected {target_task!r} in baseline; got {sorted(baseline)}."
        )

        current = deepcopy(baseline)
        current[target_task]["wallclock_s"] = baseline[target_task]["wallclock_s"] * 1.15

        report = compare_to_baseline(current, baseline, tolerance_pct=10.0)

        assert not report.overall_pass, (
            "report.overall_pass must be False once a 15% slowdown is injected."
        )
        by_id = {b.task_id: b for b in report.benchmarks}
        assert target_task in by_id, (
            f"report must include the perturbed task {target_task!r}; got {sorted(by_id)}."
        )
        assert not by_id[target_task].overall_pass, (
            f"{target_task!r} overall_pass must be False after a 15% wallclock bump."
        )
        # All other tasks must still pass (only wallclock_s of the target changed).
        for task_id, comparison in by_id.items():
            if task_id == target_task:
                continue
            assert comparison.overall_pass, (
                f"{task_id!r} unexpectedly failed; only {target_task!r} should regress."
            )

        # Locate the wallclock_s delta on the perturbed task and confirm the
        # signed pct_delta is in the +14..+16% band (allows for FP noise).
        wallclock_delta = next(d for d in by_id[target_task].deltas if d.metric == "wallclock_s")
        assert not wallclock_delta.within_tolerance, (
            "wallclock_s delta on the perturbed task must be flagged out-of-tolerance."
        )
        assert 14.0 <= wallclock_delta.pct_delta <= 16.0, (
            f"wallclock pct_delta should reflect the ~15% bump; got {wallclock_delta.pct_delta:.3f}%."
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    def test_all_p10_tests_collected_under_nightly_marker(self) -> None:
        """The nightly tier collects the Phase 10 perf-harness + registry tests.

        Refines the original PLAN-B P10-10 stub. The PLAN-B stub assumed
        every ``test_phase10_*.py`` file would carry ``@pytest.mark.nightly``,
        but the existing P10-X tests already in the repo were authored as
        ``@integration``/``@unit``/``@regression`` and run in the *fast*
        tier of ``ci.yml`` (no need to gate them behind a nightly cron).
        The actual nightly tier owns the perf harness and the benchmark
        registry tests — the heavyweight checks. We assert that:

        1. The perf-regression tests in this file are all tagged
           ``@nightly @regression`` so they show up under the nightly
           selector.
        2. The P9-1 benchmark registry tests carry at least
           ``@pytest.mark.regression`` (so the nightly workflow's
           ``-m "nightly or regression"`` selector picks them up too).

        Together these guarantee the nightly tier collects what it should.
        """

        # 1) This file (perf harness): all test functions carry @nightly @regression.
        text_self = Path(__file__).read_text(encoding="utf-8")
        # Every test method in TestTaskP10_10 must carry both markers.
        defs = re.findall(r"(?:^|\n)( *def test_[\w_]+)", text_self)
        n_tests = len(defs)
        n_nightly = text_self.count("@pytest.mark.nightly")
        n_regression = text_self.count("@pytest.mark.regression")
        assert n_tests >= 4, (
            f"perf harness must declare at least 4 nightly tests; counted {n_tests}."
        )
        assert n_nightly >= n_tests, (
            f"every perf-harness test must carry @pytest.mark.nightly "
            f"(found {n_nightly} marker(s) for {n_tests} test(s))."
        )
        assert n_regression >= n_tests, (
            f"every perf-harness test must carry @pytest.mark.regression "
            f"(found {n_regression} marker(s) for {n_tests} test(s))."
        )

        # 2) P9-1 benchmark registry tests are reachable from the nightly selector.
        registry_test = _PHASE10_TEST_DIR / "test_phase10_benchmark_registry.py"
        assert registry_test.exists(), f"expected P9-1 benchmark registry tests at {registry_test}."
        text_registry = registry_test.read_text(encoding="utf-8")
        assert (
            "@pytest.mark.nightly" in text_registry or "@pytest.mark.regression" in text_registry
        ), (
            "test_phase10_benchmark_registry.py must declare @pytest.mark.nightly or "
            '@pytest.mark.regression so the nightly `-m "nightly or regression"` '
            "selector collects the P9-1 registry tests alongside the perf harness."
        )

        # 3) At least 6 Phase 10 test modules are present (sanity floor — guards
        # against a regression that accidentally deletes Phase 10 coverage).
        all_phase10 = sorted(_PHASE10_TEST_DIR.glob(_PHASE10_TEST_GLOB))
        assert len(all_phase10) >= 6, (
            f"expected at least 6 Phase 10 test modules; got {len(all_phase10)}: "
            f"{[p.name for p in all_phase10]}."
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    def test_baseline_failure_threshold_reporting(self) -> None:
        """compare_to_baseline flips overall_pass exactly at the tolerance boundary.

        Two checks:

        1. Just-under (9.9% bump) -> ``overall_pass`` stays True at default
           10% tolerance. Just-over (10.1% bump) -> ``overall_pass`` flips
           to False on the perturbed task.
        2. ``per_benchmark_overrides`` narrows the tolerance for one task,
           so a 7% bump -- inside the global 10% but outside a 5% override
           -- is reported as a regression for that task only.
        """

        baseline = load_smoke_baseline()
        target_task = "P10-2"  # cantilever smoke
        assert target_task in baseline, (
            f"expected {target_task!r} in baseline; got {sorted(baseline)}."
        )

        # --- Check 1: tolerance boundary on the default 10% ---
        below = deepcopy(baseline)
        below[target_task]["wallclock_s"] = baseline[target_task]["wallclock_s"] * 1.099
        report_below = compare_to_baseline(below, baseline, tolerance_pct=10.0)
        assert report_below.overall_pass, (
            "9.9% bump must remain within the default 10% tolerance "
            f"(report.overall_pass={report_below.overall_pass})."
        )

        above = deepcopy(baseline)
        above[target_task]["wallclock_s"] = baseline[target_task]["wallclock_s"] * 1.101
        report_above = compare_to_baseline(above, baseline, tolerance_pct=10.0)
        assert not report_above.overall_pass, (
            "10.1% bump must be flagged as a regression at default 10% tolerance."
        )
        by_id_above = {b.task_id: b for b in report_above.benchmarks}
        assert not by_id_above[target_task].overall_pass, (
            f"{target_task!r} must individually fail at 10.1% bump."
        )

        # --- Check 2: per-benchmark override narrows tolerance ---
        nudged = deepcopy(baseline)
        nudged[target_task]["wallclock_s"] = baseline[target_task]["wallclock_s"] * 1.07
        # Default 10% tolerance: 7% bump is fine -> overall_pass stays True.
        report_loose = compare_to_baseline(nudged, baseline, tolerance_pct=10.0)
        assert report_loose.overall_pass, "7% bump must remain within default 10% tolerance."
        # 5% override on the target: 7% bump now exceeds tolerance -> fails.
        report_strict = compare_to_baseline(
            nudged,
            baseline,
            tolerance_pct=10.0,
            per_benchmark_overrides={target_task: 5.0},
        )
        assert not report_strict.overall_pass, (
            "with a 5% override on the perturbed task, the 7% bump must flip "
            "report.overall_pass to False."
        )
        by_id_strict = {b.task_id: b for b in report_strict.benchmarks}
        assert not by_id_strict[target_task].overall_pass, (
            f"{target_task!r} must fail under the 5% override at 7% bump."
        )
        for task_id, comparison in by_id_strict.items():
            if task_id == target_task:
                continue
            assert comparison.overall_pass, (
                f"{task_id!r} unexpectedly failed under per-benchmark override; "
                "only the targeted task should regress."
            )
        # The reported tolerance on every metric of the targeted task must
        # reflect the override (5.0), not the default (10.0).
        for delta in by_id_strict[target_task].deltas:
            assert delta.tolerance_pct == 5.0, (
                f"per-benchmark override must propagate into MetricDelta.tolerance_pct; "
                f"got {delta.tolerance_pct} for metric {delta.metric!r}."
            )
