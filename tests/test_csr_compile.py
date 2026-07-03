"""
Phase 1A test surfaces.

Three early tests per the implementation order:
  1. B.9 locator format parsing and round-trip
  2. C.6 three-layer hash hierarchy
  3. Collision resolution round-trip through the lockfile

Plus a few §29 failing fixtures: unresolved alias, duplicate id, dependency cycle,
namespace/layer conflation.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Make tools/ importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import csr_compile as csr  # type: ignore


# ----------------------------------------------------------------------------
# Test surface 1: B.9 locator parsing
# ----------------------------------------------------------------------------

def test_locator_parses_canonical_form():
    s = "csr.document.OPG@v0.10#section.6.6.structural_error"
    loc = csr.parse_locator(s)
    assert loc is not None, f"locator failed to parse: {s!r}"
    assert loc.document_id == "csr.document.OPG"
    assert loc.version == "0.10"
    assert loc.section == "6.6"
    assert loc.anchor == "structural_error"


def test_locator_parses_ci_section_15_4():
    s = "csr.document.CI@v19.0#section.15.4.ALG_I_tuple"
    loc = csr.parse_locator(s)
    assert loc is not None
    assert loc.document_id == "csr.document.CI"
    assert loc.version == "19.0"
    assert loc.section == "15.4"
    assert loc.anchor == "ALG_I_tuple"


def test_locator_parses_pfr_v50_7():
    s = "csr.document.PFR_Reference@v50.7#section.LXII.canonical_semantic_registry"
    loc = csr.parse_locator(s)
    # Section "LXII" starts with a letter, so under the strict numeric-section rule
    # this should NOT parse. Verify the rule.
    assert loc is None, "section number must start with a digit per B.9"


def test_locator_round_trip():
    s = "csr.document.OPG@v0.10#section.6.6.structural_error"
    loc = csr.parse_locator(s)
    assert loc is not None
    rendered = loc.render()
    assert rendered == s, f"round-trip mismatch: {s!r} -> {rendered!r}"


def test_locator_rejects_legacy_underscore_form():
    s = "OPG.v0.10.section_6_6"
    loc = csr.parse_locator(s)
    assert loc is None, "legacy underscore form must not parse"


# ----------------------------------------------------------------------------
# Test surface 2: C.6 three-layer hash hierarchy
# ----------------------------------------------------------------------------

def test_definition_hash_changes_on_text_change():
    h1 = csr.compute_definition_hash("a definition")
    h2 = csr.compute_definition_hash("a definition with edit")
    assert h1 != h2
    assert h1.startswith("sha256:") and h2.startswith("sha256:")


def test_definition_hash_stable_under_whitespace():
    h1 = csr.compute_definition_hash("a definition")
    h2 = csr.compute_definition_hash("  a definition  \n")
    assert h1 == h2, "definition_hash must be stable under leading/trailing whitespace"


def test_three_hash_layers_independent():
    """source_hash, section_hash, definition_hash are computed independently
    and tracked in distinct fields."""
    sa = csr.SourceAnchor(
        document="csr.document.OPG",
        version="v0.10",
        section="6.6",
        anchor="structural_error",
        source_hash=csr.sha256_hex("full document text here"),
        section_hash=csr.sha256_hex("section 6.6 text here"),
    )
    def_hash = csr.compute_definition_hash("definition text here")
    # All three hashes are different (different inputs)
    assert sa.source_hash != sa.section_hash
    assert sa.source_hash != def_hash
    assert sa.section_hash != def_hash
    # All three start with sha256:
    assert sa.source_hash.startswith("sha256:")
    assert sa.section_hash.startswith("sha256:")
    assert def_hash.startswith("sha256:")


# ----------------------------------------------------------------------------
# Test surface 3: collision resolution round-trip
# ----------------------------------------------------------------------------

def test_collision_round_trip():
    """Parse a collision, emit lockfile, verify resolution outcome preserved."""
    src = """
