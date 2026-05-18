# 09 — Einsum Optimiser and JIT Budget Counter

---

## 1  Purpose

The einsum optimiser is a compile-time layer that sits between the symbolic engine (Layer 2/3) and the Taichi code generator (Layer 4). It solves two problems simultaneously:

1. **Contraction order optimisation.** A multi-tensor contraction like the TL element stiffness $k_{aibj} = \frac{\partial N_a}{\partial X_I}\,F_{iK}\,\mathbb{C}_{KILJ}\,F_{jL}\,\frac{\partial N_b}{\partial X_J}$ has $O(N^8)$ cost when contracted naively but only $O(N^5)$ with the optimal pairwise decomposition — a 46× FLOP reduction. opt_einsum finds this decomposition automatically.

2. **JIT budget control.** Taichi's JIT compiler unrolls every `ti.static` loop at compile time. Full unrolling of element kernels produces tens of thousands of lines for higher-order 3D elements, causing minute-long compiles or JIT OOM. The budget counter prevents this by classifying each contraction step into a tier that determines the emission strategy.

---

## 2  Index partitioning

Every index in a FEM tensor contraction falls into one of two categories:

| Category | Examples | Range | Taichi treatment |
|----------|----------|-------|-----------------|
| **Physics** | $i,j,k,l$ (spatial), $I,J,K,L$ (material), $V,W$ (Voigt) | 2–6 | `ti.static` (unrolled) |
| **Mesh** | $a,b$ (nodes), $q$ (quad points), $e$ (elements) | 3–10⁶ | Runtime loop |

**Rule:** opt_einsum operates exclusively on physics-index contractions. Mesh indices are handled by the code generator's element loop structure. The two concerns do not interact.

**Classification criterion:** An index with range $\le$ `physics_dim_max` (default 6) is physics. Anything larger is mesh.

---

## 3  JIT budget thresholds

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `func_budget` | 512 | Max unrolled lines per `@ti.func` |
| `kernel_budget` | 2000 | Max total unrolled lines per `@ti.kernel` |
| `ceiling` | 5000 | Absolute hard limit — never exceed |
| `tier1_max_entries` | 36 | Max entries for `ti.Matrix @` (6×6) |
| `physics_dim_max` | 6 | Max index range to classify as physics |

**Empirical basis:**

| Unrolled lines | JIT compile time | Assessment |
|----------------|------------------|------------|
| < 100 | < 1 s | Instant |
| 100–500 | 1–5 s | Tolerable |
| 500–2000 | 5–30 s | Acceptable for research |
| 2000–5000 | 30 s – minutes | Painful |
| > 5000 | Minutes or OOM | Unusable |

---

## 4  Tier classification

### Tier 1 — Native `ti.Matrix @`

**Criteria:** both operands rank ≤ 2, all dimensions ≤ 6, output ≤ 36 entries, BLAS type is GEMM or DOT.

**JIT cost:** 0 unrolled lines (Taichi handles `@` internally).

**Applies to:** $P = F \cdot S$, $C = F^T F$, $\sigma = (1/J)\,P\,F^T$, Mandel tangent rotation $T\,C_M\,T^T$, 2D Voigt $B^T C B$ intermediate steps.

**Implementation:** Pre-written library of ~5 `@ti.func` functions. No code generation needed.

### Tier 2 — Emitted `ti.static` loops

**Criteria:** unrolled multiply-add count ≤ `func_budget` (512) but does not qualify for Tier 1 (rank > 2, or output too large for `ti.Matrix`).

**JIT cost:** equals the multiply-add count (each unrolled line ≈ one multiply-add).

**Applies to:** rank-4 tangent push-forward ($F_{iK}\,\mathbb{C}_{KILJ}\,F_{jL}$, 243 lines/step), 3D Voigt $B^T C B$ steps (36 lines/step), stress from tangent ($\sigma_{ij} = C_{ijkl}\,\varepsilon_{kl}$, 81 lines).

