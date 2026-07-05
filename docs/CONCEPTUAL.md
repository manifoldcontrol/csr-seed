# Corpus Semantic Registry: Conceptual Outline (v0)

A document about CSR itself: what it is, what problem it solves, how the parts fit together, and where the boundaries are. Conceptual scope; the procedural companions are `OPERATIONS.md` (daily workflow and CLI reference) and `CLAUDE.md` (agent navigation and registration recipes). The implementation spec series is internal to the production instance.

**Version:** v0
**Status:** candidate
**Date:** 2026-06-03
**Provenance:** written for and used by the production instance (1,486 symbols across 191 documents as of 2026-07); published with the seed because the architecture is the same at any scale.

---

## 1. What CSR is

CSR is a registry layer over a corpus of documents. Two layers, one apparatus:

- **The corpus** is a set of documents (`.tex`, `.md`, source code, working notes). Documents own prose, math, definitions, and proofs. They are the substantive content.
- **The registry** is a structured index of names, versions, dependencies, status, aliases, collisions, and audit history. It is small relative to the corpus, machine-readable, and authoritative for cross-document identity.

The split is the central design move: **documents define, the registry identifies**. When two documents touch the same concept, the registry resolves which one is canonical. When a symbol moves or is renamed, the registry records the predecessor edge and downstream consumers do not churn. When a document bumps version, the registry absorbs the cross-document version delta so that other documents continue to cite by name.

## 2. The problem CSR solves

Without a registry, every document in a multi-document corpus carries its own cross-reference table to every other document. That state shape is unmaintainable past about a dozen documents. The failure modes are predictable:

1. **Xref drift.** A symbol gets renamed in its definition home. Cross-references in N other documents continue to cite the old name. Build still passes; the corpus is silently inconsistent.

2. **Version-tag explosion.** Every document carries explicit version pointers to every doc it cites. A version bump in one doc forces text edits across all consumers. Operators avoid bumping. Documents drift out of date because the cost of bumping is the cost of editing everywhere.

3. **Collision-by-coincidence.** Two documents independently introduce a symbol with the same name. Both are canonical from inside the document; neither is canonical from the corpus-wide view. The conflict goes unresolved because no layer owns adjudication.

4. **Deprecated definitions live forever.** A document gets superseded by a successor. References in third-party docs continue to point at the superseded one because no machine-readable supersession edge exists. The superseded artifact accumulates pseudo-canon.

5. **Audit gaps.** Who registered what, when, and why is dispersed across git history (which records bytes) and not connected to the symbol-level decisions. Reconstructing a chain of definition lineage requires archaeology.

CSR removes these failures by making cross-document identity a first-class registry concern. The corpus continues to grow; the registry tracks what is canonical, what is candidate, what is deprecated, and what supersedes what.

## 3. Architecture

The CSR architecture has five components:

### 3.1. Documents (the corpus)

A document is a file with prose: `.tex`, `.md`, source code, working notes. Documents are owned by their authors and edited freely. The registry does not constrain document content. A document becomes registered when an operator adds an entry to `registry/documents.csr` declaring its identity.

### 3.2. Symbols (registry-level concepts)

A symbol is a named concept that belongs to a document. Symbols are the unit of cross-document reference. Each symbol has:

