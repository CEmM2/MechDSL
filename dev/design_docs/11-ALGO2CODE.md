# 11-ALGO2CODE — Algorithmic LaTeX → Executable Code Transpiler

**Package:** `algo2code`
**Status:** Design Spec (MVP validated)
**Monorepo path:** `packages/algo2code/`
**Version:** 0.1.0

---

## §1  Purpose

`algo2code` transpiles LaTeX algorithm boxes (`algpseudocode` environments) into executable code targeting Taichi, NumPy, or C/PETSc backends.  It occupies a distinct niche from the tensor-expression pipeline in `mechdsl-core`: where the core DSL handles constitutive equations and element-level physics written in Einstein notation, `algo2code` handles the *solver scaffolding* — iterative linear solvers (CG, GMRES, BiCGSTAB), nonlinear drivers (Newton–Raphson, line search), time integrators, and return-mapping algorithms — whose canonical descriptions in textbooks and papers are `algpseudocode` boxes.

The motivating observation is that an algorithm like Preconditioned Conjugate Gradient has exactly *one* correct description — the one in Saad, or Golub–Van Loan, or any of a dozen references — and every hand-implementation is a transcription of that box.  Errors in transcription are the #1 source of solver bugs.  By parsing the LaTeX directly, we eliminate that class of errors and gain automatic backend portability.

### §1.1  Relationship to MechDSL

```
MechDSL monorepo
├── packages/
│   ├── mechdsl-core/          ← tensor expressions, constitutive laws, element kernels
│   │   └── src/mechdsl/       ← mechdsl.frontend, mechdsl.symbolic, mechdsl.ir, etc.
│   └── algo2code/             ← THIS PACKAGE: algorithm boxes → solver code
├── dev/
│   └── design_docs/
│       ├── 06-CODEGEN.md
│       ├── 07-CONVENTIONS.md
│       ├── 09-EINSUM-OPTIMISER.md
│       └── 11-ALGO2CODE.md    ← THIS DOCUMENT
└── tests/
```

`algo2code` is consumed by the `mechdsl-core` driver at two integration points. The first is **landed** as of recovery-plan Phase 6; the second is **deferred** per recovery plan §P6-4.

1. **Linear-solver seam (recovery plan §P6-1..P6-3 — landed 2026-04-29)** — the Newton–Raphson driver in `mechdsl.solver.newton.newton_solve` consumes any `LinearSolverInterface` adapter. The recovered seam adds **`mechdsl.solver.import_adapter.Algo2CodePCGSolver`** as a third concrete adapter alongside `CGSolver`, `PCGSolver`, `ScipyCGSolver`, opt-in via the `linear_solver=` kwarg or `mechdsl.solver.integration.select_linear_solver("generated")`. The default remains `ScipyCGSolver` until further validation. The canonical PCG algpseudocode lives at **`algo2code.library.pcg.PCG_ALGORITHM_LATEX`** (string constant + `get_pcg_algorithm_latex()` accessor) and is the single source of truth for the PCG algorithm; the adapter body is a verbatim line-by-line Python translation of that LaTeX (parser-deferral note in §2.5). `algo2code` remains runtime-free — zero `mechdsl` imports under `packages/algo2code/src/`. End-to-end plumbing is exercised by `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_3.py`.

2. **Constitutive seam — radial-return (Plan A Phase A9, deferred per recovery plan §P6-4)** — the J2 radial-return algorithm is itself an `algpseudocode` box (Algorithm 7.1 in de Souza Neto). Replacing the imported J2 path with an `algo2code`-generated equivalent is **later-stage, post-MVP** work, deferred until the recovery plan's frontend (R2) and IR alignment (R3) phases settle. Substituting it before those layers stabilise risks re-introducing the contract drift the recovery plan is correcting.

### §1.2  Design principles

**P1  Valid LaTeX in, valid code out.**  The input must compile under `pdflatex` with `\usepackage{algpseudocode}`.  The output must pass `compile()` (Python) or `gcc -fsyntax-only` (C) with zero modifications.

**P2  Type-directed code generation.**  The same LaTeX operator (`\cdot`, implicit multiplication, `^\top`) generates different code depending on operand types.  `r^\top z` with two vectors becomes `_dot(r, z)`; `A \cdot p` with matrix × vector becomes `_matvec(A, p, q)`.  Types are declared through `%`-comment directives embedded in valid LaTeX, following the NRPyLaTeX convention that metadata lives in comments so the document remains compilable.

**P3  Kernel/scope split is automatic.**  The type system determines which operations require GPU kernels and which stay in Python driver scope.  The user never manually marks kernel boundaries.

**P4  No symbolic algebra dependency.**  The MVP expression parser handles the linear-algebra subset of LaTeX math directly (fractions, transpose, norms, subscripts, function calls).  It does *not* route through SymPy.  This keeps the package dependency-free (only `re` from the standard library) and avoids `parse_latex` edge cases around `\mathbf`, implicit multiplication, and Greek letters.  A `latex2sympy2_extended` backend can be plugged in later for algorithms requiring symbolic differentiation (§8.2).

