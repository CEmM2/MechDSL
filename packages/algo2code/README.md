# algo2code

Transpile LaTeX algorithm boxes (`algpseudocode`) to executable code targeting Taichi or NumPy (C/PETSc planned).

```python
from algo2code import transpile

transpile(source, backend="taichi")  # Taichi kernels + Python driver
transpile(source, backend="numpy")   # plain function that imports only NumPy
```

Parses `\begin{algorithmic}...\end{algorithmic}` environments with type-directed code generation.
Zero runtime dependencies — standard library only.

## Documentation

- **User docs:** <https://sosovski.group/MechDSL/algo2code/> — introduction, getting
  started, usage, and examples.
- **Design spec:** `dev/design_docs/11-ALGO2CODE.md` (authoritative source of truth).
- See the [monorepo root](../../README.md) for the full project overview.
