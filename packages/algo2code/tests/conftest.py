"""Shared fixtures for algo2code tests."""

import pytest

PCG_LATEX = r"""
% algorithm pcg
% backend taichi
% args A:matrix, b:vector, x:vector, M_inv:callable, tol:scalar, maxiter:scalar

% type r vector
% type z vector
% type p vector
% type q vector
% type rho scalar
% type alpha scalar
% type beta scalar

\begin{algorithmic}
\State $r = b - A \cdot x$                     % vector
\State $z = M^{-1}(r)$                         % vector
\State $p = z$                                  % vector
\State $\rho = r^\top z$                        % scalar
\For{$k = 0, 1, \ldots, \text{maxiter}$}
    \State $q = A \cdot p$                      % vector
    \State $\alpha = \frac{\rho}{p^\top q}$     % scalar
    \State $x = x + \alpha \, p$                % vector
    \State $r = r - \alpha \, q$                % vector
    \If{$\|r\| < \text{tol}$}
        \Return $x, k$
    \EndIf
    \State $z = M^{-1}(r)$                      % vector
    \State $\rho_{\text{new}} = r^\top z$        % scalar
    \State $\beta = \frac{\rho_{\text{new}}}{\rho}$
    \State $p = z + \beta \, p$                  % vector
    \State $\rho = \rho_{\text{new}}$
\EndFor
\Return $x, \text{maxiter}$
\end{algorithmic}
"""


@pytest.fixture
def pcg_latex():
    """Standard M_inv-based preconditioned CG (two-term recurrence, Polak-Ribière style)."""
    return PCG_LATEX
