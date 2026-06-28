"""
Taichi code generator.

Takes a typed Algorithm AST and emits:
  1. Taichi kernel functions for vector/matrix operations (matvec, dot, axpy, norm)
  2. A Python driver function that calls the kernels in the right order

Design decisions:
  - Vector/matrix variables are allocated as Taichi fields inside the driver
  - The loop driver stays in Python scope (Taichi doesn't support
    dynamic convergence checks inside kernels well)
  - Each heavy linear-algebra op gets its own @ti.kernel
  - Scalar arithmetic stays in the driver
  - Vector assignment (p = z) emits _copy(z, p), not Python reference aliasing

Import modes (``runtime`` parameter of :func:`generate_taichi`):
  - ``"inline"`` (default): emit private ``@ti.kernel`` definitions inline in
    each generated file — backward-compatible, no runtime dependency.
  - ``"ti_runtime"``: emit ``from ti_runtime import vector_ops as _v`` and call
    the shared primitives for ``dot``/``norm``/``copy``/``vec_add``; only
    ``_matvec`` remains inlined (the matrix-free operator seam is P2-2's
    concern).  algo2code itself never imports ``ti_runtime`` — it only *emits*
    the import line.

Compatibility note (``"ti_runtime"`` mode):
  ``ti_runtime.vector_ops.dot`` uses ``x[I].dot(y[I])`` which requires
  ``ti.Vector.field`` arguments.  algo2code emits ``ti.field(ti.f64, shape=n)``
  scalar fields, so ``_v.dot``/``_v.norm2`` will raise at Taichi JIT time if
  the consumer passes scalar fields.  Callers that use vector fields (e.g.
  mechdsl FEM drivers) are unaffected.  This is a known field-model mismatch;
  resolving it (either by changing the emitted field model to ``ti.Vector.field``
  or by adding scalar variants to ti_runtime) is out of scope for P2-1.
"""

from __future__ import annotations

import contextlib

from ..ast_nodes import (
    Algorithm,
    Assign,
    BinOp,
    Branch,
    Break,
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
from ..errors import UnsupportedConstructError

# Literal sentinel values for the ``runtime`` parameter.
RUNTIME_INLINE = "inline"
RUNTIME_TI_RUNTIME = "ti_runtime"

# ── Variable name sanitization ───────────────────────────────────────────────

_GREEK_MAP = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "epsilon": "eps",
    "varepsilon": "eps",
    "zeta": "zeta",
    "eta": "eta",
    "theta": "theta",
    "iota": "iota",
    "kappa": "kappa",
    "lambda": "lam",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "pi": "pi_val",
    "rho": "rho",
    "sigma": "sigma",
    "tau": "tau",
    "phi": "phi",
    "varphi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "omega",
}


def _sanitize(name: str) -> str:
    """Convert a LaTeX variable name to a valid Python identifier."""
    if name in _GREEK_MAP:
        return _GREEK_MAP[name]
    name = name.replace("{", "").replace("}", "").replace("\\", "")
    name = name.replace(" ", "_").replace("-", "_")
    if name in ("lambda", "in", "is", "not", "and", "or", "from", "import"):
        name = name + "_"
    return name


def _var_name(v: Var) -> str:
    """Get the Python name for a Var node."""
    base = _sanitize(v.name)
    if v.subscript:
        sub = _sanitize(v.subscript)
        return f"{base}_{sub}"
    return base


# ── Kernel collector ─────────────────────────────────────────────────────────


