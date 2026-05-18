# algo2code

Transpile LaTeX algorithm boxes (`algpseudocode`) to executable code targeting Taichi, NumPy, or C/PETSc.

Parses `\begin{algorithmic}...\end{algorithmic}` environments with type-directed code generation.
Zero runtime dependencies — standard library only.

See `dev/design_docs/11-ALGO2CODE.md` in the [monorepo root](../../README.md) for the full specification.
