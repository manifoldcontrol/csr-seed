# csr-seed

a corpus semantic registry: documents define, the registry identifies. one symbol, one definition home, one registry identity, with content hashes that make silent definition drift detectable.

for corpora where documents, code, and an ai agent all touch the same vocabulary: research frameworks, spec-driven codebases, long-lived design docs. the registry compiles to a lockfile, a browsable wiki, a dependency graph, and a validation report with 20+ typed error codes.

## requirements

python 3.9+ and pyyaml (`pip install pyyaml`). nothing else.

## demo

`examples/relay/` is a small api project: an auth design doc, an api spec, and a client stub. two teams used the word *session* for different things; the registry records the collision and its resolution. `api_key` was renamed `access_token`; the alias keeps old references resolving.

```bash
# 1. build the example registry; open the rendered wiki
python3 tools/csr.py --root examples/relay/csr build
open examples/relay/csr/build/CSR.registry.html

# 2. edit one sentence of the auth spec and rebuild:
echo >> examples/relay/docs/auth_design_v1.md
python3 tools/csr.py --root examples/relay/csr build
```

```
CSR004 hash_drift: symbol csr.Auth.session: source changed after hash
pinning (pinned sha256:6dfd2f.. != current sha256:e42753..)
```

every symbol whose definition home changed is flagged until you re-verify and re-pin (`python3 tools/compute_hashes.py --force` from the example root).

a second example (`examples/gambit/`, a card-game rulebook vs. its engine) shows the same machinery on prose-vs-code drift.

## start your own registry

the repo root is a blank seed: empty `registry/*.csr` stubs, the compiler in `tools/`, config in `csr_config.yaml` / `csr_schema.yaml`.

1. register a document in `registry/documents.csr` (one block per document; the stub header shows the fields; `source_path` is relative to your corpus root)
2. add symbols (`registry/symbols_core.csr` to start; lift a namespace into its own file once it accumulates ~5+ symbols)
3. `python3 tools/csr.py build` produces the lockfile, wiki, graph, and validation report
4. pin hashes: `python3 tools/compute_hashes.py --force` replaces `source_hash: auto` with sha256 literals; from then on any source change is a CSR004 diagnostic until re-verified and re-pinned
5. renames get an `alias old -> new` one-liner (`registry/aliases.csr`); contested terms get a `collision` block (`registry/collisions_resolved.csr`)

`CLAUDE.md` is the operator manual, written so a human or an ai agent can run the registration workflow. `OPERATIONS.md` covers day-2 concerns.

## layout

the compiler treats the directory containing `registry/` as the registry root (`--root`, or walks up from cwd) and resolves document `source_path`s against the corpus root two levels above `build/` (`csr_config.yaml: corpus_root_levels_up`). the examples show the intended shape: a corpus root holding `docs/`, `src/`, and a thin `csr/` (registry + config, tools shared from this repo).

## tests

`python3 tests/test_csr_compile.py`

## related

[verification-events](https://github.com/manifoldcontrol/verification-events) (provenance events) and [lean-introspect](https://github.com/manifoldcontrol/lean-introspect) (proof-term leakage reports). a real-world instance, a mathematics preprint whose claim table is maintained as a registry, is at [fold-registry](https://github.com/manifoldcontrol/fold-registry).
