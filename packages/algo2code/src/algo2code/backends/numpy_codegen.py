"""
NumPy code generator.

Takes the same typed Algorithm AST as the Taichi backend and emits a plain
Python function that depends on NumPy only. The generated module never
imports Taichi, so algorithms transpiled with this backend run on a lean
install (no ``[verify]`` extra).

The lowering mirrors :class:`~algo2code.backends.taichi_codegen.TaichiEmitter`
statement for statement, so the two backends agree on semantics:

  - Scalar arithmetic and control flow are emitted exactly as in the Taichi
    driver (plain Python on floats), so a scalar-only algorithm produces the
    same function body under both backends and yields bit-identical results.
  - Vector/matrix variables are ``numpy.ndarray`` buffers. Local working
    vectors are allocated once with ``np.zeros(n)`` and every vector operation
    writes *in place* (``out[...] = ...``), matching the Taichi field model:
    a vector argument updated by the algorithm is updated for the caller too.
  - Callables keep the in-place seam contract of the Taichi backend:
    ``M_inv(r, z)`` writes into ``z``, and a matrix-free operator declared
    ``% type A callable`` is applied as ``A(out, p)``.
  - ``dot`` lowers to ``float(np.dot(a, b))``, ``norm`` to
    ``float(np.linalg.norm(a))``, a stored-matrix product to ``A @ x``.
"""

from __future__ import annotations

from ..ast_nodes import Algorithm, Assign, BinOp, Expr, FuncCall, UnaryOp, Var, VarType
from ..errors import UnsupportedConstructError
from .taichi_codegen import (
    RUNTIME_INLINE,
    TaichiEmitter,
    _collect_arg_names,
    _collect_vector_vars,
    _var_name,
)


class NumpyEmitter(TaichiEmitter):
    """Emit a NumPy-only Python function from a typed Algorithm AST."""

    BACKEND_DOC = "Backend: NumPy (CPU)"

    def __init__(self, algo: Algorithm):
        super().__init__(algo, runtime=RUNTIME_INLINE)

    def emit(self) -> str:
        """Generate the complete NumPy source."""
        self._arg_names = _collect_arg_names(self.algo)
        self._vector_vars = _collect_vector_vars(self.algo)
        self._pre_scan_temps(self.algo.body)

        parts = ["import numpy as np\n", "# ── Solver driver " + "─" * 57, self._emit_driver()]
        return "\n\n".join(parts) + "\n"

    # ── Allocation ───────────────────────────────────────────────────────

    def _vector_field_alloc(self, vec_arg: str | None) -> str:
        return "np.zeros(n)"

    # ── Expressions ──────────────────────────────────────────────────────

    def _emit_assign(self, stmt: Assign) -> None:
        target = _var_name(stmt.target)
        target_type = self.algo.type_annotations.get(stmt.target.display, stmt.target.inferred_type)
        if (
            target_type == VarType.VECTOR
            and isinstance(stmt.value, Var)
            and stmt.value.inferred_type == VarType.VECTOR
        ):
            self._write(f"{target}[...] = {_var_name(stmt.value)}")
            return
        super()._emit_assign(stmt)

    def _emit_unary(self, expr: UnaryOp) -> str:
        if expr.op == "norm" and expr.operand.inferred_type != VarType.SCALAR:
            return f"float(np.linalg.norm({self._emit_expr_str(expr.operand)}))"
        return super()._emit_unary(expr)

    def _emit_dot(self, expr: BinOp) -> str:
        left = expr.left
        if isinstance(left, UnaryOp) and left.op == "transpose":
            left = left.operand
        return f"float(np.dot({self._emit_expr_str(left)}, {self._emit_expr_str(expr.right)}))"

    def _emit_func_call_name(self, expr: FuncCall) -> str:
        if isinstance(expr.func, Var) and _var_name(expr.func) == "sqrt":
            return "np.sqrt"
        return super()._emit_func_call_name(expr)

    # ── Vector lowering (in-place writes into ndarray buffers) ───────────

    def _lower_vector_expr(self, expr: Expr, dest: str | None) -> str:
        if isinstance(expr, Var):
            name = _var_name(expr)
            if dest is not None and dest != name:
                self._write(f"{dest}[...] = {name}")
                return dest
            return name

        if isinstance(expr, FuncCall):
            out = dest if dest is not None else self._get_temp()
            func = self._emit_func_call_name(expr)
            args = ", ".join(self._emit_expr_str(a) for a in expr.args)
            self._write(f"{func}({args}, {out})")
            return out

        if isinstance(expr, UnaryOp) and expr.op == "neg":
            vec = self._lower_to_field(expr.operand)
            out = dest if dest is not None else self._get_temp()
            self._write(f"{out}[...] = -{vec}")
            return out

        if isinstance(expr, BinOp):
            if expr.op == "matvec":
                out = dest if dest is not None else self._get_temp()
                vec = self._lower_to_field(expr.right)
                if expr.left.inferred_type == VarType.CALLABLE:
                    self._write(f"{self._emit_expr_str(expr.left)}({out}, {vec})")
                    return out
                self._write(f"{out}[...] = {self._emit_expr_str(expr.left)} @ {vec}")
                return out

            if expr.op in ("scale", "*"):
                scalar, vec_expr = self._split_scale(expr)
                if scalar is not None and vec_expr is not None:
                    vec = self._lower_to_field(vec_expr)
                    out = dest if dest is not None else self._get_temp()
                    self._write(f"{out}[...] = {scalar} * {vec}")
                    return out

            if expr.op in ("+", "-"):
                left = self._lower_to_field(expr.left)
                coeff, right = self._lower_addend(expr.right)
                beta = self._negate(coeff) if expr.op == "-" else coeff
                out = dest if dest is not None else self._get_temp()
                self._write(f"{out}[...] = {left} + {beta} * {right}")
                return out

        raise UnsupportedConstructError(
            f"cannot lower vector expression to NumPy ops: {expr!r}. "
            f"Supported vector forms are copy, callable application, matvec, "
            f"scalar*vector, and vector +/- vector."
        )


def generate_numpy(algo: Algorithm) -> str:
    """Generate NumPy source code from a typed Algorithm AST.

    The emitted module imports only ``numpy`` and defines one function named
    after the algorithm, with the same signature and return values as the
    Taichi backend's driver.
    """
    return NumpyEmitter(algo).emit()