**Implementation:** Python emitter generates the specific `ti.static` loop nest, flat-index arithmetic, and intermediate allocation for each step.

### Tier 3 — Runtime fallback

**Criteria:** unrolled multiply-add count > `func_budget`.

**JIT cost:** reduced to the innermost contracted dimension only (e.g. 3 lines instead of 729).

**Applies to:** exotic contractions not encountered in standard FEM (e.g. rank-5 tensor operations). Acts as a safety net.

**Implementation:** outer indices become runtime loops; only the innermost sum stays `ti.static`. Correctness is preserved; performance is lower than Tier 2 but compilation is guaranteed.

---

## 5  Unrolled line counting

For a pairwise contraction step with einsum `AB,CD->EF`:

$$
\text{static\_lines} = \prod_{c \in \text{output} \cap \text{physics}} \text{range}(c) \;\times\; \prod_{c \in \text{contracted} \cap \text{physics}} \text{range}(c)
$$

This counts the total number of multiply-add statements that will be unrolled by `ti.static`. Runtime-loop indices do not contribute — they wrap the static body without increasing it.

**Example:** Push-forward step `KILJ,iK->ILJi`

- Output indices: $I,L,J,i$ — all physics (range 3)
- Contracted index: $K$ — physics (range 3)
- Static lines = $3^4 \times 3^1 = 243$

**Example:** Node scatter `dN_{aI}\,A_{iIjJ}\,dN_{bJ}$

- Output indices: $a,b$ (mesh, runtime), $i,j$ (physics, range 3)
- Contracted indices: $I,J$ (physics, range 3)
- Static lines = $3^2 \times 3^2 = 81$ (node loops are runtime, not counted)

---

## 6  Budget for complete element kernels

Measured budgets for all element types in this project:

| Element | Physics kernel | Scatter | Total | Budget (2000) |
|---------|---------------|---------|-------|---------------|
| Tri3 2D | 0 (Tier 1) | 16 | 16 | ✓ |
| Q4 2D | 0 (Tier 1) | 16 | 16 | ✓ |
| Q8 2D | 0 (Tier 1) | 16 | 16 | ✓ |
| Tet4 3D | 36 + 6 | 81 | 123 | ✓ |
| Tet10 3D | 36 + 6 | 81 | 123 | ✓ |
| Hex8 3D | 36 + 6 | 81 | 123 | ✓ |
| Hex20 3D | 36 + 6 | 81 | 123 | ✓ |
| TL push-forward 3D | 243 + 243 | 81 | 567 | ✓ |

All cases are well within the kernel budget of 2000. The worst case (TL push-forward) uses 28% of the budget.

---

## 7  Interface

```python
from compmech.codegen.einsum_optimizer import plan_contraction, JITBudget

budget = JITBudget()  # uses defaults

plan = plan_contraction(
    einsum_str='iK,KILJ,jL->iIjJ',
    shapes=[(3,3), (3,3,3,3), (3,3)],
    dim=3,
    n_nodes=10,
    budget=budget,
)

assert not plan.over_budget
assert plan.total_static_lines == 567
assert plan.speedup == 2.25

for step in plan.steps:
    if step.tier == 1:
        # emit library call
        ...
    elif step.tier == 2:
        # emit ti.static loop nest
        ...
    elif step.tier == 3:
        # emit runtime fallback
        ...
```

---

## 8  Integration with SymPDE TerminalExpr

The TerminalExpr expansion produces component-wise derivative expressions like `dx1(u[0]) * dx1(v[0])`. To extract einsum strings:

1. Walk the TerminalExpr matrix and identify all derivative operators acting on trial/test functions.
2. Map each derivative to an index: `dx1` → index 0, `dx2` → index 1, etc.
3. Map each field component to a tensor index.
4. Reconstruct the einsum string from the contraction pattern.
5. Pass to `plan_contraction()`.

This extraction is deterministic and happens once at compile time.
