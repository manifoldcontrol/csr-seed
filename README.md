# csr-seed — a Corpus Semantic Registry

An identity registry for hybrid code+prose corpora: **documents define, the
registry identifies.** One symbol, one definition home, one registry
identity — with content hashes that make silent definition drift detectable.

Built for corpora where documents, code, and an AI agent all touch the same
vocabulary: research frameworks, spec-driven codebases, long-lived design
docs. The registry compiles to a lockfile, a browsable wiki, a dependency
graph, and a validation report with 20+ typed error codes.

## Requirements

Python 3.9+ and PyYAML (`pip install pyyaml`). Nothing else.

## The 60-second demo

The `examples/relay/` corpus is a small API project: an auth design doc, an
API spec, and a client stub. Two teams used the word *session* for different
things; the registry records the collision and its resolution. `api_key` was
renamed `access_token`; the alias keeps old references resolving.

```bash
# 1. build the example registry; open the rendered wiki
python3 tools/csr.py --root examples/relay/csr build
open examples/relay/csr/build/CSR.registry.html

# 2. now edit one sentence of the auth spec (simulate an agent silently
#    changing a definition), and rebuild:
echo >> examples/relay/docs/auth_design_v1.md
python3 tools/csr.py --root examples/relay/csr build
```

```
CSR004 hash_drift: symbol csr.Auth.session: source changed after hash
pinning (pinned sha256:6dfd2f.. != current sha256:e42753..) — re-verify the
definition, then re-pin with compute_hashes --force
```

Every symbol whose definition home changed is flagged. **The docs can no
longer lie silently.** Re-verify, re-pin (`python3 tools/compute_hashes.py
--force` from the example root), clean build.

A second example (`examples/gambit/`, a card-game rulebook vs. its engine)
shows the same machinery on prose-vs-code drift.

## Start your own registry

The repo root is a blank seed: empty `registry/*.csr` stubs, the compiler in
`tools/`, config in `csr_config.yaml` / `csr_schema.yaml`.

1. Register a document in `registry/documents.csr` (one block per document;
   the stub header shows the fields; `source_path` is relative to your
   corpus root).
2. Add symbols (`registry/symbols_core.csr` to start; lift a namespace into
   its own file once it accumulates ~5+ symbols).
3. `python3 tools/csr.py build` → lockfile, wiki, graph, validation report.
4. Pin reality: `python3 tools/compute_hashes.py --force` replaces
   `source_hash: auto` with sha256 literals; from then on any source change
   is a CSR004 diagnostic until you re-verify and re-pin.
5. Renames get an `alias old -> new` one-liner (`registry/aliases.csr`);
   contested terms get a `collision` block (`registry/collisions_resolved.csr`).

`CLAUDE.md` is the operator manual — written so a human *or an AI agent* can
run the registration workflow; that dual audience is the design point.
`OPERATIONS.md` covers day-2 concerns.

## Layout expectations

The compiler treats the directory containing `registry/` as the registry
root (`--root`, or walks up from cwd) and resolves document `source_path`s
against the corpus root two levels above `build/` (`csr_config.yaml:
corpus_root_levels_up`). The examples show the intended shape: a corpus root
holding `docs/`, `src/`, and a thin `csr/` (registry + config, tools shared
from this repo).

## Tests

`python3 tests/test_csr_compile.py` — parser, hashes, collision round-trips,
alias cycles, failing fixtures, seed integrity (ships empty, parses clean).

## Family

The identity leg of a three-part verification infrastructure:
[verification-events](https://github.com/manifoldcontrol/verification-events) (provenance events) and
[lean-introspect](https://github.com/manifoldcontrol/lean-introspect) (proof-term leakage reports). Each
stands alone. A real-world instance — a mathematics preprint whose claim
table is maintained as a registry — is published separately as
[fold-registry](https://github.com/manifoldcontrol/fold-registry).