- A globally unique `id` (e.g., `csr.MyDoc.my_symbol`).
- A `namespace` (typically the owning document's name).
- A `definition_home` locator pointing into the source document.
- A `type` (concept, operator, structure, schema, axiom, theorem, predicate, open_problem).
- A `framework_layer` (algebra, cross_layer, domain, procedure, registry, representation).
- A `status` on the seven-level ladder.
- A `definition` (one-line or paragraph summary; the canonical short statement).
- A `source_anchor` (the section locator with hashes for drift detection).
- A `verification` block (state, method, last_verified date).
- Relation lists (`depends_on`, `refines`, `instantiates`, `used_by`, etc.).
- Optional `notation` block (claimed letters, convention_status).

Symbols live in `registry/*.csr` files. The compiler validates them and emits a lockfile.

### 3.3. The compiler (engine)

The compiler reads all `registry/*.csr` files and produces `build/CSR.lock.json` plus several rendered views (markdown, HTML, Graphviz dot, LaTeX fragments). The compiler validates:

- ID uniqueness, namespace coherence, status taxonomy.
- Dependency resolution and cycle detection.
- Source-anchor structure (and optionally source-hash drift).
- Notation conventions (CSR027: reserved-letter check).
- Document declarations (every document referenced as `owning_document` must be registered).

The compiler does not modify the corpus; it reads the registry and writes only to `build/`. The build is deterministic: same registry produces same lockfile.

### 3.4. The lockfile (compiled state)

`build/CSR.lock.json` is the machine-readable snapshot of registry state. Every downstream consumer (HTML renderer, dependency graph generator, registry browser, search tools, agent integrations) reads the lockfile; the `.csr` source is consumed only by the compiler. This isolates consumers from parser changes and centralizes the validation pass.

### 3.5. The audit trail

`csr_edit_log.jsonl` is an append-only JSONL log of registry edits. One JSON object per line: timestamp, actor, task_id, file, old_hash, new_hash, summary. Complementary to git's byte-level history; records the semantic intent of each edit. Loadable as a stream by any consumer.

## 4. The two-layer discipline

The discipline that holds the system together has a few core rules.

### 4.1. One symbol, one definition home

Every symbol has exactly one `owning_document` and exactly one `definition_home` locator. If two documents define the same concept, that is a collision; the registry adjudicates which one is canonical, and the other becomes either an alias or a deprecated predecessor.

### 4.2. One registry identity per object

Symbol IDs are globally unique across the registry. The compiler enforces this at build time (CSR001). Renames produce a new ID and a `superseded_by` edge from the old ID; consumers walk the supersession chain to find the current name.

### 4.3. Cross-document references cite registry entry names

A document that depends on another document's symbol cites the registry ID (`csr.OtherDoc.their_symbol`). It does not cite a version. The registry's `definition_home` field holds the version. When the other document bumps, the registry absorbs the bump; the citing document needs no edit.

### 4.4. The compiler is the only writer of `build/`

Hand-edits to `build/` artifacts are forbidden. The artifacts are regenerated on every compile. The compiler is the single source of truth for the rendered registry state.

### 4.5. Snapshots before edits

Operators (human or agent) snapshot each `.csr` file before editing it: `cp registry/foo.csr registry/foo.csr.bak_pre_<change>`. Edit failures (truncation, malformed YAML, accidental delete) become recoverable. Storage cost is small; recovery value is high.

## 5. Status taxonomy

Symbols and documents progress through a seven-level status ladder:

| Status | Meaning |
|---|---|
| `draft` | Active development; not yet stable. May be incomplete or speculative. |
| `candidate` | Stable enough for cross-doc reference; not yet promoted to canonical. |
| `provisional` | Treated as canonical at one corpus layer; awaiting promotion at the global layer. |
| `canonical` | Authoritative; downstream consumers may depend on it without further checks. |
| `deprecated` | Superseded by a successor; downstream consumers should migrate. Carries `superseded_by` edge. |
| `rejected` | Tried, found wanting; not deployed. Terminal. |
| `deferred` | Set aside; reopening requires a new task. Terminal until reopened. |

Promotion is monotonic along the chain `draft → candidate → provisional → canonical`. Terminal arms are `deprecated`, `rejected`, `deferred`. A canonical symbol that loses canonical status migrates to `deprecated` (with a successor) or back to `candidate` (rare, with rationale).

Canonical promotion requires:

- `source_anchor` present and resolvable.
- `verification.state` in `{argued, tested, formalized, proved}`.
- No unresolved `depends_on` to non-canonical-or-provisional symbols (warning otherwise).

Promotion rules live in `bump-policy.yaml`. The compiler validates the canonical-promotion preconditions above (`CSR007`, `CSR011`); full promotion-legality checking (`CSR016`, illegal status transitions) is specified but deferred; the compiler does not emit it yet.

## 6. Namespaces

A namespace groups symbols owned by one document or one logical cluster. Conventions:

- A new document typically declares a namespace matching its short name.
- Symbols in the namespace use IDs of the form `csr.<Namespace>.<symbol_name>`.
- A namespace can accumulate symbols across multiple `.csr` files (e.g., when one document defines many symbols, they get split across `<Namespace>.csr` and `<Namespace>_extras.csr` for editing convenience). The compiler does not care; the namespace is metadata.
- Cross-namespace collisions (e.g., two documents both wanting `my_symbol`) are resolved by namespace prefixing: `csr.DocA.my_symbol` and `csr.DocB.my_symbol` coexist as distinct registry identities. If the underlying concept is the same, an alias or collision entry records the relationship.

The seed ships with `registry/symbols_core.csr` as a default bucket for general-purpose symbols. Once a namespace accumulates five or more symbols, it benefits from a dedicated `registry/<Namespace>.csr` file for readability and locality of edit.

## 7. Dependencies and relation types

Symbols relate to other symbols through typed edges:

- `depends_on`: symbol A's definition requires symbol B. Forms a DAG; cycles are errors (CSR008).
- `refines`: A is a more specific version of B (B remains canonical at the more general layer).
- `instantiates`: A is a concrete instance of an abstract B.
- `used_by`: inverse of `depends_on`; usually not authored, computed by the compiler.
- `conflicts_with`: A and B disagree; collision entry resolves.
- `equivalent_to`: A and B are different names for the same object (symmetric).
- `contains` / `component_of`: A includes B as a part (inverse pair).
- `xref_only`: weak link; A mentions B without depending on it.

Cycle policy: `depends_on`, `refines`, `instantiates`, `contains` form DAGs. `used_by`, `equivalent_to`, `conflicts_with`, `xref_only` allow cycles. The compiler enforces this distinction.

Status-of-target rules: `depends_on` targets must be at least `candidate`. Depending on `draft` is a warning; depending on `rejected` or `deferred` is an error.

## 8. Notation discipline

Mathematical notation in a multi-author corpus accumulates collisions. CSR ships an optional notation discipline (CSR027) to catch them at build time.

A symbol can declare which letters it claims in a `notation.symbols_used` field. The compiler checks claimed letters against a reserved-letter set: currently the fixed plain capitals `{A, V, G, O, F, K, L}` hardcoded in `tools/csr_compile.py` (`NOTATION_RESERVED_PLAIN_CAPITALS`). Externalising this set to per-project config is a future item. A claim on a reserved letter without an explicit `convention_status` declaration triggers a CSR027 warning. The `convention_status` values are:

- `convention_aligned`: the symbol uses the letter the way mathematical convention already uses it (e.g., `sigma` for a fold-normal-form threshold parameter in bifurcation theory).
- `convention_adapted`: the framework extends the conventional reading with a modifier or scope (e.g., `sigma_snd` for soundness defect; `sigma` is conventional but `_snd` disambiguates).
- `framework_original`: the framework genuinely introduces this letter for a new structure; no convention precedent.
- `aesthetic_override`: the framework deliberately deviates from convention for stylistic reasons; rationale required.
- `divergent_pending_rename`: claim is recognized as a conflict; rename is planned in a future version.

The point is to surface notation collisions at registry-build time so authors can make deliberate choices. CSR does not prescribe a notation; it tracks the choices made and flags conflicts.

## 9. The build pipeline

Each `csr build` run executes:

1. Glob `registry/*.csr` (excludes `.bak*` and other suffixes).
2. Parse each file into AST nodes (symbols, documents, collisions, invariants, aliases, predecessors).
3. Build cross-reference tables.
4. Run the `CSR<NNN>` validation passes (ID uniqueness, dependency resolution and cycles, status taxonomy, source anchors, notation; see §12 for the codes and `tools/csr_compile.py` for the complete set).
5. Emit diagnostics (info / warn / error) to `build/CSR.validation.txt`.
6. Write `build/CSR.lock.json` (the lockfile).
7. Render the markdown views: `CSR.overview.md`, `CSR.symbols.md`, `CSR.documents.md`, `CSR.collisions.md`, `CSR.status.md`, `CSR.wiki.md`.
8. Render the HTML browser: `CSR.registry.html`.
9. Render the Graphviz dependency graph: `CSR.dependencies.dot`.
10. Render the LaTeX consolidated-registry fragments: `consolidated_doc_registry.tex`, `consolidated_symbol_registry.tex`.
11. Render per-document footers: `build/footers/<Namespace>.tex` (for paste-in canonical attribution blocks).

A clean build reports `inputs=N errors=0 warnings=W`. A build with errors does not write a new lockfile; the previous lockfile remains valid.

## 10. Workflow

The intended workflow for adding new content:

1. **Quarantine.** Inbound thoughts, chat fragments, or unstructured proposals land in `quarantine/T-YYYY-MM-DD-NNN.md` with rough classification (proposed kind, namespace, related_symbols, related_documents).

2. **Gluing test.** The operator (human or agent) judges whether the proposal fits the existing apparatus. Three checks:
   - Does it preserve writer discipline (no em-dashes, no contrastive negation, no metacommentary in canonical body)?
   - Does it compose with existing canonical apparatus (or does it duplicate something already canonical)?
   - Does it introduce a new structure that warrants its own registry entry, or is it a refinement of an existing one?

3. **Promote or reject.** If admit, move to `queue/T-YYYY-MM-DD-NNN/intake.md` with the draft registry block. If reject, close in quarantine with rationale.

4. **Register.** Append the symbol or document block to the appropriate `registry/*.csr` file. Snapshot the file first.

5. **Build.** Run `python3 tools/csr.py build`. Confirm `errors=0`. Fix any new warnings or accept them with explicit `convention_status` flags.

6. **Lookup-check.** `csr lookup` the new symbol to confirm it resolves through the pipeline. (A build that says `errors=0` does not guarantee the entry actually parsed; lookup verifies it landed.)

7. **Audit.** Append a JSON line to `csr_edit_log.jsonl` describing the edit (task_id, actor, file, summary).

8. **Close.** Write `queue/T-YYYY-MM-DD-NNN/closure.md` summarizing what was registered.

The workflow is the same for human operators and agent operators. Agent coordination uses a `claimed_by` convention on queue entries to prevent two agents from editing the same registry block concurrently.

## 11. Versioning

Documents carry an explicit `version` field. Symbol locators reference a document version (`csr.MyDoc.my_symbol` definition_home is `csr.document.MyDoc@v1.0#section.2.my_symbol`). When a document bumps:

1. Operator updates the source file (e.g., `MyDoc_v1.tex` becomes `MyDoc_v2.tex`).
2. Update `documents.csr`: bump `version`, add `predecessor_version`, update `source_path`, refresh `last_verified`.
3. Optionally run `python3 tools/bump.py` to walk all symbols owned by the document and update their `definition_home: @v<ver>` locators.
4. Rebuild and verify.

Symbols themselves do not carry independent version numbers; they inherit the owning document's version through the `definition_home` locator. A symbol whose semantic content changes substantially typically gets a new ID (with a `superseded_by` edge from the old).

`bump-policy.yaml` declares per-document bump modes:

- `classify`: the watcher classifies each diff as patch or minor; major requires an operator sentinel file.
- `patch_all`: every change is a patch (no minor auto-promotion).
- `hold`: the watcher does not bump; only compiles.

## 12. Validation diagnostics

The compiler emits diagnostics keyed by `CSR<NNN>` codes. Severity is `info`, `warn`, or `error`. Errors block the lockfile write. Warnings and infos are logged in `build/CSR.validation.txt` and surface in the registry HTML view. Codes are declared in `tools/csr_compile.py`; not all declared codes are wired yet (the compiler implements a subset of the spec).

Common codes:

| Code | Meaning |
|---|---|
| CSR001 | Duplicate symbol ID |
| CSR003 | Unresolved dependency (target not in registry) |
| CSR006 | Invalid status value |
| CSR007 | Canonical symbol missing verification |
| CSR008 | Dependency cycle (on a cycle-error relation) |
| CSR009 | Invalid relation cardinality |
| CSR010 | Active symbol missing its source_anchor, or a `definition_home` that doesn't match the canonical locator format |
| CSR011 | Invalid verification state or missing last_verified |
| CSR017 | Namespace and framework_layer conflated |
| CSR020 | Source-anchor corpus hash missing (run `csr refresh`) |
| CSR021 | Declared `source_path:` but the file is unresolvable on disk |
| CSR023 | Document declared with no source_path |
| CSR025 | Prose contains a cross-document version reference (cite the registry id; the registry holds the version) |
| CSR026 | Symbol block truncation check (catches the Edit-tool-truncation failure mode) |
| CSR027 | Notation collision (claimed letter reserved by convention) |
| CSR029 | Symbol declares a reserved capital absent from its owning source (pseudo-declaration) |
| CSR030 | Plain capital claimed across ≥2 namespaces with no recorded `collision letter_<X>` |

Each code's severity is currently fixed in the compiler; there is no per-project override file yet (an externalised `diagnostic_overrides` config layer is noted for a future spec version).

## 13. Audit trail discipline

The `csr_edit_log.jsonl` audit trail (architecture in §3.5) carries the semantic intent of each edit alongside git's byte history. Discipline: agent operators write a line on every commit-equivalent action; human operators leave at least a one-line summary per session.

## 14. What CSR is not

Useful negations to anchor scope:

- CSR is not a wiki. It does not host content. Documents host content; CSR indexes them.
- CSR is not a build system for documents. PDF compilation, document rendering, and source-prose extraction are downstream consumers of the registry.
- CSR is not a permission system. Access control is out of scope; CSR assumes all operators have read and write access to the registry.
- CSR is not a database. The registry is plaintext files with a custom YAML-like syntax, parsed at build time. Query is by `csr lookup` / `csr deps` / direct lockfile reads.
- CSR is not opinionated about content. The conventions it enforces (status taxonomy, notation discipline, dependency cycles) are about cross-document identity; document content stays out of scope.

## 15. Limits and open questions

The current architecture has known limits:

- **Single-process compile.** The compiler runs in one process. Large corpora (~5000+ symbols) may want a multi-process or incremental build. Not yet implemented.
- **No symbol-level version pinning.** Cross-document citations resolve to the current registry state. For reproducible builds against a frozen registry, the lockfile serves as the snapshot; for citing a frozen symbol version from prose, no first-class support yet.
- **No native multi-language support.** All `.csr` content is parsed as ASCII / UTF-8. Symbol definitions in non-Latin scripts work but are not specifically optimized for.
- **Schema evolution is in-place.** Adding a new optional field is backward-compatible. Renaming or removing fields requires a migration entry in `registry/migration.csr` and a corresponding compiler version bump.

Open architectural questions:

- Whether `framework_layer` (currently a closed enum of six values) should be configurable per-project or remain corpus-architecture-coupled.
- Whether the audit log should be split per-namespace for large corpora, or remain monolithic.
- Whether the `consolidated_doc_registry.tex` LaTeX output should be deprecated in favor of HTML-only rendering.

These are not blockers; they are noted for future spec versions.

## 16. Citation

CSR Conceptual v0: foundational architecture and discipline. Internal specification document. 2026-06-03.

**Successor specs** (implementation and refinement):
- The `CSR_v0.1` spec series (internal to the production instance): foundational spec and incremental refinements (CLI surface, package construct, subcommand promotion).
- `bump-policy.yaml`: per-document bump modes, the one runtime config file currently present. Enums, the reserved-letter set, and diagnostic severities are presently hardcoded in `tools/csr_compile.py`; a `CSR_Schema.yaml` / `CSR_Config.yaml` externalisation is a future item; those files are planned and unwritten.

**Operational guides:**
- `CLAUDE.md`: agent-facing navigation guide for working with the registry.
- `OPERATIONS.md`: daily-flow CLI reference and silent-failure-mode catalog.
- `MIGRATION_HISTORY.md`: log of registry-wide migrations.
