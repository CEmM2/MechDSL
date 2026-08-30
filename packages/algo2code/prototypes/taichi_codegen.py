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
"""
from __future__ import annotations
from .ast_nodes import (
    Algorithm, Stmt, Assign, ForLoop, WhileLoop, Branch, Return, Break,
    Expr, Var, Number, BinOp, UnaryOp, FuncCall, VarType
)


# ── Variable name sanitization ───────────────────────────────────────────────

_GREEK_MAP = {
    'alpha': 'alpha', 'beta': 'beta', 'gamma': 'gamma', 'delta': 'delta',
    'epsilon': 'eps', 'varepsilon': 'eps', 'zeta': 'zeta', 'eta': 'eta',
    'theta': 'theta', 'iota': 'iota', 'kappa': 'kappa', 'lambda': 'lam',
    'mu': 'mu', 'nu': 'nu', 'xi': 'xi', 'pi': 'pi_val', 'rho': 'rho',
    'sigma': 'sigma', 'tau': 'tau', 'phi': 'phi', 'varphi': 'phi',
    'chi': 'chi', 'psi': 'psi', 'omega': 'omega',
}


def _sanitize(name: str) -> str:
    """Convert a LaTeX variable name to a valid Python identifier."""
    if name in _GREEK_MAP:
        return _GREEK_MAP[name]
    name = name.replace('{', '').replace('}', '').replace('\\', '')
    name = name.replace(' ', '_').replace('-', '_')
    if name in ('lambda', 'in', 'is', 'not', 'and', 'or', 'from', 'import'):
        name = name + '_'
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
            # Vector ← vector copy
            if (stmt.target.inferred_type == VarType.VECTOR
                    and isinstance(stmt.value, Var)
                    and stmt.value.inferred_type == VarType.VECTOR):
                self.needed_kernels.add('copy')
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
            if expr.op == 'dot':
                self.needed_kernels.add('dot')
            elif expr.op == 'matvec':
                self.needed_kernels.add('matvec')
            elif expr.op == 'scale':
                self.needed_kernels.add('vec_add')
            elif expr.op in ('+', '-') and expr.inferred_type == VarType.VECTOR:
                self.needed_kernels.add('vec_add')
        elif isinstance(expr, UnaryOp):
            self._scan_expr(expr.operand)
            if expr.op == 'norm':
                self.needed_kernels.add('norm')
        elif isinstance(expr, FuncCall):
            for arg in expr.args:
                self._scan_expr(arg)

    def emit_kernels(self) -> str:
        lines = []
        if 'dot' in self.needed_kernels:
            lines.append(_K_DOT)
        if 'norm' in self.needed_kernels:
            lines.append(_K_NORM)
        if 'matvec' in self.needed_kernels:
            lines.append(_K_MATVEC)
        if 'vec_add' in self.needed_kernels:
            lines.append(_K_VEC_ADD)
        if 'copy' in self.needed_kernels:
            lines.append(_K_COPY)
        return '\n\n'.join(lines)


# ── Kernel templates ─────────────────────────────────────────────────────────

_K_DOT = '''@ti.kernel
def _dot(a: ti.template(), b: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * b[i]
    return result'''

_K_NORM = '''@ti.kernel
def _norm(a: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * a[i]
    return ti.sqrt(result)'''

_K_MATVEC = '''@ti.kernel
def _matvec(A: ti.template(), x: ti.template(), out: ti.template()):
    for i in out:
        s = 0.0
        for j in range(x.shape[0]):
            s += A[i, j] * x[j]
        out[i] = s'''

_K_VEC_ADD = '''@ti.kernel
def _vec_add(alpha: ti.f64, x: ti.template(), beta: ti.f64,
             y: ti.template(), out: ti.template()):
    """out[i] = alpha*x[i] + beta*y[i]"""
    for i in out:
        out[i] = alpha * x[i] + beta * y[i]'''

_K_COPY = '''@ti.kernel
def _copy(src: ti.template(), dst: ti.template()):
    for i in dst:
        dst[i] = src[i]'''


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
    """Emit complete Taichi code from a typed Algorithm AST."""

    def __init__(self, algo: Algorithm):
        self.algo = algo
        self.lines: list[str] = []
        self._indent = 0
        self._temp_counter = 0
        self._needed_temp_count = 0
        self._arg_names: set[str] = set()
        self._vector_vars: set[str] = set()

    def emit(self) -> str:
        """Generate the complete Taichi source."""
        self._arg_names = _collect_arg_names(self.algo)
        self._vector_vars = _collect_vector_vars(self.algo)

        collector = KernelCollector()
        collector.scan(self.algo.body)

        self._pre_scan_temps(self.algo.body)

        parts = []
        parts.append('import taichi as ti\n')
        parts.append('ti.init(arch=ti.gpu, default_fp=ti.f64)\n')

        kernels = collector.emit_kernels()
        if kernels:
            parts.append('# ── Taichi kernels ' + '─' * 56)
            parts.append(kernels)
            parts.append('')

        parts.append('# ── Solver driver ' + '─' * 57)
        parts.append(self._emit_driver())

        return '\n\n'.join(parts) + '\n'

    def _pre_scan_temps(self, stmts: list[Stmt]):
        """Count matvec sub-expressions that need temporary vector fields."""
        for stmt in stmts:
            if isinstance(stmt, Assign):
                self._count_temps(stmt.value)
            elif isinstance(stmt, ForLoop):
                self._pre_scan_temps(stmt.body)
            elif isinstance(stmt, WhileLoop):
                self._pre_scan_temps(stmt.body)
            elif isinstance(stmt, Branch):
                self._pre_scan_temps(stmt.if_body)
                for _, body in stmt.elif_branches:
                    self._pre_scan_temps(body)
                self._pre_scan_temps(stmt.else_body)

    def _count_temps(self, expr: Expr):
        if isinstance(expr, BinOp):
            if expr.op in ('+', '-') and expr.inferred_type == VarType.VECTOR:
                if isinstance(expr.right, BinOp) and expr.right.op == 'matvec':
                    self._needed_temp_count = max(self._needed_temp_count, 1)
                if isinstance(expr.left, BinOp) and expr.left.op == 'matvec':
                    self._needed_temp_count = max(self._needed_temp_count, 1)
            self._count_temps(expr.left)
            self._count_temps(expr.right)
        elif isinstance(expr, UnaryOp):
            self._count_temps(expr.operand)

    def _emit_driver(self) -> str:
        self.lines = []
        self._indent = 0
        self._temp_counter = 0

        args = self._build_arg_list()
        self._write(f'def {self.algo.name}({args}):')
        self._indent += 1

        self._write('"""')
        self._write('Auto-generated from LaTeX algorithmic environment.')
        self._write('Backend: Taichi (GPU)')
        self._write('"""')

        # Infer vector size
        vec_arg = self._first_vector_arg()
        if vec_arg:
            self._write(f'n = {vec_arg}.shape[0]')
        else:
            self._write('n = b.shape[0]')

        # Allocate local vector fields
        local_vecs = self._vector_vars - self._arg_names
        if local_vecs or self._needed_temp_count > 0:
            self._write('')
            self._write('# Allocate working vectors')
            for name in sorted(local_vecs):
                self._write(f'{name} = ti.field(ti.f64, shape=n)')
            for i in range(self._needed_temp_count):
                self._write(f'_tmp{i} = ti.field(ti.f64, shape=n)')

        self._write('')

        # Emit body
        self._emit_block(self.algo.body)

        self._indent -= 1
        return '\n'.join(self.lines)

    def _first_vector_arg(self) -> str | None:
        for name, vtype in self.algo.args:
            if vtype == VarType.VECTOR:
                return name
        return None

    def _build_arg_list(self) -> str:
        if self.algo.args:
            return ', '.join(name for name, _ in self.algo.args)
        return 'A, b, x, M_inv=None, tol=1e-10, maxiter=1000'

    def _write(self, text: str):
        self.lines.append('    ' * self._indent + text)

    def _emit_block(self, stmts: list[Stmt]):
        for stmt in stmts:
            self._emit_stmt(stmt)

    def _emit_stmt(self, stmt: Stmt):
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
            self._write('break')

    # ── Assignment ───────────────────────────────────────────────────────

    def _emit_assign(self, stmt: Assign):
        target = _var_name(stmt.target)
        target_type = self.algo.type_annotations.get(
            stmt.target.display, stmt.target.inferred_type
        )

        # Vector ← simple vector: copy
        if (target_type == VarType.VECTOR
                and isinstance(stmt.value, Var)
                and stmt.value.inferred_type == VarType.VECTOR):
            src = _var_name(stmt.value)
            self._write(f'_copy({src}, {target})')
            return

        # Vector ← callable(args): in-place  e.g. M_inv(r, z) not z = M_inv(r)
        if (target_type == VarType.VECTOR
                and isinstance(stmt.value, FuncCall)):
            func_code = self._emit_func_call_name(stmt.value)
            args = ', '.join(self._emit_expr(a) for a in stmt.value.args)
            self._write(f'{func_code}({args}, {target})')
            return

        value_code = self._emit_expr(stmt.value, target_var=target)
        if value_code is not None:
            self._write(f'{target} = {value_code}')

    # ── Expression emission ──────────────────────────────────────────────

    def _emit_expr(self, expr: Expr, target_var: str | None = None) -> str | None:
        if isinstance(expr, Number):
            v = expr.value
            return str(int(v)) if v == int(v) else str(v)
        if isinstance(expr, Var):
            return _var_name(expr)
        if isinstance(expr, UnaryOp):
            return self._emit_unary(expr)
        if isinstance(expr, BinOp):
            return self._emit_binop(expr, target_var)
        if isinstance(expr, FuncCall):
            return self._emit_func_call(expr)
        return '???'

    def _emit_unary(self, expr: UnaryOp) -> str:
        inner = self._emit_expr(expr.operand)
        if expr.op == 'neg':
            return f'(-{inner})'
        if expr.op == 'norm':
            return f'_norm({inner})'
        if expr.op in ('transpose', 'inverse'):
            return inner  # semantic, handled at binop / funccall level
        return f'{expr.op}({inner})'

    def _emit_binop(self, expr: BinOp, target_var: str | None) -> str | None:
        if expr.op == 'dot':
            return self._emit_dot(expr)
        if expr.op == 'matvec':
            return self._emit_matvec(expr, target_var)
        if expr.op in ('+', '-') and expr.inferred_type == VarType.VECTOR:
            return self._emit_vec_arith(expr, target_var)
        if expr.op == 'scale' and expr.inferred_type == VarType.VECTOR:
            return self._emit_scale(expr, target_var)

        # Scalar
        left = self._emit_expr(expr.left)
        right = self._emit_expr(expr.right)
        op_map = {
            '+': '+', '-': '-', '*': '*', '/': '/',
            'pow': '**', '<': '<', '>': '>', '<=': '<=',
            '>=': '>=', '==': '==', '!=': '!=',
        }
        op = op_map.get(expr.op, expr.op)
        return f'({left} {op} {right})'

    def _emit_dot(self, expr: BinOp) -> str:
        left = expr.left
        if isinstance(left, UnaryOp) and left.op == 'transpose':
            left = left.operand
        return f'_dot({self._emit_expr(left)}, {self._emit_expr(expr.right)})'

    def _emit_matvec(self, expr: BinOp, target_var: str | None) -> str | None:
        mat = self._emit_expr(expr.left)
        vec = self._emit_expr(expr.right)
        if target_var:
            self._write(f'_matvec({mat}, {vec}, {target_var})')
            return None
        temp = self._get_temp()
        self._write(f'_matvec({mat}, {vec}, {temp})')
        return temp

    def _emit_scale(self, expr: BinOp, target_var: str | None) -> str | None:
        if expr.left.inferred_type == VarType.SCALAR:
            scalar, vec = self._emit_expr(expr.left), self._emit_expr(expr.right)
        else:
            scalar, vec = self._emit_expr(expr.right), self._emit_expr(expr.left)
        if target_var:
            self._write(f'_vec_add({scalar}, {vec}, 0.0, {vec}, {target_var})')
            return None
        return f'({scalar} * {vec})'

    def _emit_vec_arith(self, expr: BinOp, target_var: str | None) -> str | None:
        """
        Vector +/-, fusing scale where possible:
            x + alpha*p  →  _vec_add(1.0, x, alpha, p, out)
            x - alpha*q  →  _vec_add(1.0, x, -alpha, q, out)
            b - A*x      →  _matvec(A, x, tmp); _vec_add(1.0, b, -1.0, tmp, out)
        """
        sign = 1.0 if expr.op == '+' else -1.0

        # RHS is matvec → materialise to temp first
        if isinstance(expr.right, BinOp) and expr.right.op == 'matvec':
            temp = self._get_temp()
            mat = self._emit_expr(expr.right.left)
            vec = self._emit_expr(expr.right.right)
            self._write(f'_matvec({mat}, {vec}, {temp})')
            left_code = self._emit_expr(expr.left)
            if target_var:
                self._write(f'_vec_add(1.0, {left_code}, {sign}, {temp}, {target_var})')
                return None

        # RHS is scale: x ± alpha*p
        if isinstance(expr.right, BinOp) and expr.right.op in ('scale', '*'):
            alpha, vec = self._decompose_scale(expr.right)
            if alpha is not None and target_var:
                left_code = self._emit_expr(expr.left)
                beta = f'-{alpha}' if sign < 0 else alpha
                self._write(f'_vec_add(1.0, {left_code}, {beta}, {vec}, {target_var})')
                return None

        # General
        left_code = self._emit_expr(expr.left)
        right_code = self._emit_expr(expr.right)
        if target_var:
            self._write(f'_vec_add(1.0, {left_code}, {sign}, {right_code}, {target_var})')
            return None
        op = '+' if sign > 0 else '-'
        return f'({left_code} {op} {right_code})'

    def _decompose_scale(self, expr: BinOp) -> tuple[str | None, str | None]:
        if expr.left.inferred_type == VarType.SCALAR:
            return self._emit_expr(expr.left), self._emit_expr(expr.right)
        if expr.right.inferred_type == VarType.SCALAR:
            return self._emit_expr(expr.right), self._emit_expr(expr.left)
        return None, None

    def _emit_func_call(self, expr: FuncCall) -> str:
        func_name = self._emit_func_call_name(expr)
        args = ', '.join(self._emit_expr(a) for a in expr.args)
        return f'{func_name}({args})'

    def _emit_func_call_name(self, expr: FuncCall) -> str:
        """Extract the function name string from a FuncCall node."""
        if isinstance(expr.func, UnaryOp) and expr.func.op == 'inverse':
            base = expr.func.operand
            return (_var_name(base) if isinstance(base, Var)
                    else self._emit_expr(base)) + '_inv'
        elif isinstance(expr.func, Var):
            name = _var_name(expr.func)
            return 'ti.sqrt' if name == 'sqrt' else name
        else:
            return self._emit_expr(expr.func)

    # ── Control flow ─────────────────────────────────────────────────────

    def _emit_for(self, stmt: ForLoop):
        end = _sanitize(stmt.end_expr) if stmt.end_expr else 'maxiter'
        self._write(f'for {stmt.var} in range({stmt.start}, {end}):')
        self._indent += 1
        self._emit_block(stmt.body)
        self._indent -= 1

    def _emit_while(self, stmt: WhileLoop):
        cond = self._emit_expr(stmt.condition)
        self._write(f'while {cond}:')
        self._indent += 1
        self._emit_block(stmt.body)
        self._indent -= 1

    def _emit_branch(self, stmt: Branch):
        cond = self._emit_expr(stmt.condition)
        self._write(f'if {cond}:')
        self._indent += 1
        self._emit_block(stmt.if_body)
        self._indent -= 1
        for elif_cond, elif_body in stmt.elif_branches:
            self._write(f'elif {self._emit_expr(elif_cond)}:')
            self._indent += 1
            self._emit_block(elif_body)
            self._indent -= 1
        if stmt.else_body:
            self._write('else:')
            self._indent += 1
            self._emit_block(stmt.else_body)
            self._indent -= 1

    def _emit_return(self, stmt: Return):
        if not stmt.values:
            self._write('return')
        else:
            vals = ', '.join(self._emit_expr(v) for v in stmt.values)
            self._write(f'return {vals}')

    def _get_temp(self) -> str:
        name = f'_tmp{self._temp_counter}'
        self._temp_counter += 1
        return name


# ── Public API ───────────────────────────────────────────────────────────────

def generate_taichi(algo: Algorithm) -> str:
    """Generate Taichi source code from a typed Algorithm AST."""
    return TaichiEmitter(algo).emit()