**P5  One LaTeX dialect.**  We standardise on `algpseudocode` (from the `algorithmicx` package) exclusively.  No `algorithm2e`, no legacy `algorithmic`.  This gives us an unambiguous LL(1) grammar with explicit `\End*` terminators.

---

## §2  Input format

### §2.1  Directive comments

Directives appear as LaTeX comments (`%`) outside or inside the `algorithmic` environment.  Because they are comments, they are invisible to `pdflatex` — the `.tex` file renders identically with or without them.

```latex
% algorithm <name>
% backend <taichi|numpy|c_petsc>
% args <name>:<type>, <name>:<type>, ...
% type <varname> <scalar|vector|matrix|callable>
```

**Supported types:**

| Type | Meaning | Taichi representation |
|---|---|---|
| `scalar` | Real number | `ti.f64` (Python scope) |
| `vector` | 1D array of reals | `ti.field(ti.f64, shape=n)` |
| `matrix` | 2D array of reals | `ti.field(ti.f64, shape=(n,n))` |
| `callable` | User-supplied function | Python callable `(in_field, out_field) → None` |

### §2.2  Algorithmic body

The full `algpseudocode` command set we support:

| LaTeX command | AST node | Semantics |
|---|---|---|
| `\State $lhs = rhs$` | `Assign` | Assignment; `$...$` parsed as math |
| `\For{$range$}` ... `\EndFor` | `ForLoop` | Deterministic loop |
| `\While{$cond$}` ... `\EndWhile` | `WhileLoop` | Conditional loop |
| `\If{$cond$}` ... `\EndIf` | `Branch` | Conditional branch |
| `\ElsIf{$cond$}` | `Branch.elif` | Chained condition |
| `\Else` | `Branch.else` | Default branch |
| `\Return $expr$` | `Return` | Return one or more values |
| `\State \textbf{break}` | `Break` | Loop break |

### §2.3  Inline type annotations

Each `\State` line may carry a trailing `%` comment with a type hint.  This is the *primary* mechanism for annotating intermediate variables that are not function arguments:

```latex
\State $r = b - A \cdot x$       % vector
\State $\alpha = \frac{\rho}{p^\top q}$   % scalar
```

The parser extracts the LHS variable name and associates it with the declared type.  Inline annotations override `% type` directives if both are present.

### §2.4  Expression sub-language

The math fragments inside `$...$` are parsed by a custom recursive-descent parser.  The supported grammar (in extended BNF):

```
expr         := term (('+' | '-') term)*
term         := signed_factor (('·' | implicit_mul) signed_factor)*
signed_factor := '-'? factor
factor       := base ('^' superscript)? ('(' arglist ')')?
base         := '(' expr ')'
              | '\frac{' expr '}{' expr '}'
              | '\sqrt{' expr '}'
              | norm_expr
              | atom
norm_expr    := '\|' expr '\|'
              | '\lVert' expr '\rVert'
superscript  := '{' expr '}'
              | '\top'
              | '{-1}'
              | atom
atom         := NUMBER
              | LETTER ('_' subscript)?
              | GREEK  ('_' subscript)?
              | STYLED ('_' subscript)?
subscript    := '{' text '}'  |  single_token
arglist      := expr (',' expr)*
implicit_mul := (when next token can start a factor and no explicit operator present)
```

**Styled commands** recognised: `\mathbf`, `\boldsymbol`, `\bm`, `\mathit`, `\mathrm`, `\text`, `\textbf`, `\operatorname`.  All are treated as variable-name wrappers — the inner text becomes the variable name.

**What is NOT supported** (and why):

| LaTeX construct | Reason for exclusion | Alternative |
|---|---|---|
| `\sum_{i}`, `\prod_{i}` | Summation/product loops belong in tensor pipeline | Use `mechdsl-core` einsum |
| `\int`, `\lim`, `\frac{d}{dx}` | Calculus operations need symbolic engine | Use `latex2sympy2_extended` backend (§8.2) |
| `\begin{pmatrix}` | Matrix literals rarely appear in solver algorithms | Pass as argument |
| `\hat{}`, `\tilde{}`, `\bar{}` | Ambiguous naming diacritics | Use subscripts instead |
| Nested `\frac{\frac{}{}}{}` | Rarely needed; complicates precedence | Rewrite as flat fractions |


### §2.5  Complete input example: PCG


