"""W5 (issue #307, F3/F4/F5) — deferred constructs are loud and point to the way out.

Accents (F3) and tensor contraction `:` (F4) are intentionally excluded by the
design doc (§2.4). Rather than silently mangling them, the transpiler raises an
``UnsupportedConstructError`` whose message names the supported alternative.
Spectral intrinsics (F5) are not built in but are reachable through the existing
``% args ...:callable`` mechanism — this test pins that documented path.
"""

from __future__ import annotations

import re

import pytest

from algo2code import UnsupportedConstructError, transpile
from algo2code.expr_parser import parse_latex_expr

# ── F3: accents are deferred, with a subscript alternative in the message ────


@pytest.mark.parametrize("accent", [r"\tilde{r}", r"\hat{\tau}", r"\bar{x}"])
def test_accents_raise_pointing_to_subscripts(accent):
    with pytest.raises(UnsupportedConstructError, match="subscript"):
        parse_latex_expr(accent)


# ── F4: tensor contraction is deferred, with the einsum alternative ──────────


def test_colon_contraction_raises_pointing_to_einsum():
    with pytest.raises(UnsupportedConstructError, match=r"(?i)einsum|contraction"):
        parse_latex_expr(r"C : e")


# ── F5: spectral intrinsics work through the % args callable path ────────────


def test_declared_callable_intrinsics_transpile_to_inplace_calls():
    """DFT/IDFT/Gamma0 declared as callables emit in-place calls (like apply_M_inv)."""
    src = r"""% algorithm fft_step
% backend taichi
% args x:vector, xhat:vector, y:vector, DFT:callable, IDFT:callable
\begin{algorithmic}
\State $xhat = DFT(x)$
\State $y = IDFT(xhat)$
\end{algorithmic}"""
    code = transpile(src)
    assert re.search(r"\bDFT\(x, xhat\)", code)
    assert re.search(r"\bIDFT\(xhat, y\)", code)


def test_deferral_messages_are_actionable():
    """Each deferral error must name a concrete alternative, not just 'unsupported'."""
    cases = {
        r"\tilde{r}": "subscript",
        r"C : e": "einsum",
    }
    for latex, alternative in cases.items():
        try:
            parse_latex_expr(latex)
        except UnsupportedConstructError as exc:
            assert alternative in str(exc).lower(), f"{latex!r} message lacks {alternative!r}"
        else:
            pytest.fail(f"{latex!r} should have raised")
