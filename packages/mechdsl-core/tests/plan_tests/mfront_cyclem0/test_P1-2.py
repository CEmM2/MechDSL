"""Plan-anchor tests for Task P1-2: mechdsl-lawgen compile CLI skeleton with dry-run.

Plan: dev/plans/mfront_cycleM0.md (lines 59-62) — MFront-mimic Cycle M0, Phase 1.
Deliverables under test (built in P1-2 exec):
  packages/mechdsl-core/src/mechdsl/lawgen/cli.py + `mechdsl-lawgen` entry point.

These three tests anchor the plan's ``test_plan.cases`` (AC 1, 2, 3). The
exhaustive integration suite lives in ``tests/lawgen/test_cli.py``; here we pin
the acceptance criteria directly against ``mechdsl.lawgen.cli.main``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mechdsl.lawgen.cli import main

if TYPE_CHECKING:
    from pathlib import Path

_MINIMAL_LAW = (
    "name: linear_min\n"
    "parameters: [sigma0, K, n]\n"
    "variables: [p, edot, T]\n"
    "expressions:\n"
    '  R: "sigma0 + K*p**n"\n'
    '  H: "1"\n'
    '  Q: "1"\n'
)


class TestTaskP1_2:
    """Tests for Task P1-2: mechdsl-lawgen compile CLI (dry-run). AC covered: 1,2,3."""

    @pytest.mark.integration
    def test_dryrun_minimal_yaml_emission_plan(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verifies: `compile <yaml> --target ticonstit --dry-run` prints the emission plan.
        AC1: dry-run prints target contract_id, planned output paths, expressions to lower —
        and writes no files.
        Passes when: stdout contains the plan lines and the --out dir stays empty."""
        law = tmp_path / "linear_min.yaml"
        law.write_text(_MINIMAL_LAW, encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        rc = main(
            ["compile", str(law), "--target", "ticonstit", "--out", str(out_dir), "--dry-run"]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "ticonstit.plasticity_carrier.v1" in out  # contract_id
        assert "ticonstit.generated" in out  # package
        assert "plasticity/linear_min.py" in out  # planned carrier path
        assert "_manifest.json" in out  # planned manifest entry
        assert "R:" in out and "H:" in out and "Q:" in out  # expressions to lower
        # Dry-run writes nothing.
        assert list(out_dir.iterdir()) == []

    @pytest.mark.integration
    def test_missing_yaml_key_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verifies: a law YAML missing a required key exits non-zero with a human error.
        AC2: invalid YAML → readable error, not a traceback.
        Passes when: exit code != 0 and stderr carries a message naming the missing key."""
        law = tmp_path / "broken.yaml"
        law.write_text("name: broken\nparameters: [K]\nvariables: [p]\n", encoding="utf-8")

        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])

        assert rc != 0
        err = capsys.readouterr().err
        assert "expressions" in err  # names the missing key
        assert "Traceback" not in err  # readable error, not a traceback

    @pytest.mark.integration
    def test_help_shows_compile_subcommand(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verifies: `mechdsl-lawgen --help` (and `compile --help`) advertise the compile subcommand.
        AC3: CLI is reachable after uv sync; compile subcommand documented.
        Passes when: help text lists `compile` with --target/--out/--dry-run."""
        with pytest.raises(SystemExit) as top_exc:
            main(["--help"])
        assert top_exc.value.code == 0
        assert "compile" in capsys.readouterr().out

        with pytest.raises(SystemExit) as sub_exc:
            main(["compile", "--help"])
        assert sub_exc.value.code == 0
        sub_out = capsys.readouterr().out
        assert "--target" in sub_out
        assert "--out" in sub_out
        assert "--dry-run" in sub_out