collision morphospace_vs_possibility_space:
  id: csr.collision.morphospace_vs_possibility_space
  status: resolved
  resolution: subset_with_added_structure
  entries:
    - csr.OPG.morphospace
    - csr.CI.possibility_space
  resolution_note: "morphospace = cost-geometry-stratified restriction of possibility_space."
  resolved_at: PFR_Reference_v50.7
  owner: OPG
  last_verified: 2026-05-02
"""
    reg, diags = csr.parse(src, file_path="<test>")
    assert len(reg.collisions) == 1
    c = reg.collisions[0]
    assert c.id == "csr.collision.morphospace_vs_possibility_space"
    assert c.resolution == "subset_with_added_structure"
    assert c.resolved_at == "PFR_Reference_v50.7"
    assert c.owner == "OPG"

    lockfile = csr.emit_lockfile(reg)
    assert "csr.collision.morphospace_vs_possibility_space" in lockfile["collisions"]
    cd = lockfile["collisions"]["csr.collision.morphospace_vs_possibility_space"]
    assert cd["resolution"] == "subset_with_added_structure"
    assert cd["entries"] == ["csr.OPG.morphospace", "csr.CI.possibility_space"]


def test_seed_registry_is_blank_and_parses_clean():
    """Seed integrity: every shipped registry stub parses with zero entries
    and zero diagnostics -- the seed must start empty and clean."""
    reg_dir = Path(__file__).resolve().parent.parent / "registry"
    for f in sorted(reg_dir.glob("*.csr")):
        reg, diags = csr.parse(f.read_text(encoding="utf-8"), file_path=str(f))
        assert not diags, f"{f.name}: {diags}"
        assert not reg.symbols and not reg.documents and not reg.collisions \
            and not reg.aliases, f"{f.name} ships non-empty"


# ----------------------------------------------------------------------------
# Failing fixtures from §29
# ----------------------------------------------------------------------------

def test_failing_unresolved_alias():
    src = """
alias retained_skeleton -> csr.OPG.nonexistent_target
"""
    reg, diags = csr.parse(src, file_path="<test>")
    v = csr.Validator(reg)
    v.build_indexes()
    v.validate_fields()
    v.resolve_aliases()
    codes = {d.code for d in v.diagnostics}
    assert "CSR002" in codes, f"expected CSR002, got {codes}"


def test_failing_duplicate_id():
    src = """
symbol foo:
  id: csr.X.foo
  namespace: X
  framework_layer: algebra
  owning_document: csr.document.X
  display_name: foo
  status: candidate

symbol foo_again:
  id: csr.X.foo
  namespace: X
  framework_layer: algebra
  owning_document: csr.document.X
  display_name: foo_again
  status: candidate
"""
    reg, _ = csr.parse(src, file_path="<test>")
    v = csr.Validator(reg)
    v.build_indexes()
    codes = {d.code for d in v.diagnostics}
    assert "CSR001" in codes


def test_failing_namespace_layer_conflation():
    src = """
symbol bad_layer:
  id: csr.OPG.bad_layer
  namespace: OPG
  framework_layer: OPG
  owning_document: csr.document.OPG
  display_name: bad_layer
  status: candidate
"""
    reg, _ = csr.parse(src, file_path="<test>")
    v = csr.Validator(reg)
    v.build_indexes()
    v.validate_fields()
    codes = {d.code for d in v.diagnostics}
    assert "CSR017" in codes


def test_failing_dependency_cycle():
    src = """
symbol a:
  id: csr.X.a
  namespace: X
  framework_layer: algebra
  owning_document: csr.document.X
  display_name: a
  status: candidate
  definition_home: csr.document.X@v0.1#section.1.a
  definition: "a"
  source_anchor:
    document: csr.document.X
    version: v0.1
    section: "1"
    anchor: a
    source_hash: sha256:x
    section_hash: sha256:y
  verification:
    state: argued
    method: prose
    last_verified: 2026-05-02
  relations:
    depends_on:
      - csr.X.b

