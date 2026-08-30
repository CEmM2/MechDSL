"""Integration tests for the ``mechdsl-lawgen compile`` CLI (Task P1-2).

Covers three CLI cases:

1. dry-run on a minimal fixture YAML prints the expected plan lines and writes
   no files (the ``--out`` dir stays empty);
2. a YAML missing a required key exits non-zero with a readable stderr error
   (no traceback);
3. ``--help`` / ``compile --help`` advertise the ``compile`` subcommand.

Tests call ``main([...])`` in-process (fast) and capture stdout/stderr with
``capsys``. Only ``--help`` goes through ``SystemExit`` (argparse convention).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mechdsl.lawgen.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL_LAW = FIXTURES / "linear_min.yaml"


def _write_law(tmp_path: Path, body: str) -> Path:
    law = tmp_path / "law.yaml"
    law.write_text(body, encoding="utf-8")
    return law


# ---------------------------------------------------------------------------
# Case 1 — dry-run prints the emission plan and writes no files.
# ---------------------------------------------------------------------------


class TestDryRunEmissionPlan:
    @pytest.mark.integration
    def test_dryrun_prints_plan_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(
            ["compile", str(MINIMAL_LAW), "--target", "ticonstit", "--out", "out", "--dry-run"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # Header + carrier identity.
        assert "emission plan (dry-run" in out
        assert "linear_min" in out
        # Resolved target identity (contract_id + package).
        assert "ticonstit.plasticity_carrier.v1" in out
        assert "ticonstit.generated" in out
        # Planned output paths under --out (nothing written).
        assert "out/plasticity/linear_min.py" in out
        assert "_manifest.json" in out
        assert "test_linear_min.py" in out
        # Every scalar expression to lower is summarised.
        assert "R:" in out
        assert "H:" in out
        assert "Q:" in out

    @pytest.mark.integration
    def test_dryrun_writes_no_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        rc = main(
            [
                "compile",
                str(MINIMAL_LAW),
                "--target",
                "ticonstit",
                "--out",
                str(out_dir),
                "--dry-run",
            ]
        )
        assert rc == 0
        # The --out directory stays empty — dry-run writes nothing.
        assert list(out_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# Case 2 — missing required key → non-zero exit, readable stderr, no traceback.
# ---------------------------------------------------------------------------


class TestFailureRoutes:
    @pytest.mark.integration
    def test_missing_required_key_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Drop the 'expressions' key entirely.
        law = _write_law(
            tmp_path,
            "name: broken\nparameters: [K]\nvariables: [p]\n",
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "expressions" in captured.err
        # No traceback leaked to the user.
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_malformed_yaml_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(tmp_path, "name: broken\n  parameters: [K]\n: :\n")
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_missing_file_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["compile", str(tmp_path / "nope.yaml"), "--target", "ticonstit", "--dry-run"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "not found" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_bad_expression_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(
            tmp_path,
            "name: broken\nparameters: [K]\nvariables: [p]\n"
            'expressions:\n  R: "K*("\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_unknown_target_exits_nonzero(self, capsys: pytest.CaptureFixture[str]) -> None:
        # --target is validated by argparse `choices`, so an unknown value is a
        # usage error: SystemExit(2), message on stderr, no Python traceback.
        with pytest.raises(SystemExit) as exc_info:
            main(["compile", str(MINIMAL_LAW), "--target", "mfront", "--dry-run"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "mfront" in captured.err  # names the invalid choice
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_undeclared_symbol_in_expression_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 'signa0' is a typo for the declared 'sigma0'; a naive parser would
        # silently turn it into a stray free symbol. The free-symbol subset
        # check must reject it, naming the offending symbol and the role.
        law = _write_law(
            tmp_path,
            "name: typo\nparameters: [sigma0, K, n]\nvariables: [p, edot, T]\n"
            'expressions:\n  R: "signa0 + K*p**n"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "undeclared" in captured.err
        assert "signa0" in captured.err  # names the offending symbol
        assert "'R'" in captured.err  # names the role
        assert "Traceback" not in captured.err

    # --- F1: no arbitrary code execution via a hostile expression -----------

    @pytest.mark.integration
    def test_code_injection_expression_does_not_execute(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # CRITICAL (F1): `sympify` would eval this and run os.system, creating
        # the sentinel file. The non-eval parser must NOT execute anything —
        # assert via a sentinel that would only exist if the payload ran.
        sentinel = tmp_path / "PWNED_SENTINEL"
        assert not sentinel.exists()
        payload = f"__import__('os').system('touch {sentinel}')"
        law = _write_law(
            tmp_path,
            "name: evil\nparameters: [b]\nvariables: [p]\n"
            f'expressions:\n  R: "{payload}"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        # The payload never executed — no side effect on disk.
        assert not sentinel.exists()
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    # --- F2: unknown function calls are rejected ----------------------------

    @pytest.mark.integration
    def test_unknown_function_in_expression_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 'expp' is a typo for 'exp' (not in the allow-list) → AppliedUndef.
        law = _write_law(
            tmp_path,
            "name: fn\nparameters: [b]\nvariables: [p]\n"
            'expressions:\n  R: "expp(b*p)"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "expp" in captured.err  # names the unknown function
        assert "Traceback" not in captured.err

    # --- F4: name / identifier validation -----------------------------------

    @pytest.mark.integration
    def test_name_with_path_traversal_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(
            tmp_path,
            'name: "../../escape"\nparameters: [K]\nvariables: [p]\n'
            'expressions:\n  R: "K*p"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "identifier" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_name_reserved_word_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(
            tmp_path,
            'name: "class"\nparameters: [K]\nvariables: [p]\n'
            'expressions:\n  R: "K*p"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "identifier" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_duplicate_parameter_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(
            tmp_path,
            "name: dup\nparameters: [K, K]\nvariables: [p]\n"
            'expressions:\n  R: "K*p"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "duplicate" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_parameter_variable_collision_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 'p' declared as both a parameter and a variable.
        law = _write_law(
            tmp_path,
            "name: col\nparameters: [p]\nvariables: [p]\n"
            'expressions:\n  R: "p"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "both a parameter and a variable" in captured.err
        assert "Traceback" not in captured.err

    # --- F6: strict keys ----------------------------------------------------

    @pytest.mark.integration
    def test_unknown_top_level_key_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(
            tmp_path,
            "name: t\nparameters: [K]\nvariables: [p]\nbogus: 1\n"
            'expressions:\n  R: "K*p"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "bogus" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.integration
    def test_unknown_expression_role_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        law = _write_law(
            tmp_path,
            "name: t\nparameters: [K]\nvariables: [p]\n"
            'expressions:\n  R: "K*p"\n  H: "1"\n  Q: "1"\n  QQ: "2"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--dry-run"])
        assert rc != 0
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "QQ" in captured.err
        assert "Traceback" not in captured.err

    # --- valid expressions with allow-listed functions still parse ----------

    @pytest.mark.integration
    def test_allowed_function_expression_parses(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # exp() is in the allow-list and a plain integer literal must parse.
        law = _write_law(
            tmp_path,
            "name: voce\nparameters: [sigma0, Q0, b]\nvariables: [p]\n"
            'expressions:\n  R: "sigma0 + Q0*(1 - exp(-b*p))"\n  H: "1"\n  Q: "1"\n',
        )
        rc = main(["compile", str(law), "--target", "ticonstit", "--out", "out", "--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "exp(-b*p)" in out


# ---------------------------------------------------------------------------
# Case 3 — --help advertises the compile subcommand.
# ---------------------------------------------------------------------------


class TestHelp:
    @pytest.mark.integration
    def test_top_level_help_lists_compile(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        assert "compile" in capsys.readouterr().out

    @pytest.mark.integration
    def test_compile_help_lists_options(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["compile", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--target" in out
        assert "--out" in out
        assert "--dry-run" in out
