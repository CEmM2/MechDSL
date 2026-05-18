"""Constitutive models.

Support tier (per ``README.md`` Support tiers and
``dev/plans/recovery_plan_latex_contract.md`` Phase 1 (R0)):

- **MVP-stable**: ``svk`` (St. Venant–Kirchhoff), ``j2_power_law`` (J2 plasticity
  with power-law hardening). Only these two are part of the canonical
  LaTeX-driven compile path.
- **experimental**: ``neo_hookean``, ``mooney_rivlin``, ``ogden``, ``hgo``,
  ``perzyna``, ``johnson_cook``, ``lemaitre``. Preserved in tree; not part of
  the contract surface.
"""