```latex
% algorithm pcg
% backend taichi
% args A:matrix, b:vector, x:vector, apply_M_inv:callable, tol:scalar, maxiter:scalar

% type r vector
% type z vector
% type p vector
% type q vector
% type rho scalar
% type rho_new scalar
% type alpha scalar
% type beta scalar
% type pq scalar
% type r0_norm scalar
% type r_norm scalar

\begin{algorithmic}
\State $r = b - A \cdot x$                                         % vector
\State $r_0 = \lVert r \rVert_2$                                    % scalar
\If{$r_0 = 0$}
    \Return $x, 0, 0$
\EndIf
\State $z = \text{apply\_M\_inv}(r)$                                % vector
\State $p = z$                                                      % vector
\State $\rho = r^\top z$                                            % scalar
\For{$k = 1, 2, \ldots, \text{maxiter}$}
    \State $q = A \cdot p$                                          % vector
    \State $pq = p^\top q$                                          % scalar
    \If{$|pq| < 10^{-300}$}
        \State \textbf{break}
    \EndIf
    \State $\alpha = \frac{\rho}{pq}$                               % scalar
    \State $x = x + \alpha \, p$                                    % vector
    \State $r = r - \alpha \, q$                                    % vector
    \State $r_n = \lVert r \rVert_2$                                % scalar
    \If{$r_n < \text{tol} \cdot r_0$}
        \Return $x, k, r_n$
    \EndIf
    \State $z = \text{apply\_M\_inv}(r)$                            % vector
    \State $\rho_{\text{new}} = r^\top z$                           % scalar
    \State $\beta = \frac{\rho_{\text{new}}}{\rho}$                 % scalar
    \State $p = z + \beta \, p$                                     % vector
    \State $\rho = \rho_{\text{new}}$                               % scalar
\EndFor
\Return $x, \text{maxiter}, \lVert r \rVert_2$
\end{algorithmic}
```
---

## §3  Architecture

### §3.1  Pipeline

```
                    ┌─────────────────────────────────────────────┐
                    │            LaTeX Source (.tex)               │
                    │   % directives + \begin{algorithmic}...     │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │          1. algo_parser                      │
                    │   • Reads % directives → AlgorithmMeta      │
                    │   • Parses \For, \If, \State, \Return       │
                    │   • Delegates $...$ to expr_parser           │
                    │   output: Algorithm AST (untyped)            │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │          2. expr_parser                      │
                    │   • Tokeniser: LaTeX → Token stream          │
                    │   • Recursive-descent parser                 │
                    │   • Handles: frac, ^, \top, \|.\|, M^{-1}() │
                    │   output: Expression sub-trees (Expr nodes)  │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │          3. type_inference                   │
                    │   • Seeds from % type + % args directives   │
                    │   • Forward-propagates through Assign chain  │
                    │   • Resolves BinOp semantics:               │
                    │       * → dot / matvec / scale / multiply   │
                    │   output: Algorithm AST (typed)              │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │          4. backend codegen                  │
                    │   • taichi_codegen  (MVP)                   │
                    │   • numpy_codegen   (planned)               │
                    │   • c_petsc_codegen (planned)               │
                    │   output: source code string                │
                    └─────────────────────────────────────────────┘
```

### §3.2  Module map

```
algo2code/
├── __init__.py              # Public API: transpile()
├── ast_nodes.py             # Dataclass AST definitions
├── expr_parser.py           # Tokeniser + recursive-descent expression parser
├── algo_parser.py           # algpseudocode control-flow parser
├── type_inference.py        # Forward type propagation + BinOp resolution
├── backends/
│   ├── __init__.py
│   ├── taichi_codegen.py    # Taichi kernel + driver emitter
│   ├── numpy_codegen.py     # (planned) NumPy emitter
│   └── c_petsc_codegen.py   # (planned) C/PETSc emitter
├── library/                 # Pre-written .tex algorithm files
│   ├── pcg.tex
│   ├── gmres.tex            # (planned)
│   ├── bicgstab.tex         # (planned)
│   ├── newton_raphson.tex   # (planned)
│   ├── line_search.tex      # (planned)
│   └── radial_return.tex    # (planned)
└── tests/
    ├── test_expr_parser.py
    ├── test_algo_parser.py
    ├── test_type_inference.py
    ├── test_taichi_codegen.py
    └── test_end_to_end.py
```

### §3.3  Dependencies

**Runtime:** None.  Standard library only (`re`, `dataclasses`, `enum`, `typing`).

**Optional:**
- `taichi` — only needed to *run* generated Taichi code, not to *generate* it
- `latex2sympy2_extended` — pluggable expression backend (§8.2)

**Dev:**
- `pytest`

---

## §4  AST specification

### §4.1  Type system

```python
class VarType(Enum):
    SCALAR   = auto()    # float
    VECTOR   = auto()    # 1D field
    MATRIX   = auto()    # 2D field
    CALLABLE = auto()    # user function  (in_field, out_field) → None
    UNKNOWN  = auto()    # pre-inference placeholder
```

### §4.2  Expression nodes

All expression nodes inherit from `Expr` and carry an `inferred_type: VarType` field, populated by the type inference pass.

| Node | Fields | Example |
|---|---|---|
| `Var` | `name: str`, `subscript: str?` | `\rho_{\text{new}}` → `Var("rho", "new")` |
| `Number` | `value: float` | `42` → `Number(42.0)` |
| `BinOp` | `op: str`, `left: Expr`, `right: Expr` | `a + b` → `BinOp("+", a, b)` |
| `UnaryOp` | `op: str`, `operand: Expr` | `\|r\|` → `UnaryOp("norm", r)` |
| `FuncCall` | `func: Expr`, `args: list[Expr]` | `M^{-1}(r)` → `FuncCall(UnaryOp("inverse", M), [r])` |

