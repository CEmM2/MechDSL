"""Tests for Task P1-2: Extend Neumann directive parser."""

from __future__ import annotations

import pytest

from mechdsl.frontend.directives import ParseError, _mech_boundary
from mechdsl.frontend.parser import parse


def _parse_bc(directive_body: str) -> dict:
    """Drive the BC directive handler with the parsed-args tuple shape."""
    accum: dict = {}
    # Strip leading "boundary " from the body for handler input.
    # The handler expects (positional, options) shape.
    parts = directive_body.split(maxsplit=1)
    name = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    # Tokenize options as the parser does (very simple split-on-flags).
    options: dict = {}
    tokens = []
    in_quote = False
    cur = []
    for ch in rest:
        if ch == '"':
            in_quote = not in_quote
            continue
        if ch == " " and not in_quote:
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:]
            options[key] = tokens[i + 1] if i + 1 < len(tokens) else ""
            i += 2
        else:
            i += 1
    _mech_boundary(accum, ([name], options), line_no=1)
    return accum["boundaries"][0]


class TestTaskP1_2:
    """Tests for Task P1-2: Neumann directive parser with traction + surface."""

    @pytest.mark.unit
    def test_parse_neumann_with_traction_and_surface(self):
        bc = _parse_bc('load --type neumann --traction "0 0 -1000" --surface top')
        assert bc["type"] == "neumann"
        assert bc["traction"] == [0.0, 0.0, -1000.0]
        assert bc["surface_tag"] == "top"

    @pytest.mark.unit
    def test_parse_neumann_with_symbolic_traction(self):
        bc = _parse_bc("load --type neumann --traction t_bar")
        assert bc["traction"] == "t_bar"
        assert "surface_tag" not in bc

    @pytest.mark.unit
    def test_parse_neumann_malformed_traction_errors(self):
        with pytest.raises(ParseError, match="--traction"):
            _parse_bc('load --type neumann --traction "0 abc -1000"')

    @pytest.mark.unit
    def test_parse_neumann_wrong_arity_traction_errors(self):
        with pytest.raises(ParseError, match="3 components"):
            _parse_bc('load --type neumann --traction "0 0"')

    @pytest.mark.unit
    def test_dirichlet_directive_unchanged(self):
        bc = _parse_bc('fix --type dirichlet --components "0 1 2" --value 0')
        assert bc["type"] == "dirichlet"
        assert bc["components"] == [0, 1, 2]
        assert bc["value"] == 0

    @pytest.mark.unit
    def test_full_pipeline_neumann_directive(self):
        # End-to-end through parse(): the LaTeX source produces a context
        # with the Neumann BC carrying traction vector + surface tag.
        latex = (
            "% mechanics dim 3\n"
            "% mechanics cell hex8\n"
            "% mechanics formulation total_lagrangian\n"
            "% mechanics material svk --E 200e3 --nu 0.3\n"
            '% mechanics boundary load --type neumann --traction "0 0 -1000" --surface top\n'
        )
        ctx = parse(latex)
        bcs = ctx.get("boundaries", [])
        load_bc = next(b for b in bcs if b["name"] == "load")
        assert load_bc["traction"] == [0.0, 0.0, -1000.0]
        assert load_bc["surface_tag"] == "top"