class KernelCollector:
    """Walk the AST and identify which standard kernels are needed."""

    def __init__(self):
        self.needed_kernels: set[str] = set()

    def scan(self, stmts: list[Stmt]):
        for stmt in stmts:
            self._scan_stmt(stmt)

    def _scan_stmt(self, stmt: Stmt):
        if isinstance(stmt, Assign):
            self._scan_expr(stmt.value)
            if (
                stmt.target.inferred_type == VarType.VECTOR
                and isinstance(stmt.value, Var)
                and stmt.value.inferred_type == VarType.VECTOR
            ):
                self.needed_kernels.add("copy")
        elif isinstance(stmt, ForLoop):
            self.scan(stmt.body)
        elif isinstance(stmt, WhileLoop):
            self._scan_expr(stmt.condition)
            self.scan(stmt.body)
        elif isinstance(stmt, Branch):
            self._scan_expr(stmt.condition)
            self.scan(stmt.if_body)
            for cond, body in stmt.elif_branches:
                self._scan_expr(cond)
                self.scan(body)
            self.scan(stmt.else_body)
        elif isinstance(stmt, Return):
            for v in stmt.values:
                self._scan_expr(v)

    def _scan_expr(self, expr: Expr):
        if isinstance(expr, BinOp):
            self._scan_expr(expr.left)
            self._scan_expr(expr.right)
            if expr.op == "dot":
                self.needed_kernels.add("dot")
            elif expr.op == "matvec":
                # A matrix-free callable operator (`% type A callable`, §8.3)
                # lowers `A · p` to an in-place call A(out, p); it needs no
                # dense `_matvec` kernel. Only a stored MATRIX operand does.
                if expr.left.inferred_type != VarType.CALLABLE:
                    self.needed_kernels.add("matvec")
            elif expr.op == "scale" or (
                expr.op in ("+", "-") and expr.inferred_type == VarType.VECTOR
            ):
                self.needed_kernels.add("vec_add")
        elif isinstance(expr, UnaryOp):
            self._scan_expr(expr.operand)
            if expr.op == "norm":
                self.needed_kernels.add("norm")
        elif isinstance(expr, FuncCall):
            for arg in expr.args:
                self._scan_expr(arg)

    def emit_kernels(self, runtime: str = RUNTIME_INLINE) -> str:
        """Emit kernel definitions (inline mode) or nothing (ti_runtime mode).

        In ``"ti_runtime"`` mode the shared primitives (dot/norm/copy/vec_add)
        are called via the ``_v`` alias imported from ``ti_runtime.vector_ops``.
        Only ``_matvec`` has no ti_runtime equivalent and remains inlined
        (the matrix-free operator seam is P2-2's concern).
        """
        lines = []
        if runtime == RUNTIME_TI_RUNTIME:
            # dot/norm/copy/vec_add are routed to ti_runtime; only emit _matvec.
            if "matvec" in self.needed_kernels:
                lines.append(_K_MATVEC)
        else:
            if "dot" in self.needed_kernels:
                lines.append(_K_DOT)
            if "norm" in self.needed_kernels:
                lines.append(_K_NORM)
            if "matvec" in self.needed_kernels:
                lines.append(_K_MATVEC)
            if "vec_add" in self.needed_kernels:
                lines.append(_K_VEC_ADD)
            if "copy" in self.needed_kernels:
                lines.append(_K_COPY)
        return "\n\n".join(lines)


# ── Kernel templates ─────────────────────────────────────────────────────────

_K_DOT = """@ti.kernel
def _dot(a: ti.template(), b: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * b[i]
    return result"""

_K_NORM = """@ti.kernel
def _norm(a: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * a[i]
    return ti.sqrt(result)"""

_K_MATVEC = """@ti.kernel
def _matvec(A: ti.template(), x: ti.template(), out: ti.template()):
    for i in out:
        s = 0.0
        for j in range(x.shape[0]):
            s += A[i, j] * x[j]
        out[i] = s"""

_K_VEC_ADD = '''@ti.kernel
def _vec_add(alpha: ti.f64, x: ti.template(), beta: ti.f64,
             y: ti.template(), out: ti.template()):
    """out[i] = alpha*x[i] + beta*y[i]"""
    for i in out:
        out[i] = alpha * x[i] + beta * y[i]'''

_K_COPY = """@ti.kernel
def _copy(src: ti.template(), dst: ti.template()):
    for i in dst:
        dst[i] = src[i]"""


# ── Variable scanner ─────────────────────────────────────────────────────────


def _collect_vector_vars(algo: Algorithm) -> set[str]:
    """Find all vector-typed variable names that need field allocation."""
    vecs = set()
    for name, vtype in algo.type_annotations.items():
        if vtype == VarType.VECTOR:
            vecs.add(_sanitize(name))
    return vecs


def _collect_arg_names(algo: Algorithm) -> set[str]:
    return {name for name, _ in algo.args}


