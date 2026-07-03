# Migration History

A log of registry-wide migrations (schema changes, bulk renames, namespace splits).

## Format

One entry per migration:

```
## YYYY-MM-DD: short title

**Scope:** what changed (schema field, namespace split, status enum, etc.)

**Why:** the reason

**How:** the mechanics (script, manual sweep, etc.)

**Verification:** how it was confirmed clean
```

## v0.1: Seed instantiated

**Scope:** Empty registry, no documents, no symbols.

**Why:** new theory / framework / vocabulary; populated from scratch.

**How:** seeded from the csr-seed repository.

**Verification:** `python3 tools/csr.py build` reports `inputs=N errors=0 warnings=0 documents=0 symbols=0`.