symbol b:
  id: csr.X.b
  namespace: X
  framework_layer: algebra
  owning_document: csr.document.X
  display_name: b
  status: candidate
  definition_home: csr.document.X@v0.1#section.1.b
  definition: "b"
  source_anchor:
    document: csr.document.X
    version: v0.1
    section: "1"
    anchor: b
    source_hash: sha256:x
    section_hash: sha256:z
  verification:
    state: argued
    method: prose
    last_verified: 2026-05-02
  relations:
    depends_on:
      - csr.X.a
"""
    reg, _ = csr.parse(src, file_path="<test>")
    v = csr.Validator(reg)
    v.build_indexes()
    v.validate_cycles()
    codes = {d.code for d in v.diagnostics}
    assert "CSR008" in codes, f"expected CSR008, got {codes}"


# ----------------------------------------------------------------------------
# End-to-end: Batch 1 seed compiles
# ----------------------------------------------------------------------------

def test_batch_1_seed_compiles_clean():
    """The §C.16 Batch 1 seed must compile with zero errors."""
    registry_dir = ROOT / "registry"
    inputs = sorted(registry_dir.glob("*.csr"))
    # Skip CSR.csr (it just has imports; we feed the leaf files)
    inputs = [p for p in inputs if p.name != "CSR.csr"]
    assert inputs, "no .csr files found in registry/"
    with tempfile.TemporaryDirectory() as tmp:
        errors, warnings = csr.compile_registry(inputs, Path(tmp))
        if errors:
            # Print validation report for debugging
            report = (Path(tmp) / "CSR.validation.txt").read_text()
            print(report)
        assert errors == 0, f"Batch 1 should compile clean; got {errors} errors"


def test_lockfile_is_deterministic():
    """Two compiles of the same input produce byte-identical lockfiles."""
    registry_dir = ROOT / "registry"
    inputs = sorted(p for p in registry_dir.glob("*.csr") if p.name != "CSR.csr")
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        csr.compile_registry(inputs, Path(tmp1))
        csr.compile_registry(inputs, Path(tmp2))
        a = (Path(tmp1) / "CSR.lock.json").read_bytes()
        b = (Path(tmp2) / "CSR.lock.json").read_bytes()
        assert a == b, "lockfile must be byte-deterministic"


# ----------------------------------------------------------------------------
def test_locator_admits_letter_suffix_section():
    """Sutra 5b style: section is digit+letter, not pure numeric."""
    s = "csr.document.Koopman_PLVS_v0@v0#section.5b.reversibility_unitarity"
    loc = csr.parse_locator(s)
    assert loc is not None, f"failed to parse: {s!r}"
    assert loc.section == "5b"
    assert loc.anchor == "reversibility_unitarity"


def test_locator_admits_symbolic_section():
    """Framework notes may use symbolic section names like 'preamble' or 'final'."""
    for s, expected in [
        ("csr.document.Koopman_PLVS_v0@v0#section.preamble.system_compression", "preamble"),
        ("csr.document.Koopman_PLVS_v0@v0#section.final.invariant", "final"),
    ]:
        loc = csr.parse_locator(s)
        assert loc is not None, f"failed to parse: {s!r}"
        assert loc.section == expected


# Autolink sanitation
# ----------------------------------------------------------------------------

def test_autolink_sanitation_strips_markdown_link():
    text = "depends_on: [csr.CI](http://csr.CI).correction_load"
    cleaned, count = csr.preprocess_autolinks(text)
    assert count == 1
    assert cleaned == "depends_on: csr.CI.correction_load"


def test_autolink_sanitation_handles_multiple():
    text = "[csr.CI](http://csr.CI).a and [csr.OPG](http://csr.OPG).b"
    cleaned, count = csr.preprocess_autolinks(text)
    assert count == 2
    assert cleaned == "csr.CI.a and csr.OPG.b"


if __name__ == "__main__":
    # Simple test runner without pytest dependency
    import traceback
    test_funcs = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for tf in test_funcs:
        try:
            tf()
            print(f"PASS  {tf.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {tf.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {tf.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
