#!/usr/bin/env python3
"""compile_pdfs.py - Compile a PDF from each registered .tex source and point CSR at it.

For every document in the registry whose source_path is a .tex file, this tool:
  1. compiles the .tex to a sibling .pdf with xelatex (run from the source dir so
     relative includes resolve), two passes, and cleans aux files
  2. inserts or updates a pdf_path: line in the owning document block so the
     registry browser's PDF buttons resolve to the compiled file

Usage (from the directory containing csr/, or pass --corpus-root):
    python3 csr/tools/compile_pdfs.py                 # compile missing/stale, link all
    python3 csr/tools/compile_pdfs.py --force          # recompile everything
    python3 csr/tools/compile_pdfs.py --link-only      # no compile; just set pdf_path where a PDF exists
    python3 csr/tools/compile_pdfs.py --only mydoc     # substring filter on source_path
    python3 csr/tools/compile_pdfs.py --asset-dir assets --asset-dir figures   # extra TEXINPUTS dirs

Requires xelatex on PATH. Registry-driven: the document list comes from
registry/*.csr, and source_path is resolved against the corpus root
(default: the parent of the directory containing registry/).
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys, glob
from pathlib import Path

CSR_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = CSR_ROOT / "registry"
CORPUS_ROOT = CSR_ROOT.parent          # overridable via --corpus-root
ASSET_DIRS: list = []                  # extra TEXINPUTS dirs, via --asset-dir
TIMEOUT = 90


def parse_docs():
    """Yield (csr_file, doc_id, source_path) for every document block with a source_path."""
    out = []
    for f in sorted(glob.glob(str(REGISTRY / "*.csr"))):
        lines = Path(f).read_text(encoding="utf-8").split("\n")
        cur_id = None
        for ln in lines:
            m = re.match(r"^\s+id:\s*(csr\.document\.\S+)", ln)
            if m:
                cur_id = m.group(1)
            ms = re.match(r"^\s+source_path:\s*(\S+)", ln)
            if ms and cur_id:
                out.append((f, cur_id, ms.group(1)))
                cur_id = None
    return out


def compile_one(source_path: str, force: bool):
    """Compile a .tex (corpus-root-relative) to a sibling .pdf. Returns (ok, message)."""
    tex = CORPUS_ROOT / source_path
    if not tex.exists():
        return False, "tex missing"
    pdf = tex.with_suffix(".pdf")
    if pdf.exists() and not force and pdf.stat().st_mtime >= tex.stat().st_mtime:
        return True, "up-to-date"
    env = dict(os.environ)
    env["TEXINPUTS"] = ".:" + ":".join(str(CORPUS_ROOT / d) for d in ASSET_DIRS) + ":"
    workdir = tex.parent
    for _ in range(2):  # two passes for refs/toc
        try:
            r = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                cwd=str(workdir), env=env, capture_output=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return False, "timeout"
        ok = (workdir / (tex.stem + ".pdf")).exists() and r.returncode == 0
        if not ok:
            for line in r.stdout.decode("utf-8", "ignore").splitlines():
                if line.startswith("!") or "Fatal" in line:
                    return False, line.strip()
            return False, "compile error"
    for ext in (".aux", ".log", ".out", ".toc"):
        p = workdir / (tex.stem + ext)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    return True, "compiled"


def set_pdf_path(csr_file: str, doc_id: str, pdf_rel: str) -> bool:
    """Insert/update a pdf_path: line right after the doc's source_path line (by id)."""
    lines = Path(csr_file).read_text(encoding="utf-8").split("\n")
    in_block = False
    for i, ln in enumerate(lines):
        if re.match(r"^\s+id:\s*" + re.escape(doc_id) + r"\s*$", ln):
            in_block = True
        elif re.match(r"^document \S+:", ln):
            in_block = False
        if in_block and re.match(r"^(\s+)source_path:", ln):
            indent = re.match(r"^(\s*)", ln).group(1)
            if i + 1 < len(lines) and re.match(r"^\s+pdf_path:", lines[i + 1]):
                lines[i + 1] = f"{indent}pdf_path: {pdf_rel}"
            else:
                lines.insert(i + 1, f"{indent}pdf_path: {pdf_rel}")
            Path(csr_file).write_text("\n".join(lines), encoding="utf-8")
            return True
    return False


def link_pdf_by_source(source_rel: str, pdf_rel: str) -> bool:
    """Find the document block (in any registry file) whose source_path == source_rel
    and insert/update a pdf_path: line right after it. Keyed on source_path so callers
    that don't know the owning .csr file (e.g. watch.py) can link too. Returns True if set."""
    for f in sorted(glob.glob(str(REGISTRY / "*.csr"))):
        lines = Path(f).read_text(encoding="utf-8").split("\n")
        for i, ln in enumerate(lines):
            m = re.match(r"^(\s+)source_path:\s*(\S+)\s*$", ln)
            if m and m.group(2) == source_rel:
                indent = m.group(1)
                if i + 1 < len(lines) and re.match(r"^\s+pdf_path:", lines[i + 1]):
                    lines[i + 1] = f"{indent}pdf_path: {pdf_rel}"
                else:
                    lines.insert(i + 1, f"{indent}pdf_path: {pdf_rel}")
                Path(f).write_text("\n".join(lines), encoding="utf-8")
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="recompile even if PDF is current")
    ap.add_argument("--link-only", action="store_true", help="don't compile; only set pdf_path where a PDF already exists")
    ap.add_argument("--only", default="", help="substring filter on source_path")
    ap.add_argument("--corpus-root", default="", help="corpus root that source_path values are relative to (default: parent of the csr directory)")
    ap.add_argument("--asset-dir", action="append", default=[], help="extra corpus-root-relative dir for TEXINPUTS (repeatable)")
    args = ap.parse_args()
    global CORPUS_ROOT, ASSET_DIRS
    if args.corpus_root:
        CORPUS_ROOT = Path(args.corpus_root).resolve()
    ASSET_DIRS = list(args.asset_dir)

    docs = [d for d in parse_docs() if d[2].endswith(".tex") and args.only in d[2]]
    print(f"[compile_pdfs] {len(docs)} .tex-sourced documents")
    compiled = linked = skipped = failed = 0
    failures = []
    for csr_file, doc_id, sp in docs:
        pdf_rel = sp[:-4] + ".pdf"
        pdf_abs = CORPUS_ROOT / pdf_rel
        if args.link_only:
            ok, msg = (pdf_abs.exists(), "exists" if pdf_abs.exists() else "no pdf")
        else:
            ok, msg = compile_one(sp, args.force)
        if ok:
            if msg == "compiled":
                compiled += 1
            else:
                skipped += 1
            if set_pdf_path(csr_file, doc_id, pdf_rel):
                linked += 1
        else:
            failed += 1
            failures.append((doc_id.replace("csr.document.", ""), msg))
        print(f"  {'OK ' if ok else 'XX '} {doc_id.replace('csr.document.','')[:40]:40s} {msg}")
    print(f"\n[compile_pdfs] compiled={compiled} up-to-date={skipped} linked(pdf_path set)={linked} failed={failed}")
    if failures:
        print("[compile_pdfs] failures (need attention):")
        for d, m in failures:
            print(f"    {d}: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
