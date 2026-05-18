# Phase 3 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P3-1 | Add optional semantic fields to `ProblemIR`: `fields`, `doma | none | passthrough |
| P3-4 | Define a stable `ProblemIR` minimal subset for the MVP-stabl | none | passthrough |
| P3-2 | Add compatibility constructors/adapters from the current thi | none | passthrough |
| P3-3 | Move boundary/domain assumptions out of scattered runtime/co | none | passthrough |
| P3-5 | Add targeted IR validation for semantics that were previousl | none | passthrough |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 10 |
| Cases covered by existing tests | 0 |
| New stubs generated | 10 |
| New stub files | 6 |
| Tasks needing human review | 0 |

## Notes

- All Phase-1 recovery-plan tasks are docs-tier; stubs use `@pytest.mark.audit`.
- Stubs currently `pytest.skip(...)` and become live assertions when each task lands.
- Compressed-exec convention: all 6 Phase-2 tasks land on a single branch with one commit each, then a phase-end Gate B/C.
