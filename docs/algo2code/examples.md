# Examples

Every snippet here is self-contained — `algo2code` has no runtime dependencies, so these
run anywhere the package is importable.

!!! tip "Run them with `uv`"
    Inside the workspace, prefix commands with `uv run` (e.g. `uv run python ex.py`) after
    `uv sync --all-packages --all-groups --all-extras`.

## Transpile a library algorithm

The fastest path is the convenience wrappers — each returns generated Taichi source as a
string:

```python
from algo2code.library.radial_return_j2 import transpile_radial_return_j2

code = transpile_radial_return_j2(backend="taichi")
print(code)        # deterministic Taichi-compatible Python source
```

## Transpile from the verbatim LaTeX

Equivalent to the wrapper, but shows the LaTeX-is-the-source-of-truth path explicitly:

```python
from algo2code import transpile
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX

code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")
```

## The full J2 family

All three return-map variants follow the same shape — only the constant and wrapper change:

```python
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX
from algo2code.library.radial_return_j2_kinematic import RADIAL_RETURN_J2_KINEMATIC_LATEX
from algo2code.library.radial_return_j2_mixed import RADIAL_RETURN_J2_MIXED_LATEX
from algo2code import transpile

for name, latex in [
    ("isotropic power-law", RADIAL_RETURN_J2_LATEX),
    ("linear kinematic",    RADIAL_RETURN_J2_KINEMATIC_LATEX),
    ("mixed hardening",     RADIAL_RETURN_J2_MIXED_LATEX),
]:
    code = transpile(latex, backend="taichi")
    print(f"{name}: {len(code)} chars of generated source")
```

These scalar return-maps are the inner loops of the J2 plasticity models in mechdsl-core —
see [Usage → how the J2 family is wired](usage.md#how-the-j2-family-is-wired-into-the-solver).

## Transpile the PCG solver

```python
from algo2code import transpile, PCG_ALGORITHM_LATEX

code = transpile(PCG_ALGORITHM_LATEX, backend="taichi")
```

The generated PCG is the single source of truth behind mechdsl-core's
`Algo2CodePCGSolver`, selectable in the Newton driver via
`select_linear_solver("generated")` — see [Usage → the solver seam](usage.md#the-solver-seam).

## Exec generated code into a callable

`transpile` returns source *text*. To get a function you can call, `exec` it. The emitted
function name matches the algorithm name:

```python
from algo2code import transpile
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX

code = transpile(RADIAL_RETURN_J2_LATEX, backend="taichi")

ns: dict = {}
exec(compile(code, "<algo2code>", "exec"), ns)
radial_return_j2 = ns["radial_return_j2"]   # the scalar return-map, now callable
```

## Inspect the parsed AST

The intermediate stages are exported, so you can look at what the parser and type
inference produced before codegen:

```python
from algo2code import parse_algorithm, infer_types
from algo2code.library.radial_return_j2 import RADIAL_RETURN_J2_LATEX

algo = parse_algorithm(RADIAL_RETURN_J2_LATEX)   # Algorithm AST
infer_types(algo)                                # annotate scalar/array types in place
print(algo.name)
```
