#!/usr/bin/env python3
"""notation_probe.py -- prototype for CSR029/CSR030 (notation source binding).
Extracts math symbols actually used in canonical sources, compares them with
registry notation.symbols_used declarations, and builds a cross-document
letter ledger. Read-only; writes nothing into the registry."""
import re, sys, json, collections, os

GREEK = {"alpha","beta","gamma","delta","epsilon","varepsilon","zeta","eta","theta","vartheta",
"iota","kappa","lambda","mu","nu","xi","pi","rho","varrho","sigma","tau","upsilon","phi","varphi",
"chi","psi","omega","Gamma","Delta","Theta","Lambda","Xi","Pi","Sigma","Upsilon","Phi","Psi","Omega"}
SKIP_CMDS = {"frac","sqrt","sum","prod","int","log","exp","min","max","sup","inf","lim","Pr","mathbb",
"mathcal","mathfrak","mathrm","mathbf","text","textbf","emph","left","right","big","bigl","bigr",
"leq","geq","neq","approx","sim","propto","to","in","subset","subseteq","cup","cap","ker","ll","gg",
"cdot","times","pm","mp","infty","partial","nabla","circ","langle","rangle","lfloor","rfloor",
"lceil","rceil","operatorname","mathrm","quad","qquad","label","ref","eqref","tag","begin","end",
"dot","ddot","hat","widehat","bar","tilde","tightlist","item","textbullet","vert","Vert","flat","sharp",
"prime","star","ast","dagger","ddagger","ess","floor","ceil","var","Var","Cov","ne","equiv","iff",
"Rightarrow","Leftarrow","leftrightarrow","longrightarrow","mapsto","setminus","forall","exists",
"underbrace","overbrace","overline","underline","binom","choose","substack","displaystyle","not","mid"}

def math_segments(tex):
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    segs = []
    segs += re.findall(r"(?<!\\)\$(.+?)(?<!\\)\$", tex, re.S)
    segs += re.findall(r"\\\[(.+?)\\\]", tex, re.S)
    segs += re.findall(r"\\\((.+?)\\\)", tex, re.S)
    return segs

def tokens(seg):
    seg = re.sub(r"\\(?:text|mathrm|operatorname|mathbf)\s*\{[^{}]*\}", " ", seg)
    out = []
    for cmd in re.findall(r"\\([A-Za-z]+)", seg):
        if cmd in GREEK: out.append("\\" + cmd)
        elif cmd in SKIP_CMDS or len(cmd) <= 1: pass
    plain = re.sub(r"\\[A-Za-z]+", " ", seg)
    plain = re.sub(r"_\{[^{}]*\}|\^\{[^{}]*\}", " ", plain)
    for tok in re.findall(r"[A-Za-z]", plain):
        out.append(tok)
    return out

def probe_doc(path):
    tex = open(path, errors="ignore").read()
    c = collections.Counter()
    for seg in math_segments(tex):
        c.update(tokens(seg))
    return c

def registry_scan(regdir):
    ns_syms, ns_vers, total_blocks, nonempty = {}, {}, 0, 0
    letter_hist = collections.Counter()
    for fn in sorted(os.listdir(regdir)):
        if not fn.endswith(".csr"): continue
        txt = open(os.path.join(regdir, fn), errors="ignore").read()
        used = re.findall(r"symbols_used:\s*\[([^\]]*)\]", txt)
        blocks = len(re.findall(r"^symbol ", txt, re.M))
        total_blocks += blocks
        syms = set()
        for u in used:
            items = [s.strip() for s in u.split(",") if s.strip()]
            if items: nonempty += 1
            for it in items:
                syms.add(it); letter_hist[it] += 1
        ns_syms[fn[:-4]] = syms
        ns_vers[fn[:-4]] = collections.Counter(re.findall(r"@v([0-9][\w.]*)", txt))
    return ns_syms, ns_vers, total_blocks, nonempty, letter_hist


def find_csr_root(start):
    """Walk up from start looking for a directory containing registry/."""
    p = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(p, "registry")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent

