"""One-shot smoke baseline regenerator.

Run via::

    uv run pytest packages/mechdsl-core/tests/test_phase10_benchmark_registry.py \
        --regen-baseline

or manually::

    uv run python -m mechdsl.verify.perf.regenerate_baseline > tests/golden/perf/baseline_smoke.json

Honors golden-file discipline: regen requires explicit intent, the script
prints to stdout instead of overwriting the committed file.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from mechdsl.verify.perf import BenchmarkRegistry, run_smoke_registry


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def regenerate(*, tolerance_pct_default: float = 10.0) -> dict[str, object]:
    """Run every spec under its smoke profile and pack into the baseline shape."""

    registry = BenchmarkRegistry.default()
    with tempfile.TemporaryDirectory(prefix="perf_regen_") as td:
        results = run_smoke_registry(registry, tmp_path=Path(td))
    payload: dict[str, object] = {
        "generated_on": _dt.datetime.now(_dt.UTC).date().isoformat(),
        "commit": _git_sha(),
        "tolerance_pct_default": tolerance_pct_default,
        "tasks": results,
    }
    return payload


def main() -> int:
    payload = regenerate()
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
