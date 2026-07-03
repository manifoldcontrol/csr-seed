# queue/

Active or completed registration tasks. One subdirectory per task with the form `T-YYYY-MM-DD-NNN/`.

Typical contents per task:
- `intake.md` - task proposal (parking_reason, related_symbols, related_documents)
- `closure.md` - when the task is done, what was registered or rejected

`queue.csr` (in the repo root) holds a YAML-style index of all tasks and their states.

States: `quarantined` → `queued` → `active` → `done` (or `rejected`).
See `OPERATIONS.md` for the workflow.
