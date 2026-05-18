"""LaTeX ``% mechanics`` directive parser (adapter, not parser-of-record for math).

This module is the **directive scanner** half of the frontend — see the
parser-of-record vs adapter/normalizer/validator split documented in
``packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md`` (introduced by
recovery-plan Phase 2 / R1.3 / task ``P2-3``).

Responsibilities of this module:

- Walk a LaTeX source string line-by-line.
- Collect ``% mechanics`` directive lines with their 1-based line numbers.
- Dispatch each directive through :mod:`mechdsl.frontend.directives`
  (normalization layer).
- Funnel the resulting accumulator through
  :func:`mechdsl.frontend.build_context` (validation layer) so the
  supported-subset checks live in a single place.

Out of scope for this module:

- Math-grammar parsing of ``\\Psi = ...`` expressions, index manipulation
  in body LaTeX, or anything that requires understanding LaTeX-math
  semantics. Those are the responsibility of NRPyLaTeX (the
  parser-of-record), which is wired in ``pyproject.toml`` but not yet
  imported under ``src/`` — the recovery plan defers the actual
  integration to a follow-up task. MVP constitutive models (SVK,
  J2 power-law) are hardcoded in the symbolic layer, so no math grammar
  is needed for the canonical compile path today.

See ``dev/design_docs/02-LATEX-DSL.md`` for the directive grammar and
``dev/design_docs/PLAN-A.md §A3`` for the MVP scope.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from mechdsl.frontend.directives import (
    DEFERRED_DIRECTIVES,
    HANDLERS,
    ParseError,
)

# Re-export so callers that ``from mechdsl.frontend.parser import ParseError``
# get the same class used by the handlers.
__all__ = ["ParseError", "parse", "parse_file", "scan_directives"]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


_DIRECTIVE_PREFIX = "mechanics"


def scan_directives(source: str) -> list[tuple[int, str]]:
    """Extract ``% mechanics ...`` directives from a LaTeX source string.

    Returns a list of ``(line_no, body)`` pairs in source order, where
    ``line_no`` is 1-indexed and ``body`` is the text of the directive with
    the leading ``% mechanics`` stripped (leading/trailing whitespace
    removed).  Regular LaTeX comments, blank lines, and content lines are
    skipped silently.

    Trailing LaTeX comments on the same line (``% mechanics dim 3  % 3D``)
    are *not* stripped — they survive into the token stream and
    :func:`shlex.split` treats them as positional tokens, which would cause
    a parse error.  Directives must occupy the whole comment.
    """
    out: list[tuple[int, str]] = []
    for line_no, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.lstrip()
        if not stripped.startswith("%"):
            continue
        # Strip the leading '%' and any immediately-following whitespace.
        after_percent = stripped[1:].lstrip()
        if not after_percent.startswith(_DIRECTIVE_PREFIX):
            continue
        # Require a word boundary after 'mechanics' so '% mechanicsfoo' is
        # treated as a plain LaTeX comment, not a malformed directive.
        tail = after_percent[len(_DIRECTIVE_PREFIX) :]
        if tail and not tail[0].isspace():
            continue
        body = tail.strip()
        out.append((line_no, body))
    return out


# ---------------------------------------------------------------------------
# Token splitter
# ---------------------------------------------------------------------------


def _split_directive(body: str, *, line_no: int) -> tuple[str, list[str], dict[str, str]]:
    """Split a directive body into ``(command, positional, options)``.

    Uses :func:`shlex.split` so quoted strings (``--traction "t_bar"``) and
    LaTeX escapes (``--mu \\mu``) survive as single tokens.  Options are
    ``--key value`` pairs: the key strips the leading ``--`` and the value
    is the immediately-following token.
    """
    try:
        tokens = shlex.split(body, comments=False, posix=True)
    except ValueError as exc:
        raise ParseError(
            f"line {line_no}: unbalanced quoting in '% mechanics {body}': {exc}"
        ) from exc
    if not tokens:
        raise ParseError(f"line {line_no}: '% mechanics' with no command")

    command = tokens[0]
    positional: list[str] = []
    options: dict[str, str] = {}
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:]
            if not key:
                raise ParseError(f"line {line_no}: empty option name ('--' with no key)")
            if i + 1 >= len(tokens):
                raise ParseError(f"line {line_no}: option --{key} is missing a value")
            next_tok = tokens[i + 1]
            if next_tok.startswith("--"):
                raise ParseError(
                    f"line {line_no}: option --{key} is missing a value "
                    f"(next token is --{next_tok[2:]})"
                )
            # Values for list-valued options (e.g. --components "0 1 2") may
            # span several positional tokens until the next --key appears.
            # shlex has already done the split, so we glue them back together.
            value_parts = [next_tok]
            j = i + 2
            while j < len(tokens) and not tokens[j].startswith("--"):
                value_parts.append(tokens[j])
                j += 1
            options[key] = " ".join(value_parts)
            i = j
        else:
            positional.append(tok)
            i += 1
    return command, positional, options


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def parse(source: str) -> dict[str, Any]:
    """Parse a LaTeX source string and return an MVP context dict.

    Walks ``% mechanics`` directives in order, applies each to an
    accumulator via :mod:`mechdsl.frontend.directives`, and finally calls
    :func:`mechdsl.frontend.build_context` so the supported-subset checks
    (with Plan B phase pointers) live in one place.

    Parameters
    ----------
    source:
        LaTeX source containing zero or more ``% mechanics`` directives.

    Returns
    -------
    dict
        Context dict with the same seven keys as
        :func:`mechdsl.frontend.build_context` (``dim``, ``cell_type``,
        ``formulation``, ``material_type``, ``params``, ``boundaries``,
        ``coord_system``), plus any ``coord_spatial`` / ``coord_material``
        / ``coord_convected`` / ``indices_spatial`` / ``indices_material``
        entries that were declared in the source.

    Raises
    ------
    ParseError
        Syntax errors (unknown command, malformed option, missing value).
    mechdsl.symbolic.convected.UnsupportedError
        Semantic errors caught by :func:`build_context`: inputs outside
        the MVP supported subset.  The error message names the Plan B
        phase that adds support.
    """
    # Local import to avoid a circular dependency via frontend/__init__.py.
    from mechdsl.frontend import build_context

    accum: dict[str, Any] = {}
    for line_no, body in scan_directives(source):
        # Peek at the command word before full tokenisation so deferred
        # directives (which may use flag-only options like
        # ``constitutive Psi --strain_energy``) are rejected with the
        # Plan B pointer rather than a misleading ``missing a value`` error.
        first_word = body.split(None, 1)[0] if body else ""
        if first_word in DEFERRED_DIRECTIVES:
            phase, reason = DEFERRED_DIRECTIVES[first_word]
            raise ParseError(
                f"line {line_no}: '% mechanics {first_word}' is not part of "
                f"the MVP subset; {reason} ({phase})"
            )
        if first_word not in HANDLERS:
            raise ParseError(
                f"line {line_no}: unknown directive '% mechanics {first_word}'. "
                f"Known MVP directives: {sorted(HANDLERS)}"
            )
        command, positional, options = _split_directive(body, line_no=line_no)
        # _split_directive preserves the same command word, so the handler
        # lookup below is unconditional — it exists because we just checked.
        handler = HANDLERS[command]
        handler(accum, (positional, options), line_no)

    # Defaults for fields that build_context treats as required.  The
    # accumulator-only fields (coord_spatial etc.) flow through untouched.
    if "dim" not in accum:
        raise ParseError("missing required '% mechanics dim' directive")
    if "cell_type" not in accum:
        raise ParseError("missing required '% mechanics cell' directive")
    if "formulation" not in accum:
        raise ParseError("missing required '% mechanics formulation' directive")
    if "material_type" not in accum:
        raise ParseError("missing required '% mechanics material' directive")

    # Delegate subset validation to build_context.  Anything outside the
    # MVP subset raises UnsupportedError with a Plan B phase pointer.
    base = build_context(
        dim=accum["dim"],
        cell_type=accum["cell_type"],
        formulation=accum["formulation"],
        material_type=accum["material_type"],
        params=accum.get("params", {}),
        boundaries=accum.get("boundaries", []),
        coord_system=accum.get("coord_system", "cartesian"),
        integration=accum.get("integration", "full"),
        hourglass=accum.get("hourglass"),
    )

    # Merge accumulator extras (coord_spatial etc.) into the final context.
    # build_context returns a fresh dict so we can mutate it here without
    # leaking state back into its internal validation path.
    for key in (
        "coord_spatial",
        "coord_material",
        "coord_convected",
        "indices_spatial",
        "indices_material",
        "metric_current",
        "metric_reference",
    ):
        if key in accum:
            base[key] = accum[key]
    return base


def parse_file(path: str | Path) -> dict[str, Any]:
    """Parse a LaTeX source file and return an MVP context dict.

    Thin wrapper around :func:`parse` that reads ``path`` as UTF-8.  See
    :func:`parse` for the returned dict shape and error behaviour.
    """
    text = Path(path).read_text(encoding="utf-8")
    return parse(text)
