r"""Canonical Preconditioned Conjugate Gradient (PCG) algorithm in algpseudocode.

This module is the **algo2code interface hook** consumed by
``mechdsl-core``'s ``Algo2CodePCGSolver`` adapter (Plan recovery task P6-1).
It exposes:

* :data:`PCG_ALGORITHM_LATEX` — the verbatim LaTeX source of the canonical
  PCG algorithm, mirrored from
  ``dev/tasks/recovery_plan_latex_contract/json/P6-1.json`` field
  ``pcg_algorithm_latex.latex``.
* :func:`get_pcg_algorithm_latex` — accessor returning that text.

Runtime invariant
-----------------

This module imports **only stdlib**.  ``algo2code`` is the runtime-free
sibling package of ``mechdsl-core`` (see ``.claude/CLAUDE.md`` /
``dev/design_docs/11-ALGO2CODE.md``); nothing here imports — directly or
transitively — ``mechdsl``.  Consumers that want a runnable implementation
own the translation step.

Transpilation status (issue #307, updated)
------------------------------------------

This LaTeX **now transpiles** via :func:`algo2code.transpile`. The original
deferral — multi-letter scratch identifiers such as ``pq`` tokenising as
``p * q`` — was resolved by the tokenizer's multi-character identifier rule
(``expr_parser.TOKEN_PATTERNS``), and the compound updates lower correctly via
the SSA vector-lowering pass (issue #307 F1/F2). The generated ``pcg`` driver is
runnable Taichi.

``mechdsl-core``'s ``Algo2CodePCGSolver`` is the hand-written, line-by-line
translation. A numeric comparison (hand-written vs ``transpile`` output, run under
Taichi) now shows them **bit-identical on every path** — both the converged path
and the max-iteration-exhausted path — after the for-loop range lowering was
fixed to emit the inclusive ``range(start, end + 1)`` (issue #307; the generated
``\For{$k = 1, ..., \text{maxiter}$}`` previously did one fewer iteration). The
parity is guarded by
``...recovery_plan_latex_contract/test_pcg_transpiler_parity.py``.

The hand-translation is **retained** despite the parity, because the generated
code and the consumer have different runtime models: ``transpile`` emits **Taichi**
operating on a **dense matrix field** ``A``, whereas the Newton seam
(``mechdsl.solver.newton``) is **matrix-free numpy** — it passes the tangent as a
matvec callback and never forms ``A``. Swapping the generated Taichi code in would
break that matrix-free contract. A literal code replacement would require a numpy
backend for algo2code that emits a matrix-free PCG matching ``LinearSolverInterface``
(the numpy backend is currently a stub). Until then the adapter stays, but it is
no longer a maintenance hazard: the parity test mechanically proves it stays
faithful to this canonical LaTeX. Behaviour is also pinned by
``...recovery_plan_latex_contract/test_p6_1.py``.
"""

from __future__ import annotations

# ── Canonical algorithm source ───────────────────────────────────────────────
PCG_ALGORITHM_LATEX: str = r"""% algorithm pcg
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
\end{algorithmic}"""


def get_pcg_algorithm_latex() -> str:
    """Return the canonical PCG algpseudocode LaTeX source.

    Consumers (e.g. ``mechdsl.solver.import_adapter.Algo2CodePCGSolver``)
    use the returned string both as the specification artifact for their
    runtime translation and as input to ``algo2code.transpile`` once the
    parser supports the full surface (see *Parser deferral note* in this
    module's docstring).

    Returns
    -------
    str
        Verbatim LaTeX source of the canonical PCG algorithm, including
        the leading ``% algorithm`` / ``% backend`` / ``% args`` / ``% type``
        directive comments.
    """
    return PCG_ALGORITHM_LATEX


__all__ = [
    "PCG_ALGORITHM_LATEX",
    "get_pcg_algorithm_latex",
]
