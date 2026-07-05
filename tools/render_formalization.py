#!/usr/bin/env python3
"""render_formalization.py - Generate per-namespace LaTeX canon fragments from CSR.

Renderer v0.2: Adds math-mode auto-wrap, schema-as-environment, compact status.

CSR-spine architecture: this renderer is the bridge from registry (CSR symbols)
to documents (LaTeX fragments). One-way: CSR -> render -> document.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CSR_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = CSR_ROOT / "registry"
BUILD_DIR = CSR_ROOT / "build"
FORMALIZATION_OUT = BUILD_DIR / "formalization"

# ---------------------------------------------------------------------------
# Type -> LaTeX environment mapping
# ---------------------------------------------------------------------------
# All canonical CSR types map to a LaTeX theorem-style environment.
# The (env, display_name_optional) pair: env is the LaTeX environment name;
# display_name_optional indicates whether the symbol's display_name should
# appear in the [optional] brackets of the environment.
TYPE_TO_ENV = {
    "definition":       ("definition", True),
    "structure":        ("definition", True),
    "axiom":            ("axiom",      True),
    "theorem":          ("theorem",    True),
    "proposition":      ("proposition", True),
    "lemma":            ("lemma",      True),
    "corollary":        ("corollary",  True),
    "conjecture":       ("conjecture", True),
    "predicate":        ("definition", True),
    "concept":          ("definition", True),
    "operator":         ("definition", True),
    "schema":           ("schema",     False),
    "diagnostic":       ("diagnostic", False),
    "candidate":        ("candidate",  False),
    "empirical_anchor": ("anchor",     False),
    "method":           ("method",     False),
}

# Theorem environment declarations to include in any preview wrapper.
THEOREM_DECLARATIONS = r"""\theoremstyle{definition}
\newtheorem{definition}{Definition}[section]
\newtheorem*{axiom}{Axiom}

\theoremstyle{plain}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{proposition}[theorem]{Proposition}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{conjecture}[theorem]{Conjecture}