**`BinOp.op` values** — before and after type inference:

| Pre-inference op | Operand types | Post-inference op | Result type |
|---|---|---|---|
| `*` | `transpose(vector) × vector` | `dot` | `scalar` |
| `*` | `matrix × vector` | `matvec` | `vector` |
| `*` | `scalar × vector` | `scale` | `vector` |
| `*` | `scalar × scalar` | `*` (unchanged) | `scalar` |
| `+`, `-` | `vector ± vector` | `+`, `-` (unchanged) | `vector` |
| `+`, `-` | `scalar ± scalar` | `+`, `-` (unchanged) | `scalar` |
| `/` | any | `/` (unchanged) | `scalar` |
| `pow` | any | `pow` (unchanged) | follows base |

### §4.3  Statement nodes

| Node | Fields | LaTeX source |
|---|---|---|
| `Assign` | `target: Var`, `value: Expr`, `comment: str` | `\State $x = expr$  % comment` |
| `ForLoop` | `var: str`, `start: int`, `end_expr: str`, `body: list[Stmt]` | `\For{$k = 0, ..., N$}` |
| `WhileLoop` | `condition: Expr`, `body: list[Stmt]` | `\While{$cond$}` |
| `Branch` | `condition: Expr`, `if_body`, `elif_branches`, `else_body` | `\If{$cond$}` |
| `Return` | `values: list[Expr]` | `\Return $x, k$` |
| `Break` | (none) | `\State \textbf{break}` |

### §4.4  Top-level node

```python
@dataclass
class Algorithm:
    name: str                                    # from % algorithm directive
    backend: str                                 # from % backend directive
    args: list[tuple[str, VarType]]              # from % args directive
    body: list[Stmt]                             # parsed algorithmic body
    type_annotations: dict[str, VarType]         # merged from all sources
```

---

## §5  Parsing

### §5.1  Expression tokeniser

The tokeniser converts LaTeX math fragments into a flat token stream.  It is implemented as a single compiled regex with named groups, ordered longest-match-first.  Whitespace and thin-space commands (`\,`, `\;`, `\quad`) are consumed and discarded.

**Token types (22):**

`STYLED` · `OPNAME` · `LNORM` · `RNORM` · `NORMPIPE` · `FRAC` · `SQRT` · `CDOT` · `THINSPACE` · `TOP` · `DOTS` · `GREEK` · `LBRACE` · `RBRACE` · `LPAREN` · `RPAREN` · `CARET` · `UNDERSCORE` · `PLUS` · `MINUS` · `SLASH` · `EQUALS` · `LT` · `GT` · `COMMA` · `NUMBER` · `LETTER` · `WS`

### §5.2  Expression parser

Recursive-descent, LL(1).  The grammar has six levels of precedence:

```
    expr  →  term  →  signed_factor  →  factor  →  base  →  atom
     ↑ +/-    ↑ ·/implicit   ↑ unary-     ↑ ^/()    ↑ ()/frac/√/‖‖  ↑ terminal
```

