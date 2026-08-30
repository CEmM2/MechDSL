"""
AST node definitions for algorithmic pseudocode → code transpiler.

Two-level AST:
  1. Control-flow nodes (ForLoop, WhileLoop, Branch, Assign, Return, Break)
  2. Expression nodes (BinOp, UnaryOp, FuncCall, Var, Scalar, Norm, Transpose)

The expression nodes are *typed* (scalar / vector / matrix / callable)
to drive correct code generation for Taichi kernels vs. Python-scope code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

# ── Type system ──────────────────────────────────────────────────────────────


class VarType(Enum):
    SCALAR = auto()
    VECTOR = auto()
    MATRIX = auto()
    CALLABLE = auto()  # e.g. preconditioner M^{-1}
    UNKNOWN = auto()


# ── Expression nodes ─────────────────────────────────────────────────────────


@dataclass
class Expr:
    """Base class for all expression nodes."""

    inferred_type: VarType = field(default=VarType.UNKNOWN, repr=False)


@dataclass
class Var(Expr):
    """A named variable:  x, r, A, \\alpha, \\rho_{\\text{new}}, etc."""

    name: str = ""
    subscript: str | None = None  # e.g. "new" from \rho_{\text{new}}

    def __post_init__(self):
        super().__init__()

    @property
    def display(self) -> str:
        if self.subscript:
            return f"{self.name}_{self.subscript}"
        return self.name


@dataclass
class Number(Expr):
    """A literal number."""

    value: float = 0.0

    def __post_init__(self):
        super().__init__(inferred_type=VarType.SCALAR)


@dataclass
class BinOp(Expr):
    """Binary operation:  a + b,  A*p,  r^T z,  a/b,  etc."""

    op: str = ""  # '+', '-', '*', '/', 'dot', 'matvec', 'matmul'
    left: Expr = field(default_factory=Expr)
    right: Expr = field(default_factory=Expr)

    def __post_init__(self):
        super().__init__()


@dataclass
class UnaryOp(Expr):
    """Unary operation:  -x, ‖r‖, etc."""

    op: str = ""  # 'neg', 'norm', 'transpose'
    operand: Expr = field(default_factory=Expr)

    def __post_init__(self):
        super().__init__()


@dataclass
class FuncCall(Expr):
    """Function application:  M^{-1}(r), f(x,y), etc."""

    func: Expr = field(default_factory=Expr)
    args: list[Expr] = field(default_factory=list)

    def __post_init__(self):
        super().__init__()


# ── Control-flow nodes ───────────────────────────────────────────────────────


@dataclass
class Stmt:
    """Base class for all statement nodes."""

    pass


@dataclass
class Assign(Stmt):
    """Assignment:  x = expr"""

    target: Var = field(default_factory=Var)
    value: Expr = field(default_factory=Expr)
    comment: str = ""  # inline annotation: "% vector", "% matvec"


@dataclass
class ForLoop(Stmt):
    """For loop:  \\For{k = 0, 1, ..., maxiter}  body  \\EndFor"""

    var: str = ""
    start: int = 0
    end_expr: str = ""  # e.g. "maxiter", or "" for indefinite
    body: list[Stmt] = field(default_factory=list)


@dataclass
class WhileLoop(Stmt):
    """While loop:  \\While{cond}  body  \\EndWhile"""

    condition: Expr = field(default_factory=Expr)
    body: list[Stmt] = field(default_factory=list)


@dataclass
class Branch(Stmt):
    """If / ElsIf / Else:  \\If{cond}  body  \\EndIf"""

    condition: Expr = field(default_factory=Expr)
    if_body: list[Stmt] = field(default_factory=list)
    elif_branches: list[tuple[Expr, list[Stmt]]] = field(default_factory=list)
    else_body: list[Stmt] = field(default_factory=list)


@dataclass
class Return(Stmt):
    """Return statement:  \\Return expr"""

    values: list[Expr] = field(default_factory=list)


@dataclass
class Break(Stmt):
    """Break statement."""

    pass


# ── Top-level algorithm ──────────────────────────────────────────────────────


@dataclass
class Algorithm:
    """A complete parsed algorithm."""

    name: str = ""
    backend: str = "taichi"
    args: list[tuple[str, VarType]] = field(default_factory=list)
    body: list[Stmt] = field(default_factory=list)
    type_annotations: dict[str, VarType] = field(default_factory=dict)  # var_name -> type
