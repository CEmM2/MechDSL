"""Shared helpers for end-to-end / integration tests in mechdsl-core.

post_recovery_plan Phase 6 (P6-1) — single source of truth for test
helpers that were previously duplicated across four sites:

- ``test_e2e_taichi.py``           (promoted in P6-2)
- ``plan_tests/recovery_plan_latex_contract/test_p7_2.py``  (promoted in P6-2)
- ``test_e2e_plastic.py``          (promoted in P7 cleanup)
- ``test_explicit_dynamics_acceptance.py``  (promoted in P7 cleanup)

All four call sites now import from this module. The family-split
rule (cross-test imports allowed once a third caller appears) is
satisfied. Future helpers used in 3+ test files belong here.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _import_generated_module(source: str, tmp_path: Path, name: str = "gen_e2e") -> ModuleType:
    """Write generated Taichi source to ``tmp_path/<name>.py`` and import
    it via ``importlib`` so tests can drive the emitted kernels.

    Identical signature and behaviour to the four previously-duplicated
    copies. Returns the loaded module object.
    """
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(source, encoding="utf-8")

    spec = importlib.util.spec_from_file_location(name, mod_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


__all__ = ["_import_generated_module"]