**Implicit multiplication** is triggered when two adjacent factors have no explicit operator between them and the next token can start a new factor.  The set of "can-start" tokens is `{LETTER, GREEK, STYLED, NUMBER, LPAREN, FRAC, SQRT, LNORM, OPNAME}`.  Critically, `NORMPIPE` is *excluded* from this set — it is ambiguous (could be a closing pipe of a norm we're currently inside), so norms as implicit-multiply operands must use `\lVert`/`\rVert` or explicit `\cdot`.

**Function call detection** happens in `parse_factor`, *after* superscript parsing.  This is essential for the `M^{-1}(r)` pattern: the parser first sees `M`, then `^{-1}` (producing `UnaryOp("inverse", M)`), then `(r)` (producing `FuncCall(inverse(M), [r])`).  If function-call detection were in `parse_base` instead, the `(r)` would be consumed before the `^{-1}` is seen.

### §5.3  Algorithm parser

The algorithm parser works line-by-line over the body of the `\begin{algorithmic}` ... `\end{algorithmic}` environment.  It maintains a line cursor and uses recursive `_parse_block(terminators)` calls to handle nesting.

**Directive parsing** happens in a pre-pass over lines *outside* the algorithmic environment.  Inline type annotations (trailing `%` comments on `\State` lines) are collected in a second pre-pass over the body lines.

**For-loop range parsing** recognises three patterns:

| Pattern | Example | Parsed as |
|---|---|---|
| `k = 0, 1, \ldots, N` | Standard textbook form | `var=k, start=0, end=N` |
| `k = 0, 1, 2, \ldots` | Indefinite (uses maxiter) | `var=k, start=0, end=""` |
| `k = 1 \to N` | Arrow notation | `var=k, start=1, end=N` |

### §5.4  Condition parsing

Conditions inside `\If{...}` and `\While{...}` are parsed by splitting on comparison operators (`<`, `>`, `\leq`, `\geq`) at brace depth 0, then parsing each side as an expression.

---

## §6  Type inference

### §6.1  Algorithm

Type inference is a single forward pass over the AST.  It seeds the type table from `% type` directives and `% args` declarations, then propagates through assignments in statement order.

```
for each statement in program order:
    if Assign(target, value):
        infer_expr(value)                    # recursive, bottom-up
        types[target.name] = value.inferred_type
    if ForLoop:
        types[loop_var] = SCALAR
        infer_block(body)
    if Branch / WhileLoop:
        infer_expr(condition)
        infer_block(body)
```

### §6.2  Expression inference rules

| Expression | Rule | Result type |
|---|---|---|
| `Number(v)` | Always | `SCALAR` |
| `Var(name)` | Lookup `types[name]`; default uppercase single-letter → `MATRIX` | Looked-up type |
| `UnaryOp("norm", x)` | Always | `SCALAR` |
| `UnaryOp("transpose", x)` | Preserves inner type | Same as operand |
| `UnaryOp("neg", x)` | Preserves inner type | Same as operand |
| `BinOp("+"/"-", l, r)` | Dominant type wins: `VECTOR > MATRIX > SCALAR` | Dominant |
| `BinOp("/", l, r)` | Always | `SCALAR` |
| `BinOp("*", l, r)` | See §4.2 resolution table | Depends |
| `FuncCall(f, args)` | Copies first argument's type | `args[0].type` |

### §6.3  Multiply resolution

The key logic.  Given `BinOp("*", left, right)` where `left` has type `lt` and `right` has type `rt`:

```
if left is UnaryOp("transpose") and rt == VECTOR:
    op ← "dot",    result ← SCALAR
elif lt == MATRIX and rt == VECTOR:
    op ← "matvec", result ← VECTOR
elif lt == SCALAR and rt == VECTOR (or symmetric):
    op ← "scale",  result ← VECTOR
elif lt == MATRIX and rt == MATRIX:
    op ← "matmul", result ← MATRIX
else:
    op ← "*",      result ← SCALAR
```

### §6.4  Callable inference

`M^{-1}(r)` is parsed as `FuncCall(UnaryOp("inverse", Var("M")), [Var("r")])`.  During type inference, when an `inverse` node is encountered inside a `FuncCall`, the base variable is retroactively typed as `CALLABLE`.  The result type is inherited from the first argument (`VECTOR` if `r` is a vector).

---

## §7  Code generation: Taichi backend

### §7.1  Architecture: kernel/scope split

The Taichi backend splits generated code into two tiers:

**Tier 1 — `@ti.kernel` functions** for operations that touch every element of a vector or matrix.  These run on GPU.  They are stateless, reusable, and defined at module scope.

**Tier 2 — Python-scope driver** function containing the loop logic, scalar arithmetic, convergence checks, and kernel invocations.  Runs on CPU.

The split is determined entirely by the type system.  The rule is:

> Any `Assign` whose RHS involves a vector- or matrix-typed operation invokes one or more Tier 1 kernels.  Any `Assign` whose RHS is purely scalar-typed emits a Python expression.

### §7.2  Standard kernel library

The code generator emits only the kernels actually used by the algorithm (determined by a pre-scan).

| Kernel | Signature | Operation | When emitted |
|---|---|---|---|
| `_dot` | `(a: template, b: template) → f64` | $\sum_i a_i b_i$ | Any `dot` BinOp |
| `_norm` | `(a: template) → f64` | $\sqrt{\sum_i a_i^2}$ | Any `norm` UnaryOp |
| `_matvec` | `(A: template, x: template, out: template)` | $\text{out}_i = \sum_j A_{ij} x_j$ | Any `matvec` BinOp |
| `_vec_add` | `(α: f64, x: template, β: f64, y: template, out: template)` | $\text{out}_i = \alpha x_i + \beta y_i$ | Any vector `+`/`-` or `scale` |
| `_copy` | `(src: template, dst: template)` | $\text{dst}_i = \text{src}_i$ | Vector-to-vector copy |

### §7.3  Operation fusion

The emitter attempts to fuse scalar-vector patterns into single `_vec_add` calls:

| LaTeX | Naive emission | Fused emission |
|---|---|---|
| `x = x + \alpha p` | `_scale(α,p,tmp); _vec_add(1,x,1,tmp,x)` | `_vec_add(1.0, x, α, p, x)` |
| `r = r - \alpha q` | `_scale(α,q,tmp); _vec_add(1,r,-1,tmp,r)` | `_vec_add(1.0, r, -α, q, r)` |
| `r = b - Ax` | `_matvec(A,x,tmp); _vec_add(1,b,-1,tmp,r)` | `_matvec(A,x,_tmp0); _vec_add(1.0,b,-1.0,_tmp0,r)` |

The third case requires a temporary field (`_tmp0`), which is automatically allocated in the driver preamble.

### §7.4  Driver preamble

The generated driver function begins with:

1. **Size inference:** `n = <first_vector_arg>.shape[0]`
2. **Working vector allocation:** `ti.field(ti.f64, shape=n)` for each vector-typed variable that is not a function argument
3. **Temporary allocation:** `_tmpN` fields for sub-expressions (matvec results used inside larger expressions)

### §7.5  Callable convention

Functions typed as `CALLABLE` (e.g., preconditioners `M^{-1}`) are emitted as two-argument calls: `M_inv(input_field, output_field)`.  The code generator appends `_inv` to the base name when it encounters an `inverse` node wrapping a `FuncCall`.

### §7.6  Generated code example

For the PCG input in §2.5:

```python
import taichi as ti

ti.init(arch=ti.gpu, default_fp=ti.f64)

# ── Taichi kernels ────────────────────────────────────────────────────────

@ti.kernel
def _dot(a: ti.template(), b: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * b[i]
    return result

@ti.kernel
def _norm(a: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * a[i]
    return ti.sqrt(result)

@ti.kernel
def _matvec(A: ti.template(), x: ti.template(), out: ti.template()):
    for i in out:
        s = 0.0
        for j in range(x.shape[0]):
            s += A[i, j] * x[j]
        out[i] = s

@ti.kernel
def _vec_add(alpha: ti.f64, x: ti.template(), beta: ti.f64,
             y: ti.template(), out: ti.template()):
    for i in out:
        out[i] = alpha * x[i] + beta * y[i]

@ti.kernel
def _copy(src: ti.template(), dst: ti.template()):
    for i in dst:
        dst[i] = src[i]

# ── Solver driver ─────────────────────────────────────────────────────────

def pcg(A, b, x, M_inv, tol, maxiter):
    n = b.shape[0]

    p = ti.field(ti.f64, shape=n)
    q = ti.field(ti.f64, shape=n)
    r = ti.field(ti.f64, shape=n)
    z = ti.field(ti.f64, shape=n)
    _tmp0 = ti.field(ti.f64, shape=n)

    _matvec(A, x, _tmp0)
    _vec_add(1.0, b, -1.0, _tmp0, r)
    M_inv(r, z)
    _copy(z, p)
    rho = _dot(r, z)
    for k in range(0, maxiter):
        _matvec(A, p, q)
        alpha = (rho / _dot(p, q))
        _vec_add(1.0, x, alpha, p, x)
        _vec_add(1.0, r, -alpha, q, r)
        if (_norm(r) < tol):
            return x, k
        M_inv(r, z)
        rho_new = _dot(r, z)
        beta = (rho_new / rho)
        _vec_add(1.0, z, beta, p, p)
        rho = rho_new
    return x, maxiter
```

---

## §8  Extension points

### §8.1  Additional backends

Each backend implements a single function:

```python
def generate_<backend>(algo: Algorithm) -> str
```

**NumPy backend** (planned).  Simpler than Taichi — no kernel/scope split.  `dot` → `a @ b`, `matvec` → `A @ p`, `norm` → `np.linalg.norm(r)`, `scale` → `α * p`, vector add → `x + α*p`.  Single flat function.

**C/PETSc backend** (planned).  Emits a C function using PETSc `Vec` and `Mat` types.  `dot` → `VecDot()`, `matvec` → `MatMult()`, etc.  Requires declaring all variables at function scope (C89) or with appropriate types (C99).  Loop syntax changes (`for (int k = 0; k < maxiter; k++)`).  This backend is consumed by the `mechdsl-driver` MFEM/MOOSE export path (Plan B Phase B8).

### §8.2  `latex2sympy2_extended` expression backend

For algorithms that contain symbolic expressions beyond linear algebra — e.g., the yield function evaluation in radial return, or the consistent tangent computation — the expression parser can be swapped.  The interface:

```python
class ExprBackend(Protocol):
    def parse(self, latex: str) -> Expr:
        """Parse a LaTeX math fragment into an Expr AST node."""
        ...
```

The `latex2sympy2_extended` adapter would:

1. Call `latex2sympy(fragment)` to get a SymPy expression
2. Walk the SymPy tree and convert to our `Expr` nodes
3. Annotate with type information from the `% type` directives

This is deferred to Plan B because the MVP algorithms (CG, Newton, radial return) all have simple enough expressions that the custom parser handles them.

### §8.3  Matrix-free operator interface

For FEM solvers, the "matrix" `A` is never assembled — it is a matrix-free operator.  The `matvec` kernel is replaced by the element-level operator application generated by `mechdsl-core`.  The integration point:

```python
# In the driver, A is a callable, not a field:
# % type A callable
#
# Generated code calls A(p, q) instead of _matvec(A, p, q)
```

This is activated by annotating `A` as `callable` instead of `matrix`.  The code generator detects this and emits `A(p, q)` instead of `_matvec(A, p, q)`.  The matrix-free operator is supplied by the `mechdsl-driver` and wraps the element kernel loop.

### §8.4  Sparse matrix support

For assembled systems, the `_matvec` kernel uses dense indexing (`A[i, j]`).  For sparse systems (CSR/CSC), a specialised kernel template is needed:

```python
@ti.kernel
def _spmv_csr(row_ptr: ti.template(), col_idx: ti.template(),
              values: ti.template(), x: ti.template(), out: ti.template()):
    for i in out:
        s = 0.0
        for jj in range(row_ptr[i], row_ptr[i + 1]):
            s += values[jj] * x[col_idx[jj]]
        out[i] = s
```

Activation: `% type A sparse` or `% sparsity csr`.  Deferred to post-MVP.

---

## §9  Testing strategy

### §9.1  Unit tests — expression parser (16 tests)

Each test parses a LaTeX fragment and asserts the AST structure:

| Test | Input | Assertion |
|---|---|---|
| `test_number` | `42` | `Number(42.0)` |
| `test_variable` | `x` | `Var("x")` |
| `test_greek_var` | `\alpha` | `Var("alpha")` |
| `test_addition` | `a + b` | `BinOp("+", ...)` |
| `test_subtraction` | `a - b` | `BinOp("-", ...)` |
| `test_fraction` | `\frac{a}{b}` | `BinOp("/", ...)` |
| `test_cdot` | `A \cdot p` | `BinOp("*", ...)` |
| `test_transpose` | `r^\top z` | `BinOp("*", UnaryOp("transpose", r), z)` |
| `test_transpose_braces` | `r^{\top} z` | Same as above |
| `test_norm` | `\|r\|` | `UnaryOp("norm", r)` |
| `test_styled_vars` | `\mathbf{A} \cdot \mathbf{p}` | `BinOp("*", Var("A"), Var("p"))` |
| `test_subscript` | `\rho_{\text{new}}` | `Var("rho", subscript="new")` |
| `test_inverse_func` | `M^{-1}(r)` | `FuncCall(UnaryOp("inverse", M), [r])` |
| `test_nested_frac` | `\frac{\rho_{\text{new}}}{\rho}` | `BinOp("/", ...)` |
| `test_frac_with_dot` | `\frac{\rho}{p^\top q}` | Denominator is `BinOp("*", ...)` |
| `test_assignment` | `r = b - A` | `(Var("r"), BinOp("-", ...))` |

### §9.2  Unit tests — algorithm parser (8 tests)

Parse the full PCG input and assert structural properties:

| Test | Assertion |
|---|---|
| `test_parses_name` | `algo.name == "pcg"` |
| `test_parses_backend` | `algo.backend == "taichi"` |
| `test_parses_args` | 6 arguments, correct names |
| `test_parses_type_directives` | `r → VECTOR`, `rho → SCALAR` |
| `test_body_structure` | 4 Assigns + 1 ForLoop + 1 Return |
| `test_for_loop` | `var="k"`, `start=0`, `end="maxiter"` |
| `test_if_branch` | Body contains 1 Branch with 1 Return |
| `test_return_values` | Final Return has 2 values |

### §9.3  Unit tests — type inference (3 tests)

| Test | Assertion |
|---|---|
| `test_dot_product` | `rho = r^T z` → `rho.inferred_type == SCALAR` |
| `test_matvec` | `r = b - A·x` → `r.inferred_type == VECTOR` |
| `test_norm_is_scalar` | `\|r\| < tol` → LHS is SCALAR |

### §9.4  End-to-end tests (8 tests)

| Test | Assertion |
|---|---|
| `test_transpile_produces_code` | Output is non-empty string |
| `test_code_has_imports` | Contains `import taichi` |
| `test_code_has_kernels` | Contains `@ti.kernel` |
| `test_code_has_driver` | Contains `def pcg(` |
| `test_code_has_matvec` | Contains `_matvec` |
| `test_code_has_convergence_check` | Contains `_norm(` and `tol` |
| `test_code_has_loop` | Contains `for k in range` |
| `test_code_is_syntactically_valid_python` | `compile(code, ..., 'exec')` succeeds |

### §9.5  Integration tests (planned)

| Test | Description |
|---|---|
| `test_pcg_solves_spd_system` | Generate PCG, run on a 100×100 SPD system, verify residual < tol |
| `test_pcg_matches_numpy` | Compare Taichi PCG output against `numpy.linalg.solve` |
| `test_newton_converges` | Transpile Newton–Raphson, solve `x² - 2 = 0`, verify convergence |
| `test_radial_return_J2` | Transpile radial return, verify against analytical J2 return |
| `test_matrix_free_pcg` | PCG with `A` as callable, verify same result as dense |

---

## §10  Algorithm library

The `library/` directory contains pre-validated `.tex` files for standard algorithms.  Each file is a complete, compilable LaTeX fragment with correct `%` directives.

### §10.1  MVP algorithms

| File | Algorithm | Reference | Status |
|---|---|---|---|
| `pcg.tex` | Preconditioned Conjugate Gradient | Saad §6.7, Golub–Van Loan Alg 11.5.1 | ✓ Validated |
| `newton_raphson.tex` | Newton–Raphson with line search | Wriggers (2008) §5.3 | Planned |
| `radial_return.tex` | J2 radial return mapping | de Souza Neto (2008) Box 7.5 | Planned |

### §10.2  Post-MVP algorithms

| File | Algorithm | Reference |
|---|---|---|
| `gmres.tex` | Restarted GMRES(m) | Saad §6.5 |
| `bicgstab.tex` | BiCGSTAB | Van der Vorst (1992) |
| `line_search.tex` | Backtracking Armijo line search | Nocedal & Wright §3.1 |
| `central_difference.tex` | Explicit central difference time integration | Belytschko (2000) Box 6.1 |
| `newmark.tex` | Newmark-β implicit time integration | Hughes (2000) Box 9.1 |
| `closest_point_return.tex` | General closest-point return mapping | Simo & Hughes (1998) Box 3.2 |
| `arc_length.tex` | Riks/Crisfield arc-length continuation | Crisfield (1991) §9.3 |

---

## §11  API

### §11.1  Primary API

```python
from algo2code import transpile

code: str = transpile(
    source: str,             # LaTeX source with \begin{algorithmic}
    backend: str = "taichi"  # "taichi" | "numpy" | "c_petsc"
) -> str
```

### §11.2  Granular API

```python
from algo2code import parse_algorithm, infer_types, generate_taichi
from algo2code import Algorithm, VarType

# Step 1: Parse
algo: Algorithm = parse_algorithm(latex_source)

# Step 2: Inspect / modify AST
algo.type_annotations["A"] = VarType.CALLABLE   # override to matrix-free

# Step 3: Type inference
infer_types(algo)

# Step 4: Generate
code: str = generate_taichi(algo)
```

### §11.3  CLI (planned)

```bash
# Transpile a .tex file
algo2code pcg.tex --backend taichi --output pcg_solver.py

# Validate a .tex file (parse + type-check, no code generation)
algo2code --check pcg.tex

# Dump the typed AST for debugging
algo2code --dump-ast pcg.tex
```

---

## §12  Conventions and compatibility with MechDSL

### §12.1  Naming

Generated function names follow the `% algorithm` directive.  Generated kernel names are prefixed with `_` (private).  Variable names follow the Greek-to-Python map:

| Greek | Python | Greek | Python |
|---|---|---|---|
| `\alpha` | `alpha` | `\rho` | `rho` |
| `\beta` | `beta` | `\sigma` | `sigma` |
| `\gamma` | `gamma` | `\varepsilon` | `eps` |
| `\lambda` | `lam` (avoids keyword) | `\pi` | `pi_val` (avoids constant) |

### §12.2  Precision

All generated Taichi code uses `ti.f64` and `default_fp=ti.f64`, consistent with the `mechdsl-core` convention (spec 07-CONVENTIONS §10, spec 06-CODEGEN §2).

### §12.3  JIT budget

The standard kernels (`_dot`, `_norm`, `_matvec`, `_vec_add`, `_copy`) are all small (< 10 lines each) and well within the Tier 1 JIT budget threshold of 512 lines (spec 07-CONVENTIONS §9).  They are emitted at module scope and JIT-compiled once on first call.

### §12.4  Integration with mechdsl-driver

The `mechdsl-driver` build step invokes `algo2code.transpile()` at module-import time (not at simulation time):

```python
# In mechdsl_driver/solvers/__init__.py
from algo2code import transpile
import importlib, types, sys

_pcg_src = open(_SOLVER_DIR / "pcg.tex").read()
_pcg_code = transpile(_pcg_src, backend="taichi")
_pcg_module = types.ModuleType("_pcg_generated")
exec(compile(_pcg_code, "pcg.tex→taichi", "exec"), _pcg_module.__dict__)
sys.modules["mechdsl_driver.solvers._pcg"] = _pcg_module

# Usage:
from mechdsl_driver.solvers._pcg import pcg
```

---

## §13  Limitations and known issues

| Issue | Severity | Mitigation |
|---|---|---|
| No in-place aliasing safety | Medium | `_vec_add(1.0, x, α, p, x)` overwrites `x` while reading it.  Safe for the fused AXPY pattern but would fail for general `out = f(out, out)`.  Need to detect and insert a copy when aliasing is unsafe. |
| Dynamic field allocation | Low | `ti.field()` inside the driver is called every invocation.  For repeated solves, fields should be pre-allocated and reused.  Future: emit a solver *class* with `__init__` allocation and `solve()` method. |
| No convergence history | Low | The generated solver returns only the final `(x, k)`.  No residual history, no iteration log.  Add optional `% option history` directive. |
| Dense matvec only | Medium | The default `_matvec` kernel assumes dense storage.  Sparse and matrix-free require explicit type annotations.  See §8.3 and §8.4. |
| No nested algorithms | Low | Cannot compose algorithms (e.g., PCG *inside* Newton).  The driver must manually wire the inner solver call.  Future: `% call` directive. |
| No parallel reduction safety | Medium | The `_dot` and `_norm` kernels use `+=` which relies on Taichi's automatic atomic reduction.  Correct but may have non-deterministic floating-point summation order on GPU. |

---

## §14  Revision history

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2026-03-31 | Initial design spec.  MVP validated: 42/42 tests passing.  Taichi backend complete.  PCG algorithm transpiles to syntactically valid, structurally correct Taichi code. |
