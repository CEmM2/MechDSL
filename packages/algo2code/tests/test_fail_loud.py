"""W1 (issue #307, F6) — fail-loud foundation.

The transpiler must raise on constructs it cannot faithfully lower, instead of
silently dropping statements or emitting wrong/empty code. These tests pin the
new behaviour and guard against regressing back to silent failure.
"""

from __future__ import annotations

import pytest

from algo2code import UnsupportedConstructError, transpile
from algo2code.expr_parser import parse_condition, parse_latex_expr

ALGO_HEAD = "\\begin{algorithmic}\n"
ALGO_TAIL = "\n\\end{algorithmic}"


def _wrap(state_math: str) -> str:
    return f"{ALGO_HEAD}\\State ${state_math}${ALGO_TAIL}"


# ── Tokenizer fail-loud: no silently-skipped characters ──────────────────────


def test_tensor_contraction_colon_raises():
    """F4: ':' is unsupported and must raise, not be silently skipped."""
    with pytest.raises(UnsupportedConstructError, match="contraction"):
        parse_latex_expr("C : e")


def test_accent_tilde_raises_with_guidance():
    """F3: \\tilde{r} raises and the message points to the subscript workaround."""
    with pytest.raises(UnsupportedConstructError, match="accent"):
        parse_latex_expr(r"\tilde{r}")


def test_accent_hat_raises():
    with pytest.raises(UnsupportedConstructError, match="accent"):
        parse_latex_expr(r"\hat{\tau}")


def test_unknown_symbol_raises():
    """A stray unrecognised character is reported, not dropped."""
    with pytest.raises(UnsupportedConstructError, match="unrecognised"):
        parse_latex_expr("a @ b")


# ── Parser fail-loud: whole expression must be consumed ──────────────────────


def test_unsupported_norm_order_raises():
    """Only the Euclidean 2-norm is supported; other orders must fail loud."""
    with pytest.raises(UnsupportedConstructError, match="2-norm"):
        parse_latex_expr(r"\lVert r \rVert_1")


def test_transpile_drops_nothing_silently():
    """A \\State whose math cannot tokenize raises rather than vanishing."""
    with pytest.raises(UnsupportedConstructError):
        transpile(_wrap(r"t = C : e"))


# ── Latent silent bugs that fail-loud surfaced and we corrected ──────────────


def test_equality_condition_is_equality_not_truthiness():
    """\\If{$r_0 = 0$}: bare '=' in a condition is equality (==), not a drop."""
    cond = parse_condition("r_0 = 0")
    assert cond.op == "=="


def test_abs_of_scalar_emits_abs_not_norm():
    """|pq| with pq scalar must emit abs(...), not the vector _norm kernel."""
    src = (
        "% algorithm absdemo\n"
        "% backend taichi\n"
        "% args x:vector\n"
        "% type pq scalar\n"
        f"{ALGO_HEAD}"
        r"\State $pq = 5$"
        "\n"
        r"\If{$|pq| < 1$}"
        "\n"
        r"\State $pq = 0$"
        "\n"
        r"\EndIf"
        f"{ALGO_TAIL}"
    )
    code = transpile(src)
    assert "abs(pq)" in code
    assert "_norm(pq)" not in code
