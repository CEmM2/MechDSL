r"""
Parser for LaTeX `algpseudocode` environments.

Recognises:
  \begin{algorithmic}  ...  \end{algorithmic}
  \State $lhs = rhs$       % optional_comment
  \For{$k = 0, 1, \ldots, N$}  ...  \EndFor
  \While{$cond$}            ...  \EndWhile
  \If{$cond$}               ...  \ElsIf{$cond$}  ...  \Else  ...  \EndIf
  \Return $expr$
  \State \textbf{break}

Directive comments (lines starting with `%` OUTSIDE algorithmic):
  % algorithm <name>
  % backend <taichi|numpy|petsc>
  % args <name>:<type>, ...
  % type <varname> <scalar|vector|matrix|callable>

The parser delegates all $...$ math fragments to expr_parser.
"""
from __future__ import annotations
import re
from .ast_nodes import (
    Algorithm, Stmt, Assign, ForLoop, WhileLoop, Branch, Return, Break,
    Var, VarType
)
from .expr_parser import parse_latex_expr, parse_assignment, parse_condition


# ── Directive parsing ────────────────────────────────────────────────────────

_TYPE_MAP = {
    'scalar':   VarType.SCALAR,
    'vector':   VarType.VECTOR,
    'matrix':   VarType.MATRIX,
    'callable': VarType.CALLABLE,
    'matvec':   VarType.MATRIX,     # alias
}


def _parse_directives(lines: list[str]) -> dict:
    """Parse % directive comments before the algorithmic block."""
    directives: dict = {
        'name': 'algorithm',
        'backend': 'taichi',
        'args': [],
        'types': {},
    }

    for line in lines:
        line = line.strip()
        if not line.startswith('%'):
            continue
        line = line[1:].strip()

        if line.startswith('algorithm '):
            directives['name'] = line.split(None, 1)[1].strip()

        elif line.startswith('backend '):
            directives['backend'] = line.split(None, 1)[1].strip()

        elif line.startswith('args '):
            arg_str = line.split(None, 1)[1]
            for arg in arg_str.split(','):
                arg = arg.strip()
                if ':' in arg:
                    name, typ = arg.split(':', 1)
                    directives['args'].append(
                        (name.strip(), _TYPE_MAP.get(typ.strip(), VarType.UNKNOWN))
                    )
                else:
                    directives['args'].append((arg, VarType.UNKNOWN))

        elif line.startswith('type '):
            parts = line.split()
            if len(parts) >= 3:
                varname = parts[1]
                vtype = _TYPE_MAP.get(parts[2], VarType.UNKNOWN)
                directives['types'][varname] = vtype

    return directives


# ── Main parser ──────────────────────────────────────────────────────────────