def registered_sources(regdir):
    """Yield (namespace, source_path) for every document block with a probeable source."""
    out = []
    for fn in sorted(os.listdir(regdir)):
        if not fn.endswith(".csr"):
            continue
        txt = open(os.path.join(regdir, fn), errors="ignore").read()
        for block in re.split(r"^document ", txt, flags=re.M)[1:]:
            ns = re.search(r"^\s+namespace:\s*(\S+)", block, re.M)
            sp = re.search(r"^\s+source_path:\s*(\S+)", block, re.M)
            if ns and sp and sp.group(1).endswith((".tex", ".md")):
                out.append((ns.group(1), sp.group(1)))
    return out

def main():
    import argparse
    ap = argparse.ArgumentParser(description="notation source binding probe (CSR029/CSR030 prototype)")
    ap.add_argument("--root", default="", help="csr root (directory containing registry/); default: walk up from cwd, then from this script")
    ap.add_argument("--corpus-root", default="", help="corpus root for resolving source_path (default: parent of the csr root)")
    ap.add_argument("--min-freq", type=int, default=3, help="minimum in-document frequency for a symbol to count as recurring")
    args = ap.parse_args()

    root = args.root or find_csr_root(os.getcwd()) or find_csr_root(os.path.dirname(os.path.abspath(__file__)))
    if not root:
        print("no registry/ directory found; pass --root"); return 1
    regdir = os.path.join(root, "registry")
    corpus = args.corpus_root or os.path.dirname(os.path.abspath(root))

    # reserved set: prefer the compiler's constant so the probe and CSR027 agree
    try:
        sys.path.insert(0, os.path.join(root, "tools"))
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from csr_compile import NOTATION_RESERVED_PLAIN_CAPITALS as RESERVED
    except Exception:
        RESERVED = ["A", "V", "G", "O", "F", "K", "L"]

    ns_syms, ns_vers, total_blocks, nonempty, letter_hist = registry_scan(regdir)
    print(f"REGISTRY: {total_blocks} symbol blocks; {nonempty} with nonempty symbols_used ({100*nonempty/max(total_blocks,1):.0f}%)")
    print(f"Top letters declared across all symbols_used: {letter_hist.most_common(14)}")
    res = {l: letter_hist.get(l, 0) for l in RESERVED}
    other = sum(v for k, v in letter_hist.items() if k not in res)
    print(f"reserved-set declarations: {sum(res.values())} vs all-other declarations: {other}")
    print()

    doccounts = {}
    for ns, sp in registered_sources(regdir):
        path = os.path.join(corpus, sp)
        if not os.path.exists(path):
            print(f"{ns}: source not on disk, skipped ({sp})"); print(); continue
        c = probe_doc(path)
        doccounts[ns] = c
        top = [f"{s}:{n}" for s, n in c.most_common(18)]
        observed = {s for s in c if c[s] >= args.min_freq}
        print(f"{ns} ({sp}): {len(observed)} distinct symbols (freq>={args.min_freq}); top: {', '.join(top)}")
        if ns in ns_syms and ns_syms[ns]:
            declared = set()
            for d in ns_syms[ns]:
                m = re.fullmatch(r"([A-Za-z])(?:_.*)?", d)
                declared.add("\\" + d if d in GREEK else (m.group(1) if m else d))
            cov = observed & declared
            print(f"   registry declares {sorted(ns_syms[ns])}")
            print(f"   coverage: {len(cov)}/{len(observed)} observed recurring symbols declared ({100*len(cov)/max(len(observed),1):.0f}%)")
        else:
            print("   no symbols_used declarations in this namespace yet")
        print()

    shared = {}
    for ns, c in doccounts.items():
        for s, n in c.items():
            if n >= args.min_freq:
                shared.setdefault(s, {})[ns] = n
    conflicts = {s: row for s, row in shared.items() if len(row) >= 2}
    if conflicts:
        print("CROSS-DOCUMENT LETTER LEDGER (symbols recurring in 2+ documents):")
        for s in sorted(conflicts, key=lambda x: -sum(conflicts[x].values())):
            print(f"  {s:14s} " + "  ".join(f"{k}:{v:4d}" for k, v in conflicts[s].items()))
    return 0

if __name__ == "__main__":
    sys.exit(main())
