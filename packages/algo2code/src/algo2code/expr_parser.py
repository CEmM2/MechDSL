"""
Expression parser for LaTeX math fragments inside \\State commands.

Handles the linear-algebra subset of LaTeX math relevant to iterative solvers:
  - Scalar arithmetic:  \\alpha, \\frac{a}{b}, a + b, a - b
  - Vector/matrix ops:  \\mathbf{A} \\mathbf{p}, \\mathbf{r}^\\top \\mathbf{z}
  - Norms:              \\|\\mathbf{r}\\|, \\lVert r \\rVert
  - Function calls:     \\mathbf{M}^{-1}(\\mathbf{r})
  - Subscripts:         \\rho_{\\text{new}}, x_{k+1}

This is intentionally NOT a full LaTeX math parser. It handles the ~20 patterns
that actually appear in algorithm boxes for CG, GMRES, Newton, return-mapping, etc.
"""

from __future__ import annotations

import re

from .ast_nodes import BinOp, Expr, FuncCall, Number, UnaryOp, Var

# ── Tokenizer ────────────────────────────────────────────────────────────────

# Order matters: longer patterns first
TOKEN_PATTERNS = [
    # Commands and groups
    (r"\\(?:mathbf|boldsymbol|bm|mathit|mathrm|text|textbf)\{([^}]*)\}", "STYLED"),
    (r"\\operatorname\{([^}]*)\}", "OPNAME"),
    (r"\\(?:lVert|left\\\|)", "LNORM"),
    (r"\\(?:rVert|right\\\|)", "RNORM"),
    (r"\\\|", "NORMPIPE"),
    (r"\\frac\s*", "FRAC"),
    (r"\\sqrt\s*", "SQRT"),
    (r"\\cdot", "CDOT"),
    (r"\\,", "THINSPACE"),
    (r"\\;", "THINSPACE"),
    (r"\\quad", "THINSPACE"),
    (r"\\top", "TOP"),
    (r"\\[Tt]ranspose", "TOP"),
    (r"\\ldots|\\dots|\\cdots", "DOTS"),
    # Greek letters
    (
        r"\\(alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|"
        r"iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|"
        r"varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|"
        r"Upsilon|Phi|Psi|Omega)",
        "GREEK",
    ),
    # Delimiters and operators
    (r"\{", "LBRACE"),
    (r"\}", "RBRACE"),
    (r"\(", "LPAREN"),
    (r"\)", "RPAREN"),
    (r"\^", "CARET"),
    (r"_", "UNDERSCORE"),
    (r"\+", "PLUS"),
    (r"-", "MINUS"),
    (r"/", "SLASH"),
    (r"=", "EQUALS"),
    (r"<", "LT"),
    (r">", "GT"),
    (r",", "COMMA"),
    # Numbers
    (r"\d+\.?\d*", "NUMBER"),
    # Plain letters / identifiers — multi-character names supported so
    # algorithm scratch identifiers like ``pq``, ``sn``, ``rho_new`` can
    # tokenise as a single Var instead of an implicit product. Single
    # letters still tokenise to LETTER for back-compat (``x``, ``a``).
    # post_recovery_plan Phase 5: parser fix landed alongside the
    # algo2code radial-return substitution so ``algo2code.transpile``
    # can consume the algpseudocode without manual rewriting.
    (r"[a-zA-Z][a-zA-Z0-9]*", "LETTER"),
    # Whitespace
    (r"\s+", "WS"),
]

_TOKEN_RE = re.compile("|".join(f"(?P<T{i}>{pat})" for i, (pat, _) in enumerate(TOKEN_PATTERNS)))
_TOKEN_NAMES = [name for _, name in TOKEN_PATTERNS]


class Token:
    __slots__ = ("kind", "pos", "value")

    def __init__(self, kind: str, value: str, pos: int):
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r})"


