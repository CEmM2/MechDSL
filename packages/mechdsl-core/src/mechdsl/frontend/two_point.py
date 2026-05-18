"""Dual-index (two-point) tensor support for mixed-manifold indices.

This module is the **index validator** of the frontend — see
``packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md`` for the
parser-of-record vs adapter/normalizer/validator split (recovery-plan
Phase 2 / R1.3 / task ``P2-3``).

Resolves two-point tensor index families (lowercase ``i, j, k, l`` =
spatial; uppercase ``I, J, K, L`` = material) and rejects mixed-tier
expressions with stable error messages so downstream layers can trust
the index typing on every IR they receive.
"""
