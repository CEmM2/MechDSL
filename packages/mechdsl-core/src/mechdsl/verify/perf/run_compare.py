"""Smoke-registry runner + baseline comparison CLI.

This module is the canonical entry point invoked by nightly CI to enforce the
"no >10% regression vs the committed baseline" gate (P9-2 acceptance
criterion). It is also useful as a local dev verification step:

::

    uv run python -m mechdsl.verify.perf.run_compare --output report.json

Behaviour
---------
1. Run :func:`mechdsl.verify.perf.run_smoke_registry` over the default
   :class:`~mechdsl.verify.perf.BenchmarkRegistry`.
2. Load the committed smoke baseline from
   ``packages/mechdsl-core/tests/golden/perf/baseline_smoke.json``.
3. Call :func:`mechdsl.verify.perf.compare_to_baseline` (default tolerance
   10% per metric).
4. If ``--output`` is supplied, write the
   :class:`~mechdsl.verify.perf.ComparisonReport` JSON to that path; else
   print it to stdout.
5. Return exit code ``0`` if ``report.overall_pass`` is ``True``, else ``1``.

The CLI is intentionally minimal — it has no dependencies beyond the rest of
:mod:`mechdsl.verify.perf` so it is safe to call from inline workflow Python.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from mechdsl.verify.perf import (
    BenchmarkRegistry,
    compare_to_baseline,
    load_smoke_baseline,
    run_smoke_registry,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mechdsl.verify.perf.baseline import ComparisonReport


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mechdsl.verify.perf.run_compare",
        description=(
            "Run the Phase 10 smoke benchmark registry and compare against "
            "the committed baseline. Exit non-zero on >tolerance regression."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional path to write the ComparisonReport JSON to. If omitted, "
            "the report is printed to stdout."
        ),
    )
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=10.0,
        help="Default per-metric tolerance in percent (default: 10.0).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "Override path to the smoke baseline JSON. Defaults to the "
            "committed file under tests/golden/perf/baseline_smoke.json."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns exit status (0 = pass, 1 = regression)."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    registry = BenchmarkRegistry.default()
    with tempfile.TemporaryDirectory(prefix="perf_compare_") as td:
        current = run_smoke_registry(registry, tmp_path=Path(td))
    baseline = load_smoke_baseline(args.baseline)

    report: ComparisonReport = compare_to_baseline(
        current,
        baseline,
        tolerance_pct=args.tolerance_pct,
    )

    payload = report.to_json(indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        sys.stderr.write(f"wrote ComparisonReport -> {args.output}\n")
    else:
        sys.stdout.write(payload + "\n")

    if not report.overall_pass:
        failing = [b.task_id for b in report.benchmarks if not b.overall_pass]
        sys.stderr.write(
            f"perf regression detected (overall_pass=False); failing tasks: {failing}\n"
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - thin shim
    raise SystemExit(main())