def tokenize(latex: str) -> list[Token]:
    """Tokenize a LaTeX math expression."""
    tokens = []
    for m in _TOKEN_RE.finditer(latex):
        for i, (_, name) in enumerate(TOKEN_PATTERNS):
            g = m.group(f"T{i}")
            if g is not None:
                if name in ("WS", "THINSPACE"):
                    break  # skip whitespace
                val = g
                # Extract inner text for styled commands
                if name in ("STYLED", "OPNAME"):
                    inner = re.match(TOKEN_PATTERNS[0 if name == "STYLED" else 1][0], g)
                    if inner:
                        val = inner.group(1)
                if name == "GREEK":
                    idx = next(j for j, (_, n) in enumerate(TOKEN_PATTERNS) if n == "GREEK")
                    inner = re.match(TOKEN_PATTERNS[idx][0], g)
                    if inner:
                        val = inner.group(1)
                tokens.append(Token(name, val, m.start()))
                break
    return tokens


# ── Recursive-descent parser ─────────────────────────────────────────────────


class ExprParser:
    """
    Recursive-descent parser for LaTeX math expressions.

    Grammar (simplified):
        expr        := term (('+' | '-') term)*
        term        := factor (('\\cdot' | implicit) factor)*
        factor      := base ('^' superscript)?
        base        := '(' expr ')'
                     | '\\frac' '{' expr '}' '{' expr '}'
                     | '\\sqrt' '{' expr '}'
                     | norm_expr
                     | func_call
                     | atom
        norm_expr   := '\\|' expr '\\|' | '\\lVert' expr '\\rVert'
        atom        := NUMBER | LETTER | GREEK | STYLED
        superscript := '{' expr '}' | '\\top' | '-1' | atom
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.peek()
        if tok is None or tok.kind != kind:
            got = tok.kind if tok else "EOF"
            raise SyntaxError(f"Expected {kind} but got {got} at position {self.pos}")
        return self.advance()

    def at(self, *kinds: str) -> bool:
        tok = self.peek()
        return tok is not None and tok.kind in kinds

    def parse(self) -> Expr:
        """Parse the full expression."""
        return self.parse_expr()

    def parse_expr(self) -> Expr:
        """expr := term (('+' | '-') term)*"""
        left = self.parse_term()
        while self.at("PLUS", "MINUS"):
            op_tok = self.advance()
            right = self.parse_term()
            op = "+" if op_tok.kind == "PLUS" else "-"
            left = BinOp(op=op, left=left, right=right)
        return left

    def parse_term(self) -> Expr:
        """term := signed_factor (('·' | '/' | implicit_mul) signed_factor)*

        Division at the term level shares precedence with multiplication
        (left-associative) so ``a + b / c`` parses as ``a + (b / c)``
        rather than dropping the divisor. post_recovery_plan Phase 5
        parser fix.
        """
        left = self.parse_signed_factor()
        while True:
            # Explicit multiply
            if self.at("CDOT"):
                self.advance()
                right = self.parse_signed_factor()
                left = BinOp(op="*", left=left, right=right)
            # Division (bare ``/``); ``\frac{}{}`` is handled separately by
            # parse_frac so this path only fires for inline divisions.
            elif self.at("SLASH"):
                self.advance()
                right = self.parse_signed_factor()
                left = BinOp(op="/", left=left, right=right)
            # Implicit multiplication: two adjacent factors with no operator
            elif self._can_start_factor():
                right = self.parse_signed_factor()
                left = BinOp(op="*", left=left, right=right)
            else:
                break
        return left

    def parse_signed_factor(self) -> Expr:
        """Handle unary minus before a factor."""
        if self.at("MINUS"):
            self.advance()
            operand = self.parse_factor()
            return UnaryOp(op="neg", operand=operand)
        return self.parse_factor()

    def _can_start_factor(self) -> bool:
        """Check if the next token can start a new factor (implicit multiply).

        NOTE: NORMPIPE is intentionally excluded. It is ambiguous — it could
        be the *closing* pipe of a norm we're currently inside.  Norms as
        implicit-mul operands must use \\lVert/\\rVert or explicit \\cdot.
        """
        tok = self.peek()
        if tok is None:
            return False
        return tok.kind in (
            "LETTER",
            "GREEK",
            "STYLED",
            "NUMBER",
            "LPAREN",
            "FRAC",
            "SQRT",
            "LNORM",
            "OPNAME",
        )

    def parse_factor(self) -> Expr:
        """factor := base ('^' superscript)? ('(' args ')')?

        The trailing parens handle M^{-1}(r) as a function call.
        """
        base = self.parse_base()

        if self.at("CARET"):
            self.advance()
            base = self.parse_superscript(base)

        # Check for function call after superscript:  M^{-1}(r)
        if self.at("LPAREN"):
            self.advance()
            args = []
            if not self.at("RPAREN"):
                args.append(self.parse_expr())
                while self.at("COMMA"):
                    self.advance()
                    args.append(self.parse_expr())
            self.expect("RPAREN")
            return FuncCall(func=base, args=args)

        return base

    def parse_superscript(self, base: Expr) -> Expr:
        """
        superscript after ^:
          ^{\\top}     → transpose
          ^{-1}        → inverse (for callable context)
          ^{T}         → transpose
          ^{expr}      → power
          ^\\top       → transpose (no braces)
        """
        if self.at("TOP"):
            self.advance()
            return UnaryOp(op="transpose", operand=base)

        if self.at("LBRACE"):
            self.advance()

            # Check for ^\top inside braces
            if self.at("TOP"):
                self.advance()
                self.expect("RBRACE")
                return UnaryOp(op="transpose", operand=base)

            # Check for ^{T}
            tok = self.peek()
            if tok is not None and tok.kind == "LETTER" and tok.value == "T":
                saved_pos = self.pos
                self.advance()
                if self.at("RBRACE"):
                    self.advance()
                    return UnaryOp(op="transpose", operand=base)
                else:
                    self.pos = saved_pos

            # Check for ^{-1}  (inverse)
            if self.at("MINUS"):
                saved_pos = self.pos
                self.advance()
                num_tok = self.peek()
                if num_tok is not None and num_tok.kind == "NUMBER" and num_tok.value == "1":
                    self.advance()
                    self.expect("RBRACE")
                    return UnaryOp(op="inverse", operand=base)
                self.pos = saved_pos

            # General exponent
            exp = self.parse_expr()
            self.expect("RBRACE")
            return BinOp(op="pow", left=base, right=exp)

        # Bare superscript: single token
        if self.at("TOP"):
            self.advance()
            return UnaryOp(op="transpose", operand=base)

        exp = self.parse_atom()
        return BinOp(op="pow", left=base, right=exp)

    def parse_base(self) -> Expr:
        """
        base := '(' expr ')'
              | '\\frac{num}{den}'
              | '\\sqrt{expr}'
              | norm_expr
              | func_call  (detected by atom followed by '(')
              | atom
        """
        if self.at("LPAREN"):
            self.advance()
            expr = self.parse_expr()
            self.expect("RPAREN")
            return expr

        if self.at("FRAC"):
            return self.parse_frac()

        if self.at("SQRT"):
            return self.parse_sqrt()

        if self.at("NORMPIPE", "LNORM"):
            return self.parse_norm()

        atom = self.parse_atom()

        if self.at("LPAREN"):
            self.advance()
            args = []
            if not self.at("RPAREN"):
                args.append(self.parse_expr())
                while self.at("COMMA"):
                    self.advance()
                    args.append(self.parse_expr())
            self.expect("RPAREN")
            return FuncCall(func=atom, args=args)

        return atom

    def parse_frac(self) -> Expr:
        """\\frac{numerator}{denominator}"""
        self.expect("FRAC")
        self.expect("LBRACE")
        num = self.parse_expr()
        self.expect("RBRACE")
        self.expect("LBRACE")
        den = self.parse_expr()
        self.expect("RBRACE")
        return BinOp(op="/", left=num, right=den)

    def parse_sqrt(self) -> Expr:
        """\\sqrt{expr}"""
        self.expect("SQRT")
        self.expect("LBRACE")
        inner = self.parse_expr()
        self.expect("RBRACE")
        return FuncCall(func=Var(name="sqrt"), args=[inner])

    def parse_norm(self) -> Expr:
        """\\| expr \\|  or  \\lVert expr \\rVert"""
        start = self.advance()  # consume NORMPIPE or LNORM
        inner = self.parse_expr()
        if start.kind == "LNORM":
            self.expect("RNORM")
        else:
            self.expect("NORMPIPE")
        return UnaryOp(op="norm", operand=inner)

    def parse_atom(self) -> Expr:
        """atom := NUMBER | LETTER | GREEK | STYLED"""
        tok = self.peek()
        if tok is None:
            raise SyntaxError("Unexpected end of expression")

        if tok.kind == "NUMBER":
            self.advance()
            return Number(value=float(tok.value))

        if tok.kind in ("LETTER", "GREEK", "STYLED", "OPNAME"):
            self.advance()
            name = tok.value
            subscript = None
            if self.at("UNDERSCORE"):
                self.advance()
                subscript = self._parse_subscript_text()
            return Var(name=name, subscript=subscript)

        if tok.kind == "DOTS":
            self.advance()
            return Var(name="...")

        raise SyntaxError(f"Unexpected token {tok} at position {tok.pos}")

    def _parse_subscript_text(self) -> str:
        """Parse the text after _ : either {content} or single token."""
        if self.at("LBRACE"):
            self.advance()
            parts: list[str] = []
            depth = 1
            while depth > 0:
                tok = self.advance()
                if tok.kind == "LBRACE":
                    depth += 1
                elif tok.kind == "RBRACE":
                    depth -= 1
                    if depth == 0:
                        break
                if tok.kind == "STYLED" or tok.kind in ("LETTER", "GREEK", "NUMBER"):
                    parts.append(tok.value)
                elif tok.kind == "PLUS":
                    parts.append("+")
                elif tok.kind == "MINUS":
                    parts.append("-")
            return "".join(parts)
        else:
            tok = self.advance()
            return tok.value


# ── Public API ───────────────────────────────────────────────────────────────


def parse_latex_expr(latex: str) -> Expr:
    """Parse a LaTeX math expression string into an AST."""
    tokens = tokenize(latex)
    if not tokens:
        raise SyntaxError(f"Empty expression: {latex!r}")
    parser = ExprParser(tokens)
    return parser.parse()


def parse_assignment(latex: str) -> tuple[Var, Expr] | None:
    """
    Parse 'lhs = rhs' from a LaTeX string.
    Returns (target_var, rhs_expr) or None if not an assignment.
    """
    depth = 0
    eq_pos = -1
    for i, ch in enumerate(latex):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "=" and depth == 0:
            eq_pos = i
            break

    if eq_pos < 0:
        return None

    lhs_str = latex[:eq_pos].strip()
    rhs_str = latex[eq_pos + 1 :].strip()

    lhs = parse_latex_expr(lhs_str)
    rhs = parse_latex_expr(rhs_str)

    if not isinstance(lhs, Var):
        raise SyntaxError(f"LHS of assignment must be a variable, got {type(lhs)}: {lhs_str}")

    return (lhs, rhs)


def parse_condition(latex: str) -> Expr:
    """
    Parse a condition expression: \\|r\\| < \\varepsilon, etc.
    Returns a BinOp with op='<', '>', '<=', '>=', '=='.
    """
    depth = 0
    for i, ch in enumerate(latex):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and ch in "<>":
            lhs_str = latex[:i].strip()
            rhs_str = latex[i + 1 :].strip()
            op = ch
            if rhs_str.startswith("="):
                op += "="
                rhs_str = rhs_str[1:].strip()

            lhs = parse_latex_expr(lhs_str)
            rhs = parse_latex_expr(rhs_str)
            return BinOp(op=op, left=lhs, right=rhs)

    return parse_latex_expr(latex)
