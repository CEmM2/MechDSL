# Phase 3 Context Summary: Type Validation (`__post_init__`)

## Must Know

### Files modified
- `symbolic/models/j2_power_law.py` — J2PowerLawMaterial `__post_init__`, freeze ReturnMappingResult, comment fixes
- `symbolic/models/svk.py` — SVKMaterial `__post_init__` + `from_E_nu` validation
- `solver/mesh_io.py` — HexMesh `__post_init__`
- `ir/element_ir.py` — QuadratureRule `__post_init__`
- `codegen/boundary_codegen.py` — DirichletBC/NeumannBC `__post_init__`
- `solver/history_fields.py` — error messages + duplicate guard

### Conventions
- **IR discipline**: "IRs are immutable dataclasses. Validation runs at construction time." — CLAUDE.md. Every frozen dataclass in the IR layers should have a `__post_init__` that validates its invariants.
- **Error messages**: Use `f"field_name must be X, got {self.field}"` pattern. Include the actual value for debuggability.
- **Tension-positive stress**: When checking material params, `sigma_y0 > 0` (yield stress) and `mu > 0` (shear modulus) are physical requirements.

### Key principles
- **All existing constructions must pass**: The plan review verified that no existing test or factory function constructs invalid instances. Adding `__post_init__` should not break any existing tests.
- **Frozen dataclass + `__post_init__`**: Python calls `__post_init__` after `__init__` even for frozen dataclasses. Use `object.__setattr__` only if you need to modify fields (not needed here — we only validate).
- **ReturnMappingResult freezing**: This changes a mutable `@dataclass` to `@dataclass(frozen=True)`. The plan review confirmed no caller reassigns fields on the result, so this is safe.

### Pre-resolved design decisions
- **SVKMaterial validation**: Only check `mu > 0`, not `lam`. Negative `lam` is physically valid for auxetic materials.
- **HexMesh validation**: Check shapes and consistency (n_nodes vs coords.shape[0]) but NOT connectivity bounds (np.all(connectivity < n_nodes)). Bounds checking is O(n_elem) and deferred to avoid slowing construction.
- **HistoryFields**: Not a frozen dataclass — intentionally mutable for state management. Only improve error messages and add duplicate guard.

## Should Know

### Downstream impact
- Phase 5 task R3.5.3 adds tests for all new `__post_init__` validators.
- Phase 5 tasks R3.5.1 depends on R3.3.1 (J2PowerLawMaterial must validate before testing error paths).
- Comment fixes H12 (`# unit normal` → `# flow direction n = S_dev / q`) and H13 (§3.3 → §3.4) in j2_power_law.py affect only comments, no behavioral change.