\theoremstyle{remark}
\newtheorem*{schema}{Schema}
\newtheorem*{diagnostic}{Diagnostic}
\newtheorem*{candidate}{Candidate}
\newtheorem*{anchor}{Empirical anchor}
\newtheorem*{method}{Method}
"""

# ---------------------------------------------------------------------------
# Math auto-wrap heuristics
# ---------------------------------------------------------------------------
# Greek tokens to convert: sqcup, varphi, epsilon, kappa, mu, delta, alpha,
# beta, gamma, lambda, tau, sigma, phi, rho, theta, omega, nu, xi, pi, zeta,
# chi, eta, iota, psi.
GREEK_TOKENS = [
    "sqcup", "sqcap", "varphi", "varepsilon", "vartheta",
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma",
    "tau", "phi", "chi", "psi", "omega", "Gamma", "Delta", "Theta",
    "Lambda", "Xi", "Pi", "Sigma", "Phi", "Psi", "Omega", "Upsilon",
]

# Operator/relation tokens
ASCII_RELATIONS = {
    "<=": r"\le",
    ">=": r"\ge",
    "!=": r"\ne",
    "->": r"\to",
    "<-": r"\leftarrow",
    "<->": r"\leftrightarrow",
    "==>": r"\Longrightarrow",
    "<==": r"\Longleftarrow",
    "<=>": r"\iff",
}


def parse_csr_file(path: Path) -> list:
    text = path.read_text(encoding="utf-8", errors="ignore")
    records = []
    block_re = re.compile(r"^(symbol|document)\s+(\S+):\s*$", re.MULTILINE)
    matches = list(block_re.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1) != "symbol":
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        record = parse_block(block, m.group(2))
        if record:
            records.append(record)
    return records


def parse_block(block: str, name: str) -> dict:
    record = {"_symbol_name": name}
    lines = block.splitlines()
    cur_key = None
    for line in lines:
        if not line.strip():
            continue
        m = re.match(r"^  ([a-z_]+):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            cur_key = key
            if value:
                record[key] = strip_quotes(value)
            else:
                record[key] = None
            continue
        m = re.match(r"^    ([a-z_]+):\s*(.*)$", line)
        if m and cur_key:
            sub_key, sub_value = m.group(1), m.group(2).strip()
            if record.get(cur_key) is None or not isinstance(record.get(cur_key), dict):
                record[cur_key] = {}
            record[cur_key][sub_key] = strip_quotes(sub_value)
            continue
        m = re.match(r"^    - (.*)$", line)
        if m and cur_key:
            if not isinstance(record.get(cur_key), list):
                record[cur_key] = []
            record[cur_key].append(strip_quotes(m.group(1).strip()))
            continue
    return record


def strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


SECTION_RE = re.compile(r"#section\.(\d+(?:\.\d+)*)\.(.+)$")


def sort_key(record):
    home = record.get("definition_home", "")
    m = SECTION_RE.search(home)
    if not m:
        return ((999,), "", record.get("_symbol_name", ""))
    section_parts = tuple(int(p) for p in m.group(1).split("."))
    anchor = m.group(2)
    return (section_parts, anchor, record.get("_symbol_name", ""))


# ---------------------------------------------------------------------------
# Math auto-wrap: detect ASCII math conventions and wrap in $...$
# ---------------------------------------------------------------------------
def auto_wrap_math(seg: str) -> str:
    """Wrap ASCII math conventions in $...$. Conservative heuristic.

    Patterns wrapped:
    - Greek tokens followed optionally by _subscript: sqcup, varphi_L, kappa_R
    - Identifier subscripts: X_Y, X_{abc}, R_{adm}
    - ASCII relations: <=, >=, !=, ->, <->
    - Math fragments: c_R(x,x)=0 style sequences

    The text must already have $...$ spans protected upstream; this only
    processes text-mode segments.
    """
    # 1. Replace Greek tokens with optional subscript
    greek_re = re.compile(r"\b(" + "|".join(GREEK_TOKENS) + r")(_[A-Za-z0-9]+|_\{[^}]+\})?\b")

    def greek_repl(m):
        name = m.group(1)
        sub = m.group(2) or ""
        # Don't double-escape if subscript has _
        sub_tex = sub.replace("_", "_")  # keep _ as-is inside math
        return f"$\\{name}{sub_tex}$"

    seg = greek_re.sub(greek_repl, seg)

    # 2. (disabled): uppercase subscript autowrap was too aggressive,
    # creating pseudo-math like $ALG-I_global$ that breaks compilation.
    # The right fix is the CSR026 author-side rule requiring math to be
    # wrapped in $...$ in the CSR definition itself.

    # 3. ASCII relations
    for ascii_op, tex_op in sorted(ASCII_RELATIONS.items(), key=lambda x: -len(x[0])):
        # Escape backslashes in replacement for re.sub
        seg = re.sub(r"(?<!\\)" + re.escape(ascii_op), lambda m, t=tex_op: f"${t}$", seg)

    # 4. After math-wrapping, escape remaining bare underscores
    # but DON'T escape inside the $...$ spans we just created
    # Split by $-spans and only escape underscores in non-math segments
    parts = re.split(r"(\$[^$]+\$)", seg)
    for i in range(0, len(parts), 2):
        # Only even indices are non-math
        parts[i] = re.sub(r"(?<!\\)_", r"\\_", parts[i])
        # Escape ampersands that aren't already escaped
        parts[i] = re.sub(r"(?<!\\)&", r"\\&", parts[i])
    return "".join(parts)


def latex_escape(s: str) -> str:
    """Escape ASCII-math content in CSR definition prose.

    Splits on existing $...$ spans (which authors marked as math).
    Inside math spans: leave as-is.
    Outside math spans: auto-wrap Greek tokens / subscripts / operators,
    then escape bare underscores and ampersands.
    """
    if not s:
        return s

    # Split into segments: alternating text and math ($...$)
    out_parts = []
    i = 0
    buf = []
    while i < len(s):
        ch = s[i]
        if ch == "$" and (i == 0 or s[i - 1] != "\\"):
            if buf:
                out_parts.append(("text", "".join(buf)))
                buf = []
            # Find matching $
            j = i + 1
            while j < len(s):
                if s[j] == "$" and s[j - 1] != "\\":
                    break
                j += 1
            if j < len(s):
                out_parts.append(("math", s[i:j + 1]))
                i = j + 1
                continue
            else:
                buf.append(ch)
                i += 1
                continue
        buf.append(ch)
        i += 1
    if buf:
        out_parts.append(("text", "".join(buf)))

    # Process text segments through auto_wrap_math; leave math alone
    result = []
    for kind, seg in out_parts:
        if kind == "math":
            result.append(seg)
        else:
            result.append(auto_wrap_math(seg))
    return "".join(result)


def escape_id(s: str) -> str:
    """Escape underscores in display_names and CSR ids for LaTeX."""
    return s.replace("\\_", "\x00").replace("_", "\\_").replace("\x00", "\\_")


def make_label(sym_id: str) -> str:
    parts = sym_id.split(".")
    if parts and parts[0] == "csr":
        parts = parts[1:]
    return "csr:" + ":".join(parts)


# ---------------------------------------------------------------------------
# Compact status footer
# ---------------------------------------------------------------------------
DEFAULT_STATE = "argued"
DEFAULT_METHOD = "prose"


def render_status_footer(record):
    """Render a compact status footer. Only show non-default fields."""
    status = record.get("status", "candidate")
    verification = record.get("verification") or {}
    if not isinstance(verification, dict):
        verification = {}
    proof_state = verification.get("state", DEFAULT_STATE)
    method = verification.get("method", DEFAULT_METHOD)
    depends_on = record.get("depends_on") or []

    parts = [status]
    if proof_state != DEFAULT_STATE:
        parts.append(proof_state)
    if method != DEFAULT_METHOD:
        parts.append(method)
    line = "; ".join(parts)
    if depends_on:
        dep_refs = ", ".join(f"\\texttt{{{escape_id(d.split('.')[-1])}}}" for d in depends_on[:4])
        if len(depends_on) > 4:
            dep_refs += f" (+{len(depends_on) - 4})"
        line += "; deps: " + dep_refs
    return "\\hfill{\\footnotesize\\textit{" + line + "}}\n"


def render_symbol(record):
    sym_id = record.get("id", "")
    display_name = record.get("display_name", record.get("_symbol_name", ""))
    sym_type = record.get("type", "schema")
    definition = record.get("definition", "")

    env_info = TYPE_TO_ENV.get(sym_type, ("definition", True))
    env, use_display = env_info
    label = make_label(sym_id)
    display_safe = escape_id(display_name)

    out = []
    out.append(f"% {sym_id} ({sym_type})")

    if use_display:
        out.append(f"\\begin{{{env}}}[{display_safe}]\\label{{{label}}}")
    else:
        out.append(f"\\begin{{{env}}}\\label{{{label}}}")
    out.append(latex_escape(definition))
    out.append(f"\\end{{{env}}}")
    out.append(render_status_footer(record).rstrip())
    out.append("")
    return "\n".join(out)


def render_namespace(namespace, records):
    ns_records = [r for r in records if r.get("namespace") == namespace]
    ns_records.sort(key=sort_key)
    if not ns_records:
        return f"% No symbols found in namespace {namespace}\n"
    out = [
        f"% ============================================================",
        f"%  CSR canon for namespace {namespace}",
        f"%  Auto-generated by csr/tools/render_formalization.py v0.2",
        f"%  Symbol count: {len(ns_records)}",
        f"%  DO NOT EDIT - modify CSR symbol records instead",
        f"% ============================================================",
        "",
    ]
    for record in ns_records:
        out.append(render_symbol(record))
    return "\n".join(out)


def main(argv):
    target_namespaces = argv[1:] if len(argv) > 1 else None
    FORMALIZATION_OUT.mkdir(parents=True, exist_ok=True)

    # Write theorem-declarations include
    decl_path = FORMALIZATION_OUT / "_theorem_decls.tex"
    decl_path.write_text(THEOREM_DECLARATIONS, encoding="utf-8")

    all_records = []
    for csr_file in sorted(REGISTRY_DIR.glob("*.csr")):
        all_records.extend(parse_csr_file(csr_file))

    if target_namespaces is None:
        namespaces = sorted({r.get("namespace") for r in all_records if r.get("namespace")})
    else:
        namespaces = target_namespaces

    for ns in namespaces:
        fragment = render_namespace(ns, all_records)
        out_path = FORMALIZATION_OUT / f"{ns}_canon.tex"
        out_path.write_text(fragment, encoding="utf-8")
        sym_count = sum(1 for r in all_records if r.get("namespace") == ns)
        print(f"  {ns}_canon.tex  ({sym_count} symbols)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
