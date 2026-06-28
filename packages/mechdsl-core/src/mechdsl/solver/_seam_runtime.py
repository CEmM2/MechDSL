"""Shared runtime plumbing for the generated-over-seam modules (PlanJune14).

Both :mod:`mechdsl.solver.seam_solve` (generated PCG, P4-2) and
:mod:`mechdsl.solver.seam_integrate` (generated Newmark-β, P6-1) transpile a LaTeX
algorithm box to runtime-mode Taichi source and import the generated driver. They
share two concerns, factored here so neither feature module reaches across the
other's (private) boundary:

* :func:`strip_ti_init` — drop the module-level ``ti.init(...)`` line so the
  **caller** owns Taichi initialisation / the device. Re-init at import would free
  the caller's already-allocated DOF fields (the P2-2 finding); stripping it makes
  the generated body device-agnostic.
* :func:`import_generated_module` — write generated source to a real ``.py`` file
  and import it. Taichi needs ``inspect.getsource`` on the driver, so the code
  cannot be ``exec``'d. Mirrors ``tests/_e2e_helpers._import_generated_module`` /
  the P2-2 pattern.
"""

# NOTE: no ``from __future__ import annotations`` — kept consistent with the seam
# modules that consume this helper and wire imported generated code into
# ``@ti.kernel`` bodies needing eager annotation evaluation (PEP 563 breaks the
# JIT; the PJ-0/PJ-1 finding).

import importlib.util
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType

# Matches a module-level ``ti.init(...)`` line regardless of indentation/spacing,
# so :func:`strip_ti_init` can never miss it. A missed init line would
# re-initialise Taichi at import and free the caller's already-allocated DOF
# fields (the P2-2 finding).
TI_INIT_LINE = re.compile(r"^\s*ti\.init\s*\(")


def strip_ti_init(code: str) -> str:
    """Drop the module-level ``ti.init(...)`` line(s) from generated *code*.

    The caller owns Taichi initialisation (device/arch); re-init here would free
    already-allocated DOF fields (the P2-2 finding), so the result is
    device-agnostic — it runs on whatever arch the caller's ``ti.init`` selected.
    """
    return "\n".join(line for line in code.splitlines() if not TI_INIT_LINE.match(line))


def import_generated_module(source: str, name: str) -> ModuleType:
    """Write generated Taichi *source* to a real ``.py`` file and import it.

    Taichi requires ``inspect.getsource`` on the driver, so the generated code
    must live in a real module file (not ``exec``'d). Mirrors
    ``tests/_e2e_helpers._import_generated_module`` / the P2-2 pattern.
    """
    tmp = Path(tempfile.mkdtemp())
    path = tmp / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib invariant
        raise ImportError(f"could not build import spec for generated module {name!r}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


__all__ = ["TI_INIT_LINE", "import_generated_module", "strip_ti_init"]