# ── Code emitter ─────────────────────────────────────────────────────────────


class TaichiEmitter:
    """Emit complete Taichi code from a typed Algorithm AST.

    Parameters
    ----------
    algo:
        Typed Algorithm AST to emit.
    runtime:
        Import mode — ``"inline"`` (default) or ``"ti_runtime"``.  See module
        docstring for the full description of each mode.
    """

    def __init__(self, algo: Algorithm, runtime: str = RUNTIME_INLINE):
        self.algo = algo
        self.runtime = runtime
        self.lines: list[str] = []
        self._indent = 0
        self._temp_counter = 0
        self._needed_temp_count = 0
        self._peak_temps = 0
        self._arg_names: set[str] = set()
        self._vector_vars: set[str] = set()

    def emit(self) -> str:
        """Generate the complete Taichi source."""
        self._arg_names = _collect_arg_names(self.algo)
        self._vector_vars = _collect_vector_vars(self.algo)

        collector = KernelCollector()
        collector.scan(self.algo.body)

        # Pre-scan for temp count
        self._pre_scan_temps(self.algo.body)

        if self.runtime == RUNTIME_TI_RUNTIME:
            self._check_runtime_mode_supported(collector)

        parts = []
        parts.append("import taichi as ti\n")
        parts.append("ti.init(arch=ti.gpu, default_fp=ti.f64)\n")

        if self.runtime == RUNTIME_TI_RUNTIME:
            parts.append("from ti_runtime import vector_ops as _v\n")

        kernels = collector.emit_kernels(runtime=self.runtime)
        if kernels:
            parts.append("# ── Taichi kernels " + "─" * 56)
            parts.append(kernels)
            parts.append("")

        parts.append("# ── Solver driver " + "─" * 57)
        parts.append(self._emit_driver())

        return "\n\n".join(parts) + "\n"

    def _pre_scan_temps(self, stmts: list[Stmt]):
        """Discover how many temporary vector fields the driver needs.

        Rather than re-deriving the count from a parallel traversal (which drifts
        from the real lowering — the F1 root cause was exactly such a mismatch),
        we *dry-run* the actual body emission into a throwaway buffer. Every
        ``_get_temp`` call updates ``_peak_temps``; the temp counter resets per
        statement (temps are scratch within one statement and reused across
        statements), so the peak is the number of fields to allocate once.
        ``_emit_driver`` overwrites ``lines``/``indent``/``temp_counter`` for the
        real pass, so no save/restore is needed here.
        """
        self.lines = []
        self._indent = 0
        self._temp_counter = 0
        self._peak_temps = 0
        # A genuinely un-lowerable construct will raise again — and be reported —
        # during the real emission pass, so don't let the dry run fail here.
        with contextlib.suppress(UnsupportedConstructError):
            self._emit_block(stmts)
        self._needed_temp_count = self._peak_temps

    def _emit_driver(self) -> str:
        self.lines = []
        self._indent = 0
        self._temp_counter = 0

        args = self._build_arg_list()
        self._write(f"def {self.algo.name}({args}):")
        self._indent += 1

        self._write('"""')
        self._write("Auto-generated from LaTeX algorithmic environment.")
        self._write("Backend: Taichi (GPU)")
        self._write('"""')

        vec_arg = self._first_vector_arg()
        local_vecs = self._vector_vars - self._arg_names
        requires_vector_length = bool(local_vecs) or self._needed_temp_count > 0
        needs_n = requires_vector_length or vec_arg is not None
        if needs_n:
            if vec_arg:
                self._write(f"n = {vec_arg}.shape[0]")
            elif requires_vector_length:
                self._write(
                    'raise ValueError("Cannot infer vector length n for this generated Taichi driver: '
                    "the algorithm allocates local vectors or temporary vector fields, but no vector "
                    'argument is available to determine n.")'
                )
            else:
                # post_recovery_plan Phase 5 codegen fix: previously
                # emitted ``n = b.shape[0]`` unconditionally, which
                # broke scalar/matrix-only algorithms with no vector
                # argument. Keep a harmless marker only when no
                # vector-sized allocation depends on n.
                self._write("n = 0  # no vector arg present; scalar/matrix-only algorithm")

        if local_vecs or self._needed_temp_count > 0:
            self._write("")
            self._write("# Allocate working vectors")
            alloc = self._vector_field_alloc(vec_arg)
            for name in sorted(local_vecs):
                self._write(f"{name} = {alloc}")
            for i in range(self._needed_temp_count):
                self._write(f"_tmp{i} = {alloc}")

        self._write("")

        self._emit_block(self.algo.body)

        self._indent -= 1
        return "\n".join(self.lines)

    def _first_vector_arg(self) -> str | None:
        for name, vtype in self.algo.args:
            if vtype == VarType.VECTOR:
                return name
        return None

    def _vector_field_alloc(self, vec_arg: str | None) -> str:
        """Return the field-allocation expression for a local/temp working vector.

        Inline mode keeps the historical scalar layout ``ti.field(ti.f64,
        shape=n)`` — byte-stable, so existing consumers and goldens are
        unaffected. ``ti_runtime`` mode instead allocates ``ti.Vector.field``
        locals matching the *vector argument's* component layout (``<arg>.n``):
        the ``ti_runtime`` ``dot``/``norm2`` primitives use ``x[I].dot(y[I])``,
        which requires vector fields. This is what lets the matrix-free seam
        (P2-2) run end-to-end against ``ti_runtime`` (resolving the field-model
        mismatch P2-1 documented). With no vector argument the component count
        is unknown, so fall back to the scalar layout.
        """
        if self.runtime == RUNTIME_TI_RUNTIME and vec_arg is not None:
            return f"ti.Vector.field({vec_arg}.n, ti.f64, shape=n)"
        return "ti.field(ti.f64, shape=n)"

    def _check_runtime_mode_supported(self, collector: KernelCollector) -> None:
        """Fail loud on ``ti_runtime``-mode inputs that would emit non-runnable code.

        Runtime mode targets the matrix-free seam over ``ti.Vector.field`` DOF
        vectors, so two preconditions must hold (otherwise the emitter would
        silently produce code that crashes at Taichi JIT):

        * **callable operator** — a stored ``MATRIX`` operand lowers to a dense,
          scalar-indexed ``_matvec``, incompatible with the ``ti.Vector.field``
          locals and the ``ti_runtime`` ``dot``/``norm2`` reductions
          (``x[I].dot(y[I])``). Declare the operator ``callable``
          (e.g. ``% type A callable``) to use the in-place ``A(out, x)`` seam.
        * **a vector argument** — needed to size the ``ti.Vector.field`` locals
          (``<arg>.n``). Without one the locals fall back to the scalar layout,
          on which ``_v.dot``/``_v.norm2`` cannot run.

        Both are rejected here, before emission, with the specific reason.
        """
        if "matvec" in collector.needed_kernels:
            raise UnsupportedConstructError(
                "runtime='ti_runtime' requires a matrix-free callable operator: "
                "declare the system operator callable (e.g. `% type A callable`). "
                "A matrix-typed operator lowers to a dense scalar-indexed matvec, "
                "incompatible with the ti.Vector.field layout used in runtime mode."
            )
        uses_vectors = (
            bool(self._vector_vars - self._arg_names)
            or self._needed_temp_count > 0
            or bool({"dot", "copy", "vec_add"} & collector.needed_kernels)
        )
        if uses_vectors and self._first_vector_arg() is None:
            raise UnsupportedConstructError(
                "runtime='ti_runtime' needs a vector argument to size its "
                "ti.Vector.field working vectors (`<arg>.n`); none was declared."
            )

    def _build_arg_list(self) -> str:
        if self.algo.args:
            return ", ".join(name for name, _ in self.algo.args)
        return "A, b, x, M_inv=None, tol=1e-10, maxiter=1000"

    def _write(self, text: str):
        self.lines.append("    " * self._indent + text)

    def _emit_block(self, stmts: list[Stmt]):
        for stmt in stmts:
            self._emit_stmt(stmt)

    def _emit_stmt(self, stmt: Stmt):
        # Temps are scratch within a single statement; reset so they are reused
        # across statements (only the per-statement peak is allocated).
        self._temp_counter = 0
        if isinstance(stmt, Assign):
            self._emit_assign(stmt)
        elif isinstance(stmt, ForLoop):
            self._emit_for(stmt)
        elif isinstance(stmt, WhileLoop):
            self._emit_while(stmt)
        elif isinstance(stmt, Branch):
            self._emit_branch(stmt)
        elif isinstance(stmt, Return):
            self._emit_return(stmt)
        elif isinstance(stmt, Break):
            self._write("break")

    # ── Assignment ───────────────────────────────────────────────────────

    def _emit_assign(self, stmt: Assign):
        target = _var_name(stmt.target)
        target_type = self.algo.type_annotations.get(stmt.target.display, stmt.target.inferred_type)

        # Vector ← simple vector: copy
        if (
            target_type == VarType.VECTOR
            and isinstance(stmt.value, Var)
            and stmt.value.inferred_type == VarType.VECTOR
        ):
            src = _var_name(stmt.value)
            if self.runtime == RUNTIME_TI_RUNTIME:
                # ti_runtime.vector_ops.copy(dst, src) — reversed arg order
                self._write(f"_v.copy({target}, {src})")
            else:
                self._write(f"_copy({src}, {target})")
            return

        # Vector ← callable(args): in-place  e.g. M_inv(r, z) not z = M_inv(r)
        if target_type == VarType.VECTOR and isinstance(stmt.value, FuncCall):
            func_code = self._emit_func_call_name(stmt.value)
            args = ", ".join(self._emit_expr_str(a) for a in stmt.value.args)
            self._write(f"{func_code}({args}, {target})")
            return

        value_code = self._emit_expr(stmt.value, target_var=target)
        if value_code is not None:
            self._write(f"{target} = {value_code}")

    # ── Expression emission ──────────────────────────────────────────────

    def _emit_expr_str(self, expr: Expr) -> str:
        """Like _emit_expr but asserts a value is returned (no target_var side-effect path)."""
        result = self._emit_expr(expr)
        assert result is not None, f"expression emitted no value: {expr!r}"
        return result

    def _emit_expr(self, expr: Expr, target_var: str | None = None) -> str | None:
        if isinstance(expr, Number):
            v = expr.value
            return str(int(v)) if v == int(v) else str(v)
        if isinstance(expr, Var):
            return _var_name(expr)
        if isinstance(expr, UnaryOp):
            # A vector-valued negation (w = -v) must lower to a kernel call, not
            # Python field arithmetic. Scalar/transpose/norm stay inline.
            if expr.inferred_type == VarType.VECTOR and expr.op == "neg":
                result = self._lower_vector_expr(expr, dest=target_var)
                return None if target_var is not None else result
            return self._emit_unary(expr)
        if isinstance(expr, BinOp):
            return self._emit_binop(expr, target_var)
        if isinstance(expr, FuncCall):
            return self._emit_func_call(expr)
        raise UnsupportedConstructError(
            f"cannot emit code for expression node {type(expr).__name__}: {expr!r}"
        )

    def _emit_unary(self, expr: UnaryOp) -> str:
        inner = self._emit_expr_str(expr.operand)
        if expr.op == "neg":
            return f"(-{inner})"
        if expr.op == "norm":
            # |scalar| is absolute value; ||vector|| is the Euclidean norm kernel.
            if expr.operand.inferred_type == VarType.SCALAR:
                return f"abs({inner})"
            if self.runtime == RUNTIME_TI_RUNTIME:
                return f"_v.norm2({inner})"
            return f"_norm({inner})"
        if expr.op in ("transpose", "inverse"):
            return inner  # semantic, handled at binop / funccall level
        raise UnsupportedConstructError(
            f"cannot emit code for unary operator {expr.op!r} on {expr.operand!r}"
        )

    def _emit_binop(self, expr: BinOp, target_var: str | None) -> str | None:
        if expr.op == "dot":
            return self._emit_dot(expr)
        # All vector-valued binary ops (matvec, scale, +, -) lower through the
        # SSA pass: every emitted op is a single kernel call writing a field,
        # so arbitrarily nested RHS like `r + beta*(p - omega*v)` is faithful
        # (issue #307 F1). When a target field is given the result is written
        # there and None is returned; otherwise a fresh temp field name is.
        if expr.inferred_type == VarType.VECTOR and expr.op in (
            "matvec",
            "scale",
            "*",
            "+",
            "-",
        ):
            result = self._lower_vector_expr(expr, dest=target_var)
            return None if target_var is not None else result

        # Scalar
        left = self._emit_expr(expr.left)
        right = self._emit_expr(expr.right)
        op_map = {
            "+": "+",
            "-": "-",
            "*": "*",
            "/": "/",
            "pow": "**",
            "<": "<",
            ">": ">",
            "<=": "<=",
            ">=": ">=",
            "==": "==",
            "!=": "!=",
        }
        op = op_map.get(expr.op, expr.op)
        return f"({left} {op} {right})"

    def _emit_dot(self, expr: BinOp) -> str:
        left = expr.left
        if isinstance(left, UnaryOp) and left.op == "transpose":
            left = left.operand
        if self.runtime == RUNTIME_TI_RUNTIME:
            return f"_v.dot({self._emit_expr(left)}, {self._emit_expr(expr.right)})"
        return f"_dot({self._emit_expr(left)}, {self._emit_expr(expr.right)})"

    # ── SSA vector lowering (issue #307 F1) ──────────────────────────────
    #
    # Any vector-valued expression is lowered to a chain of single-kernel-call
    # operations, each writing a fresh temporary field, with the final op
    # writing the destination. This replaces the old one-level decomposition
    # that emitted invalid ``ti.field`` Python arithmetic for nested RHS such as
    # ``r + beta*(p - omega*v)``. ``scalar * vector`` factors fuse into the
    # parent axpy coefficient, so the common solver updates stay a single
    # ``_vec_add`` and only genuinely nested sub-expressions cost a temp.

    def _lower_vector_expr(self, expr: Expr, dest: str | None) -> str:
        """Lower a vector expression to kernel calls; return the result field.

        ``dest`` is the destination field name, or None to materialise into a
        fresh temporary. Every branch emits at most one kernel call plus the
        calls from its recursively-lowered operands.
        """
        if isinstance(expr, Var):
            name = _var_name(expr)
            if dest is not None and dest != name:
                # ti_runtime.vector_ops.copy(dst, src) — note arg order is
                # reversed from the inlined _copy(src, dst) kernel.
                if self.runtime == RUNTIME_TI_RUNTIME:
                    self._write(f"_v.copy({dest}, {name})")
                else:
                    self._write(f"_copy({name}, {dest})")
                return dest
            return name

        if isinstance(expr, FuncCall):
            # In-place callable: M_inv(r, out) — out is the last argument.
            out = dest if dest is not None else self._get_temp()
            func = self._emit_func_call_name(expr)
            args = ", ".join(self._emit_expr_str(a) for a in expr.args)
            self._write(f"{func}({args}, {out})")
            return out

        if isinstance(expr, UnaryOp) and expr.op == "neg":
            vec = self._lower_to_field(expr.operand)
            out = dest if dest is not None else self._get_temp()
            if self.runtime == RUNTIME_TI_RUNTIME:
                # ti_runtime.vec_add(out, a, x, b, y) — note arg order differs
                # from the inlined _vec_add(alpha, x, beta, y, out)
                self._write(f"_v.vec_add({out}, -1.0, {vec}, 0.0, {vec})")
            else:
                self._write(f"_vec_add(-1.0, {vec}, 0.0, {vec}, {out})")
            return out

        if isinstance(expr, BinOp):
            if expr.op == "matvec":
                out = dest if dest is not None else self._get_temp()
                vec = self._lower_to_field(expr.right)
                # Matrix-free operator seam (11-ALGO2CODE §8.3): a CALLABLE
                # operand `A` is applied in place — `A(out, vec)`, matching the
                # ti_runtime `apply_A(out, x)` contract — instead of a dense
                # `_matvec` over a stored matrix field. The op name comes from
                # the operator Var the same way an `M_inv(...)` callable does.
                if expr.left.inferred_type == VarType.CALLABLE:
                    op_name = self._emit_expr_str(expr.left)
                    self._write(f"{op_name}({out}, {vec})")
                    return out
                mat = self._emit_expr_str(expr.left)
                self._write(f"_matvec({mat}, {vec}, {out})")
                return out

            if expr.op in ("scale", "*"):
                scalar, vec_expr = self._split_scale(expr)
                if scalar is not None and vec_expr is not None:
                    vec = self._lower_to_field(vec_expr)
                    out = dest if dest is not None else self._get_temp()
                    if self.runtime == RUNTIME_TI_RUNTIME:
                        self._write(f"_v.vec_add({out}, {scalar}, {vec}, 0.0, {vec})")
                    else:
                        self._write(f"_vec_add({scalar}, {vec}, 0.0, {vec}, {out})")
                    return out

            if expr.op in ("+", "-"):
                left = self._lower_to_field(expr.left)
                coeff, right = self._lower_addend(expr.right)
                beta = self._negate(coeff) if expr.op == "-" else coeff
                out = dest if dest is not None else self._get_temp()
                if self.runtime == RUNTIME_TI_RUNTIME:
                    self._write(f"_v.vec_add({out}, 1.0, {left}, {beta}, {right})")
                else:
                    self._write(f"_vec_add(1.0, {left}, {beta}, {right}, {out})")
                return out

        raise UnsupportedConstructError(
            f"cannot lower vector expression to kernel ops: {expr!r}. "
            f"Supported vector forms are copy, callable application, matvec, "
            f"scalar*vector, and vector +/- vector."
        )

    def _lower_to_field(self, expr: Expr) -> str:
        """Lower a vector expression into some field (existing var or a temp)."""
        return self._lower_vector_expr(expr, dest=None)

    def _split_scale(self, expr: BinOp) -> tuple[str | None, Expr | None]:
        """Split a scalar*vector product into (scalar_code, vector_expr).

        The vector operand is whichever side is typed VECTOR; the other side is
        the scalar coefficient. Treating "not VECTOR" (rather than strictly
        SCALAR) as the coefficient keeps lowering robust when a scalar is only
        weakly typed (e.g. an undeclared Greek coefficient inferred UNKNOWN).
        """
        lt, rt = expr.left.inferred_type, expr.right.inferred_type
        if rt == VarType.VECTOR and lt != VarType.VECTOR:
            return self._emit_expr_str(expr.left), expr.right
        if lt == VarType.VECTOR and rt != VarType.VECTOR:
            return self._emit_expr_str(expr.right), expr.left
        return None, None

    def _lower_addend(self, expr: Expr) -> tuple[str, str]:
        """Express an addend as (coefficient_code, vector_field).

        A ``scalar*vector`` addend fuses its coefficient into the parent axpy;
        anything else gets coefficient ``1.0`` and is lowered into a field.
        """
        if isinstance(expr, BinOp) and expr.op in ("scale", "*"):
            scalar, vec_expr = self._split_scale(expr)
            if scalar is not None and vec_expr is not None:
                return scalar, self._lower_to_field(vec_expr)
        return "1.0", self._lower_to_field(expr)

    @staticmethod
    def _has_top_level_addsub(coeff: str) -> bool:
        """True if ``coeff`` has a *binary* ``+``/``-`` at the top paren level.

        Emitted coefficient code spaces its binary operators (``a + b``,
        ``a - b``) while a leading unary minus (``-alpha``) and float exponents
        (``1e-3``) do not — so a space-surrounded ``+``/``-`` at paren depth 0
        unambiguously marks a top-level sum/difference. ``(a + b)`` (depth 1)
        and ``a * b`` are *not* compound for negation purposes (unary minus
        already binds tighter than ``*`` / ``/`` and the parens already group).
        """
        depth = 0
        for i, ch in enumerate(coeff):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif (
                depth == 0
                and ch in "+-"
                and 0 < i < len(coeff) - 1
                and coeff[i - 1] == " "
                and coeff[i + 1] == " "
            ):
                return True
        return False

    @staticmethod
    def _negate(coeff: str) -> str:
        """Negate a coefficient string, keeping the output tidy.

        A compound coefficient (a top-level ``+``/``-``) must be parenthesised
        so the unary minus binds the *whole* expression: ``-(a + b)``, not the
        precedence-wrong ``-a + b`` (gemini MED / WI-4). This also covers a
        compound *leading*-minus (``-a + b``) correctly — wrapping yields
        ``-(-a + b)`` (== ``a - b``), whereas the bare ``coeff[1:]`` strip would
        have produced the wrong ``a + b``. Atoms and products keep the tidy
        strip-or-prepend form.
        """
        if TaichiEmitter._has_top_level_addsub(coeff):
            return f"-({coeff})"
        return coeff[1:] if coeff.startswith("-") else f"-{coeff}"

    def _emit_func_call(self, expr: FuncCall) -> str:
        func_name = self._emit_func_call_name(expr)
        args = ", ".join(self._emit_expr_str(a) for a in expr.args)
        return f"{func_name}({args})"

    def _emit_func_call_name(self, expr: FuncCall) -> str:
        """Extract the function name string from a FuncCall node."""
        if isinstance(expr.func, UnaryOp) and expr.func.op == "inverse":
            base = expr.func.operand
            return (
                _var_name(base) if isinstance(base, Var) else self._emit_expr_str(base)
            ) + "_inv"
        elif isinstance(expr.func, Var):
            name = _var_name(expr.func)
            return "ti.sqrt" if name == "sqrt" else name
        else:
            return self._emit_expr_str(expr.func)

    # ── Control flow ─────────────────────────────────────────────────────

    def _emit_for(self, stmt: ForLoop):
        # Explicit terminal `\ldots, N` is inclusive (k = 1, 2, ..., N), so the
        # Python range upper bound is N + 1 — without the +1 the loop ran one
        # fewer iteration than written (issue #307 for-loop off-by-one). An
        # open-ended `0, 1, 2, ...` uses `maxiter` as a safety cap (exactly
        # `maxiter` iterations), not an inclusive terminal.
        end = f"{_sanitize(stmt.end_expr)} + 1" if stmt.end_expr else "maxiter"
        self._write(f"for {stmt.var} in range({stmt.start}, {end}):")
        self._indent += 1
        self._emit_block(stmt.body)
        self._indent -= 1

    def _emit_while(self, stmt: WhileLoop):
        cond = self._emit_expr(stmt.condition)
        self._write(f"while {cond}:")
        self._indent += 1
        self._emit_block(stmt.body)
        self._indent -= 1

    def _emit_branch(self, stmt: Branch):
        cond = self._emit_expr(stmt.condition)
        self._write(f"if {cond}:")
        self._indent += 1
        self._emit_block(stmt.if_body)
        self._indent -= 1
        for elif_cond, elif_body in stmt.elif_branches:
            self._write(f"elif {self._emit_expr(elif_cond)}:")
            self._indent += 1
            self._emit_block(elif_body)
            self._indent -= 1
        if stmt.else_body:
            self._write("else:")
            self._indent += 1
            self._emit_block(stmt.else_body)
            self._indent -= 1

    def _emit_return(self, stmt: Return):
        if not stmt.values:
            self._write("return")
        else:
            vals = ", ".join(self._emit_expr_str(v) for v in stmt.values)
            self._write(f"return {vals}")

    def _get_temp(self) -> str:
        name = f"_tmp{self._temp_counter}"
        self._temp_counter += 1
        if self._temp_counter > self._peak_temps:
            self._peak_temps = self._temp_counter
        return name


# ── Public API ───────────────────────────────────────────────────────────────


def generate_taichi(algo: Algorithm, runtime: str = RUNTIME_INLINE) -> str:
    """Generate Taichi source code from a typed Algorithm AST.

    Parameters
    ----------
    algo:
        Typed Algorithm AST (output of :func:`algo2code.type_inference.infer_types`).
    runtime:
        Import mode.  One of:

        ``"inline"`` (default)
            Emit private ``@ti.kernel`` definitions inline in the generated
            file.  Zero external runtime dependencies.  All existing consumers
            use this mode; it is the backward-compatible default.

        ``"ti_runtime"``
            Emit ``from ti_runtime import vector_ops as _v`` and call the
            shared primitives for dot/norm/copy/vec_add.  Only ``_matvec``
            remains inlined (the matrix-free operator seam is P2-2's concern).
            algo2code itself never imports ti_runtime — it only emits the
            import line.

    Returns
    -------
    str
        Generated Taichi Python source.
    """
    return TaichiEmitter(algo, runtime=runtime).emit()
