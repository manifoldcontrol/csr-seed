# CSR Operations

Daily flow, CLI, agent collaboration.

## Daily flow

1. **Pull state.** `git pull` if under version control.
2. **Quarantine inbound.** Drop unclassified items as `quarantine/T-YYYY-MM-DD-NNN.md`.
3. **Triage.** For each quarantine item, classify (kind, namespace), run the gluing test. Promote to `queue/` or reject.
4. **Register.** Edit the appropriate `registry/*.csr` file with the new symbol or document.
5. **Build.** `python3 tools/csr.py build`. Confirm `errors=0`. Fix any new warnings or accept them with an explicit `convention_status` flag.
6. **Lookup-check.** `csr lookup` the new symbol to confirm it resolves.
7. **Audit.** Append a JSON line to `csr_edit_log.jsonl` describing the edit (`task_id`, `actor`, `file`, `summary`).

## CLI (`python3 tools/csr.py`)

```
csr build              # compile all registry/*.csr -> build/
csr lookup "phrase"    # search ids, display_names, definitions, aliases
csr deps <id>          # walk depends_on tree
csr deps <id> --inverse # walk used_by tree
csr pack --output csr.pyz  # repack the zipapp from tools/
```

The CLI runs from source (`tools/csr.py`); an optional single-file zipapp can be produced with `csr pack --output csr.pyz` for distribution, but running from source avoids the stale-zipapp failure mode.

## Agent collaboration

For multi-actor workflows (human + AI agent both editing):

- **Lock around the edit.** Operator-and-agent coordination is by convention: the agent reads the queue.csr index, claims an open task by setting `actor:` to its name, edits, marks `state: done`, appends to `csr_edit_log.jsonl`.
- **Snapshot before edit.** `cp registry/foo.csr registry/foo.csr.bak_pre_<change>` before editing. The mount layer in some Cowork sandboxes does not allow delete, so .bak files stay around until human cleanup.
- **Verify the artifact, not the script.** After edit, re-run `csr build` AND `csr lookup` on the changed entry. A script that prints "applied" does not mean the change landed.

## Silent-failure modes to watch for

1. **Edit-tool truncation.** Large `new_string` arguments can silently truncate the file. After any non-trivial edit, verify with `wc -l` and `tail`.
2. **Stale zipapp.** If you distribute a packed `csr.pyz`, repack after editing `tools/`; running from source sidesteps this entirely.
3. **Cached .pyc.** Editing a .py file without `touch`ing it can leave `__pycache__/*.pyc` stale; the cached bytecode runs instead of the new source.
4. **Mount-layer no-delete.** Some sandbox mounts allow `mv` and `cp` but not `rm`. Cleanup of old files requires manual delete by the human, or `mv` to an archive folder.
5. **Append-to-end-of-file.** Append edits sometimes drop the trailing newline. Verify with `tail -c 1 file | xxd | grep 0a`.
6. **Build returns errors=0 but state is corrupted.** Run `csr lookup` on the newly registered symbol to confirm it actually resolves through the pipeline.

## Status taxonomy ladder

```
draft   -> candidate -> provisional -> canonical
                                    \-> deprecated -> superseded_by(new_id)
                                    \-> rejected (terminal)
                                    \-> deferred (terminal until reopen)
```

Promotion rules live in `bump-policy.yaml`. A `canonical` symbol must have a verified `source_anchor` and a `verification.state in {tested, formalized, proved}` ideally; `argued` is admissible for prose-only canon.

## Versioning

- Document versions live in `documents.csr` (`version` field, `predecessor_version` for the previous one).
- Symbol versions track the document they belong to via the `definition_home: @v<ver>` locator.
- When a document bumps, run `python3 tools/bump.py` to migrate `definition_home` locators across all owned symbols in one pass.