class AlgPseudocodeParser:
    """
    Parse a complete LaTeX source containing an algorithmic environment.

    Usage:
        algo = AlgPseudocodeParser(latex_string).parse()
    """

    def __init__(self, source: str):
        self.source = source
        self.lines: list[str] = []
        self.pos = 0

    def parse(self) -> Algorithm:
        """Parse the full source and return an Algorithm AST."""
        # Split into pre-algorithmic directives and body
        pre_lines, body_lines = self._split_sections()
        directives = _parse_directives(pre_lines)

        # Also collect inline type comments from body lines
        type_annotations = dict(directives['types'])
        self._collect_inline_types(body_lines, type_annotations)

        # Parse the body
        self.lines = body_lines
        self.pos = 0
        stmts = self._parse_block(terminators=[])

        return Algorithm(
            name=directives['name'],
            backend=directives['backend'],
            args=directives['args'],
            body=stmts,
            type_annotations=type_annotations,
        )

    def _split_sections(self) -> tuple[list[str], list[str]]:
        """Split source into pre-algorithmic lines and body lines."""
        all_lines = self.source.split('\n')
        pre_lines = []
        body_lines = []
        in_body = False

        for line in all_lines:
            stripped = line.strip()

            if re.match(r'\\begin\{algorithmic\}', stripped):
                in_body = True
                continue
            if re.match(r'\\end\{algorithmic\}', stripped):
                in_body = False
                continue
            # Also handle \begin{algorithm} wrapper
            if re.match(r'\\begin\{algorithm\}', stripped):
                continue
            if re.match(r'\\end\{algorithm\}', stripped):
                continue
            if re.match(r'\\caption\{', stripped):
                continue

            if in_body:
                if stripped:  # skip blank lines
                    body_lines.append(line)
            else:
                pre_lines.append(line)

        return pre_lines, body_lines

    def _collect_inline_types(self, lines: list[str], types: dict):
        """Extract inline type annotations from % comments on \State lines."""
        for line in lines:
            # Look for:  \State $...$ % vector
            # or:        \State $...$ % type_for:varname=vector
            m = re.search(r'%\s*(\w+)\s*$', line)
            if m:
                hint = m.group(1).lower()
                if hint in _TYPE_MAP:
                    # Infer which variable this annotates from the LHS
                    lhs_match = re.search(r'\\State\s+\$\s*([^=\$]+?)\s*=', line)
                    if lhs_match:
                        var_name = self._extract_var_name(lhs_match.group(1))
                        if var_name:
                            types[var_name] = _TYPE_MAP[hint]

    def _extract_var_name(self, lhs_latex: str) -> str | None:
        """Extract a clean variable name from a LaTeX LHS fragment."""
        # Strip \mathbf{...}, \boldsymbol{...}, etc.
        lhs = re.sub(r'\\(?:mathbf|boldsymbol|bm)\{([^}]*)\}', r'\1', lhs_latex)
        # Strip \\text{...} subscripts for naming
        lhs = re.sub(r'_\{\\text\{([^}]*)\}\}', r'_\1', lhs)
        lhs = re.sub(r'\\(\w+)', r'\1', lhs)  # \alpha -> alpha
        lhs = lhs.strip().replace(' ', '')
        return lhs if lhs else None

    # ── Statement parsing ────────────────────────────────────────────────

    def _current_line(self) -> str | None:
        if self.pos < len(self.lines):
            return self.lines[self.pos].strip()
        return None

    def _advance(self):
        self.pos += 1

    def _parse_block(self, terminators: list[str]) -> list[Stmt]:
        """Parse statements until a terminator command is found."""
        stmts = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is None:
                break

            # Check if this line starts with any terminator
            stripped = self._strip_comment(line)
            if any(stripped.startswith(t) for t in terminators):
                break

            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)

        return stmts

    def _strip_comment(self, line: str) -> str:
        """Remove trailing % comment but preserve % inside $...$."""
        in_math = False
        for i, ch in enumerate(line):
            if ch == '$':
                in_math = not in_math
            elif ch == '%' and not in_math:
                return line[:i].strip()
        return line.strip()

    def _extract_inline_comment(self, line: str) -> str:
        """Extract the % comment portion."""
        in_math = False
        for i, ch in enumerate(line):
            if ch == '$':
                in_math = not in_math
            elif ch == '%' and not in_math:
                return line[i + 1:].strip()
        return ''

    def _parse_statement(self) -> Stmt | None:
        """Parse a single statement from the current line."""
        line = self._current_line()
        if line is None:
            return None

        stripped = self._strip_comment(line)
        comment = self._extract_inline_comment(line)

        # ── \For{...} ──
        if stripped.startswith('\\For'):
            return self._parse_for(stripped)

        # ── \While{...} ──
        if stripped.startswith('\\While'):
            return self._parse_while(stripped)

        # ── \If{...} ──
        if stripped.startswith('\\If'):
            return self._parse_if(stripped)

        # ── \Return ──
        if stripped.startswith('\\Return') or stripped.startswith('\\State \\Return'):
            self._advance()
            return self._parse_return(stripped)

        # ── \State \textbf{break} or \State \Break ──
        if re.search(r'\\textbf\{break\}|\\Break|\\textbf\{Break\}', stripped):
            self._advance()
            return Break()

        # ── \State $assignment$ ──
        if stripped.startswith('\\State'):
            self._advance()
            return self._parse_state(stripped, comment)

        # Skip unrecognized lines
        self._advance()
        return None

    def _extract_math(self, text: str) -> str:
        """Extract content between $ delimiters."""
        m = re.search(r'\$(.+?)\$', text)
        if m:
            return m.group(1).strip()
        # Try without $ (some formats omit them)
        return text.strip()

    def _extract_brace_arg(self, text: str, command: str) -> str:
        """Extract the {argument} after a \\Command."""
        # Find the command, then extract balanced braces
        idx = text.find(command)
        if idx < 0:
            return ''
        rest = text[idx + len(command):]

        # Find opening brace
        brace_start = rest.find('{')
        if brace_start < 0:
            return ''

        depth = 0
        start = brace_start
        for i in range(brace_start, len(rest)):
            if rest[i] == '{':
                depth += 1
            elif rest[i] == '}':
                depth -= 1
                if depth == 0:
                    return rest[start + 1:i].strip()
        return rest[start + 1:].strip()

    # ── For loop ─────────────────────────────────────────────────────────

    def _parse_for(self, line: str) -> ForLoop:
        """Parse \\For{$k = 0, 1, \\ldots, N$}  body  \\EndFor"""
        arg = self._extract_brace_arg(line, '\\For')
        arg = arg.strip('$ ')

        var, start, end_expr = self._parse_for_range(arg)

        self._advance()  # past the \For line
        body = self._parse_block(terminators=['\\EndFor'])

        # Consume the \EndFor line
        if self._current_line() and self._strip_comment(self._current_line()).startswith('\\EndFor'):
            self._advance()

        return ForLoop(var=var, start=start, end_expr=end_expr, body=body)

    def _parse_for_range(self, arg: str) -> tuple[str, int, str]:
        """
        Parse for-loop range specifications:
          k = 0, 1, ..., N     → var='k', start=0, end='N'
          k = 0, 1, 2, ...     → var='k', start=0, end=''
          k = 1 to N           → var='k', start=1, end='N'
        """
        # Pattern: var = start, ..., end
        m = re.match(
            r'([a-zA-Z]\w*)\s*=\s*(\d+)\s*,\s*\d+\s*,?\s*'
            r'(?:\\ldots|\\dots|\\cdots|\.\.\.)\s*(?:,\s*)?'
            r'(?:\\(?:text|mathrm)\{(\w+)\}|([a-zA-Z]\w*))?',
            arg
        )
        if m:
            var = m.group(1)
            start = int(m.group(2))
            end_expr = m.group(3) or m.group(4) or ''
            return var, start, end_expr

        # Pattern: var = start to end
        m = re.match(r'([a-zA-Z]\w*)\s*=\s*(\d+)\s+(?:to|\\to)\s+(\w+)', arg)
        if m:
            return m.group(1), int(m.group(2)), m.group(3)

        # Fallback
        m = re.match(r'([a-zA-Z]\w*)', arg)
        var = m.group(1) if m else 'k'
        return var, 0, ''

    # ── While loop ───────────────────────────────────────────────────────

    def _parse_while(self, line: str) -> WhileLoop:
        arg = self._extract_brace_arg(line, '\\While')
        arg = arg.strip('$ ')
        condition = parse_condition(arg)

        self._advance()
        body = self._parse_block(terminators=['\\EndWhile'])

        if self._current_line() and self._strip_comment(self._current_line()).startswith('\\EndWhile'):
            self._advance()

        return WhileLoop(condition=condition, body=body)

    # ── If / ElsIf / Else ────────────────────────────────────────────────

    def _parse_if(self, line: str) -> Branch:
        arg = self._extract_brace_arg(line, '\\If')
        arg = arg.strip('$ ')
        condition = parse_condition(arg)

        self._advance()
        if_body = self._parse_block(
            terminators=['\\EndIf', '\\ElsIf', '\\Else']
        )

        elif_branches = []
        else_body = []

        while self._current_line():
            cur = self._strip_comment(self._current_line())
            if cur.startswith('\\ElsIf'):
                elif_arg = self._extract_brace_arg(cur, '\\ElsIf')
                elif_arg = elif_arg.strip('$ ')
                elif_cond = parse_condition(elif_arg)
                self._advance()
                elif_body = self._parse_block(
                    terminators=['\\EndIf', '\\ElsIf', '\\Else']
                )
                elif_branches.append((elif_cond, elif_body))
            elif cur.startswith('\\Else'):
                self._advance()
                else_body = self._parse_block(terminators=['\\EndIf'])
                break
            else:
                break

        if self._current_line() and self._strip_comment(self._current_line()).startswith('\\EndIf'):
            self._advance()

        return Branch(
            condition=condition,
            if_body=if_body,
            elif_branches=elif_branches,
            else_body=else_body,
        )

    # ── Return ───────────────────────────────────────────────────────────

    def _parse_return(self, line: str) -> Return:
        # Extract everything after \Return
        m = re.search(r'\\Return\s*(.*)', self._strip_comment(line))
        if not m:
            return Return(values=[])

        rest = m.group(1).strip().strip('$').strip()
        if not rest:
            return Return(values=[])

        # Parse comma-separated return values
        values = []
        for part in self._split_top_level(rest, ','):
            part = part.strip()
            if part:
                values.append(parse_latex_expr(part))

        return Return(values=values)

    def _split_top_level(self, text: str, sep: str) -> list[str]:
        """Split text by separator, respecting brace depth."""
        parts = []
        depth = 0
        current = []
        for ch in text:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append(''.join(current))
                current = []
                continue
            current.append(ch)
        parts.append(''.join(current))
        return parts

    # ── State (assignment) ───────────────────────────────────────────────

    def _parse_state(self, line: str, comment: str) -> Stmt | None:
        """Parse \\State $lhs = rhs$"""
        stripped = self._strip_comment(line)
        stripped = re.sub(r'^\\State\s*', '', stripped).strip()
        # Extract math content
        math = self._extract_math(stripped)
        if not math:
            return None

        result = parse_assignment(math)
        if result is None:
            # Not an assignment — could be a standalone expression
            expr = parse_latex_expr(math)
            return Assign(target=Var(name='_'), value=expr, comment=comment)

        target, value = result
        return Assign(target=target, value=value, comment=comment)


# ── Public API ───────────────────────────────────────────────────────────────

def parse_algorithm(source: str) -> Algorithm:
    """Parse a LaTeX source containing an algorithmic environment."""
    return AlgPseudocodeParser(source).parse()
