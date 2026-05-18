---
name: update-golden
description: Regenerate golden artifact files for a test case after an intentional change. Includes diff review before committing the update.
allowed-tools: Read, Bash, Glob, Grep, Write
model: sonnet
---

# Update Golden Files

Regenerate and review golden artifact files after an intentional compiler change.

## Input

$ARGUMENTS — the test case name or pattern (e.g. "hex8_elastic", "all")

## Process

1. **Identify affected golden files**
   ```bash
   ls packages/mechdsl-core/tests/golden/ | grep "$ARGUMENTS"
   ```
   If "all" is specified, list everything in `packages/mechdsl-core/tests/golden/`.

2. **Backup current golden files**
   ```bash
   cp packages/mechdsl-core/tests/golden/<file> packages/mechdsl-core/tests/golden/<file>.bak
   ```

3. **Regenerate by running the relevant test with update flag**
   ```bash
   uv run pytest packages/mechdsl-core/tests/ -k "<pattern>" --update-golden -v
   ```
   (If `--update-golden` is not yet implemented, run the compilation pipeline manually and capture the artifact output.)

4. **Diff review** — Show the diff between old and new golden files:
   ```bash
   diff packages/mechdsl-core/tests/golden/<file>.bak packages/mechdsl-core/tests/golden/<file>
   ```

5. **Categorise changes**:
   - 🟢 **Expected**: changes that directly correspond to the intentional modification.
   - 🟡 **Indirect**: changes in downstream artifacts caused by the modification (e.g. different contraction plan after changing an expression).
   - 🔴 **Suspicious**: changes that don't obviously relate to the modification — these need investigation.

6. **Report** — present the categorised diff and ask for confirmation before keeping the new golden files.

7. **Clean up** — remove `.bak` files after confirmation.

## Important

- Never auto-approve golden file updates. Always show the diff first.
- If any change is categorised as 🔴 Suspicious, flag it prominently and recommend investigation before accepting.
