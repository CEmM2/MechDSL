---
name: compile-check
description: Trace a LaTeX input through the compiler pipeline and identify which layers are implemented vs missing. Use during development to find what blocks end-to-end compilation.
allowed-tools: Read, Grep, Glob, Bash
model: sonnet
---

# Compile Check

Given a LaTeX input snippet (or a description of a problem), trace it through the MechDSL compiler pipeline and report the status of each layer.

## Input

$ARGUMENTS

If no arguments given, use the MVP input:
```
% mechanics dim 3
% mechanics cell hex8
% mechanics material hooke_power_law --E E --nu nu --sigma_y0 sigma_y0 --K K --n n
% mechanics formulation total_lagrangian
```

## Process

For each layer, check whether the code exists and is functional:

### Layer 1 — Frontend (`mechdsl.frontend`)
- Can the directives be parsed? Check `directives.py` for the relevant directive handlers.
- Are the required tensor types supported? Check `two_point.py`.
- Status: ✅ Implemented / 🚧 Partial / ❌ Not started

### Layer 2 — Symbolic Engine (`mechdsl.symbolic`)
- Is the constitutive model implemented? Check `symbolic/models/`.
- Are kinematics complete for this formulation? Check `kinematics.py`.
- Is the Voigt contraction available? Check `voigt.py`.
- Status: ✅ / 🚧 / ❌

### Layer 3 — Mechanics IR (`mechdsl.ir.mechanics_ir`)
- Can a ProblemIR be constructed for this input?
- Is validation present for the relevant constructs?
- Status: ✅ / 🚧 / ❌

### Layer 4 — Element IR (`mechdsl.ir.element_ir`, `mechdsl.lowering`)
- Is the element type supported? Check `fe_localise.py`.
- Are basis functions and quadrature available?
- Can einsum strings be extracted?
- Status: ✅ / 🚧 / ❌

### Layer 4b — Einsum Optimiser (`mechdsl.codegen.einsum_optimizer`)
- Can contraction plans be generated?
- Status: ✅ / 🚧 / ❌

### Layer 5 — Taichi Codegen (`mechdsl.codegen.taichi_printer`)
- Can a complete solver file be emitted?
- Status: ✅ / 🚧 / ❌

### Layer 6 — Verification (`mechdsl.verify`)
- Are reference solutions available for this problem?
- Status: ✅ / 🚧 / ❌

## Output

A table showing each layer's status and what specifically is blocking or missing. Prioritise the blockers — what's the next thing to implement to make progress?
