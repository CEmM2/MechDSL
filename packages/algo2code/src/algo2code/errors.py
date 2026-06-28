"""Exception types for algo2code.

The transpiler must *fail loud*: any LaTeX construct it cannot faithfully lower
should raise, never silently emit wrong (or empty) code. Finding F6 in issue #307
documented the opposite — statements vanished and invalid ``ti.field`` arithmetic
shipped without warning. These exception types are the contract that replaces that
silent behaviour.

Convention (mirrors the mechdsl-core IR discipline): an ``UnsupportedConstructError``
message names the offending construct *and* the workaround or plan phase that would
add support, so the failure is actionable.
"""

from __future__ import annotations


class Algo2CodeError(Exception):
    """Base class for all algo2code transpilation errors."""


class UnsupportedConstructError(Algo2CodeError):
    """A LaTeX construct is recognised but not supported by the transpiler.

    Raised instead of silently skipping a token, dropping a statement, or
    emitting un-runnable code. The message should tell the user what to do
    instead (e.g. use a subscript, use mechdsl-core einsum, declare a callable).
    """
