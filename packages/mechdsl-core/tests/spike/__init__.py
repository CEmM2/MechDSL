"""PJ-1 — SVK all-Taichi spike (architecture gate for PlanJune14).

The spike proves the *Seams & Bodies* architecture composes: a matrix-free
``@ti.kernel`` SVK tangent operator (the body PJ-3 will *generate*) injected into
the ``ti_runtime`` solver seams, driven by a PCG body (the body PJ-2's algo2code
backend will *generate*) and a thin Newton loop — solving a single Hex8 SVK patch
all-on-device and matching the handwritten NumPy reference to <1e-10.
"""
