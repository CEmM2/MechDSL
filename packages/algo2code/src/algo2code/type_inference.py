"""
Type inference for algorithm AST nodes.

Given type annotations on variables (from % comments or directives),
propagate types through expressions to resolve:
  - Which operations are scalar (stay in Python scope)
  - Which operations are vector/matrix (become Taichi kernels)
  - What each binary operator actually means:
      * vector * vector   → dot product
      * matrix * vector   → matvec
      * scalar * vector   → axpy
      * scalar / scalar   → division
"""

from __future__ import annotations

from .ast_nodes import (
    Algorithm,
    Assign,
    BinOp,
    Branch,
    Expr,
    ForLoop,
    FuncCall,
    Number,
    Return,
    Stmt,
    UnaryOp,
    Var,
    VarType,
    WhileLoop,
)


class TypeInferrer:
    """
    Walk the AST and annotate every Expr node with its inferred VarType.
    Also resolves BinOp.op to semantically specific operations:
      '*' with (matrix, vector)  → 'matvec'
      '*' with (vector, vector)  → 'dot'     (only when one is transposed)
      '*' with (scalar, vector)  → 'scale'
    """

    def __init__(self, type_annotations: dict[str, VarType]):
        self.types = dict(type_annotations)

    def infer_algorithm(self, algo: Algorithm):
        """Run type inference on the full algorithm."""
        for name, vtype in algo.args:
            if vtype != VarType.UNKNOWN:
                self.types[name] = vtype

        self._infer_block(algo.body)

    def _infer_block(self, stmts: list[Stmt]):
        for stmt in stmts:
            self._infer_stmt(stmt)

    def _infer_stmt(self, stmt: Stmt):
        if isinstance(stmt, Assign):
            self._infer_expr(stmt.value)
            var_name = stmt.target.display
            if var_name not in self.types:
                self.types[var_name] = stmt.value.inferred_type
            stmt.target.inferred_type = self.types.get(var_name, VarType.UNKNOWN)

        elif isinstance(stmt, ForLoop):
            self.types[stmt.var] = VarType.SCALAR
            self._infer_block(stmt.body)

        elif isinstance(stmt, WhileLoop):
            self._infer_expr(stmt.condition)
            self._infer_block(stmt.body)

        elif isinstance(stmt, Branch):
            self._infer_expr(stmt.condition)
            self._infer_block(stmt.if_body)
            for cond, body in stmt.elif_branches:
                self._infer_expr(cond)
                self._infer_block(body)
            self._infer_block(stmt.else_body)

        elif isinstance(stmt, Return):
            for v in stmt.values:
                self._infer_expr(v)

    def _infer_expr(self, expr: Expr) -> VarType:
        """Infer and set the type of an expression, returning the type."""
        if isinstance(expr, Number):
            expr.inferred_type = VarType.SCALAR
            return VarType.SCALAR

        if isinstance(expr, Var):
            name = expr.display
            t = self.types.get(name, VarType.UNKNOWN)
            # Single-letter uppercase → default to matrix if unknown
            if t == VarType.UNKNOWN and len(expr.name) == 1 and expr.name.isupper():
                t = VarType.MATRIX
            expr.inferred_type = t
            return t

        if isinstance(expr, UnaryOp):
            inner = self._infer_expr(expr.operand)
            if expr.op == "norm":
                expr.inferred_type = VarType.SCALAR
            elif expr.op == "transpose":
                expr.inferred_type = inner  # transpose preserves type
            elif expr.op == "neg" or expr.op == "inverse":
                expr.inferred_type = inner
            else:
                expr.inferred_type = inner
            return expr.inferred_type

        if isinstance(expr, BinOp):
            lt = self._infer_expr(expr.left)
            rt = self._infer_expr(expr.right)
            expr.inferred_type = self._resolve_binop(expr, lt, rt)
            return expr.inferred_type

        if isinstance(expr, FuncCall):
            for arg in expr.args:
                self._infer_expr(arg)
            self._infer_expr(expr.func)
            if expr.args:
                expr.inferred_type = expr.args[0].inferred_type
            else:
                expr.inferred_type = VarType.UNKNOWN
            # Check if func is an inverse of a callable
            if isinstance(expr.func, UnaryOp) and expr.func.op == "inverse":
                base = expr.func.operand
                if isinstance(base, Var):
                    self.types[base.display] = VarType.CALLABLE
            return expr.inferred_type

        expr.inferred_type = VarType.UNKNOWN
        return VarType.UNKNOWN

    def _resolve_binop(self, expr: BinOp, lt: VarType, rt: VarType) -> VarType:
        """Resolve the semantic meaning of a binary operation given operand types."""
        op = expr.op

        if op in ("+", "-"):
            if lt == VarType.VECTOR or rt == VarType.VECTOR:
                return VarType.VECTOR
            if lt == VarType.MATRIX or rt == VarType.MATRIX:
                return VarType.MATRIX
            return VarType.SCALAR

        if op == "/":
            return VarType.SCALAR

        if op == "*":
            return self._resolve_multiply(expr, lt, rt)

        if op == "pow":
            return lt

        if op in ("<", ">", "<=", ">=", "==", "!="):
            return VarType.SCALAR

        return VarType.UNKNOWN

    def _resolve_multiply(self, expr: BinOp, lt: VarType, rt: VarType) -> VarType:
        """
        Resolve multiplication semantics:
          transposed_vector * vector  →  dot product (scalar result)
          matrix * vector             →  matvec (vector result)
          scalar * vector             →  scale (vector result)
          scalar * scalar             →  multiply (scalar result)
        """
        left_is_transposed = isinstance(expr.left, UnaryOp) and expr.left.op == "transpose"

        if left_is_transposed and rt == VarType.VECTOR:
            expr.op = "dot"
            return VarType.SCALAR

        if left_is_transposed and rt == VarType.MATRIX:
            expr.op = "dot"
            return VarType.VECTOR

        if lt == VarType.MATRIX and rt == VarType.VECTOR:
            expr.op = "matvec"
            return VarType.VECTOR

        if lt == VarType.MATRIX and rt == VarType.MATRIX:
            expr.op = "matmul"
            return VarType.MATRIX

        if lt == VarType.SCALAR and rt == VarType.VECTOR:
            expr.op = "scale"
            return VarType.VECTOR

        if lt == VarType.VECTOR and rt == VarType.SCALAR:
            expr.op = "scale"
            return VarType.VECTOR

        if lt == VarType.SCALAR and rt == VarType.MATRIX:
            expr.op = "scale"
            return VarType.MATRIX

        # Default: scalar multiply
        return VarType.SCALAR


def infer_types(algo: Algorithm):
    """Run type inference on an Algorithm AST, mutating nodes in place."""
    inferrer = TypeInferrer(algo.type_annotations)
    inferrer.infer_algorithm(algo)
    # Write back discovered types
    algo.type_annotations = inferrer.types
