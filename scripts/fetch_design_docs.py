"""Fetch design documents: Go proposals, Rust RFCs and Kubernetes enhancement proposals.

    python3 -I scripts/fetch_design_docs.py /Volumes/Rebuildable/readcost-ref/broad/design-docs
    PYTHONPATH=src python3 scripts/eval_more.py /Volumes/Rebuildable/readcost-ref/broad

Lists each repository's files with the GitHub tree API (``gh api``, so it
needs a GitHub login) and reads the chosen files raw from
raw.githubusercontent.com at the listed commit, a quarter second apart:

- ``go``: every ``design/*.md`` in golang/proposal (BSD-3-Clause).
- ``rust``: ``--rust`` RFCs from ``text/*.md`` in rust-lang/rfcs, evenly
  spaced by RFC number so that every era is represented; the ``Start Date``
  in each header is recorded (Apache-2.0 or MIT, at the reader's option).
- ``kubernetes``: a seeded random ``--keps`` of the ``keps/sig-*/NNNN-*/README.md``
  files in kubernetes/enhancements (Apache-2.0).

Before writing, HTML comments (the KEP template's instructions), the
generated table of contents between ``<!-- toc -->`` markers, checklist lines
(``- [ ]``) and the metadata lines at the top (authors, dates, tracking links)
are removed; code blocks stay for readcost's Markdown reader to skip. A
document is kept when it has at least 150 words of prose outside code.
Category ``design-doc``, source ``go``, ``rust`` or ``kubernetes``. The text
stays under the output directory, outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
REPOS = {"go": ("golang/proposal", "master", r"design/[^/]+\.md", "BSD-3-Clause"),
         "rust": ("rust-lang/rfcs", "main", r"text/\d+-[^/]+\.md", "Apache-2.0 OR MIT"),
         "kubernetes": ("kubernetes/enhancements", "master", r"keps/sig-[^/]+/\d+-[^/]+/README\.md", "Apache-2.0")}
MIN_WORDS = 150
GAP = 0.25
_last = 0.0
META = re.compile(r"^\s*[-*]?\s*(authors?|author\(s\)|last updated|discussion at|start date|feature name|"
                  r"rfc pr|rust issue|status|owners?|creation date)\s*[:：]", re.IGNORECASE)


def gh(args: list[str]) -> str:
    return subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}", *args], check=True,
                          capture_output=True, text=True, timeout=120).stdout


def raw(repo: str, sha: str, path: str) -> str | None:
    global _last
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(path)}"
    for attempt in range(3):
        wait = _last + GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    return None


def clean_design_doc(md: str) -> str:
    """Drop HTML comments, a generated table of contents, checklists and header metadata lines."""
    md = re.sub(r"(?s)<!--\s*toc\s*-->.*?<!--\s*/toc\s*-->", "", md)
    md = re.sub(r"(?s)<!--.*?-->", "", md)
    out, in_code = [], False
    for line in md.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_code = not in_code
        if not in_code and (re.match(r"^\s*[-*]\s+\[[ xX]\]", line) or META.match(line)):
            continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def prose_words(md: str) -> int:
    md = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", md)
    md = re.sub(r"`[^`]*`", " ", md)
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", md))


def start_date(md: str) -> str | None:
    m = re.search(r"start date\s*:\s*\(?\s*(\d{4}-\d{2}-\d{2})", md, re.IGNORECASE)
    return m.group(1) if m else None


def evenly(items: list, n: int) -> list:
    """``n`` items spaced evenly through ``items`` (all of them when there are fewer)."""
    if len(items) <= n:
        return list(items)
    return [items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--rust", type=int, default=150)
    ap.add_argument("--keps", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries, failures = [], []
    for source, (repo, branch, pattern, licence) in REPOS.items():
        sha = json.loads(gh([f"repos/{repo}/commits/{branch}"]))["sha"]
        tree = json.loads(gh([f"repos/{repo}/git/trees/{sha}?recursive=1"]))
        paths = sorted(t["path"] for t in tree["tree"] if t["type"] == "blob" and re.fullmatch(pattern, t["path"]))
        if source == "rust":
            paths = evenly(sorted(paths, key=lambda p: int(p.split("/")[1].split("-")[0])), args.rust)
        elif source == "kubernetes":
            paths = sorted(rng.sample(paths, min(args.keps, len(paths))))
        kept = 0
        for p in paths:
            text = raw(repo, sha, p)
            if text is None:
                failures.append({"path": p, "source": source, "reason": "fetch failed"})
                continue
            cleaned = clean_design_doc(text)
            if prose_words(cleaned) < MIN_WORDS:
                failures.append({"path": p, "source": source, "reason": f"under {MIN_WORDS} words of prose"})
                continue
            name = p.split("/")[-2] if source == "kubernetes" else Path(p).stem
            rel = f"{source}/{name}.md"
            (out / source).mkdir(exist_ok=True, mode=0o700)
            (out / rel).write_text(cleaned)
            e = {"id": f"design-doc/{source}/{name}", "category": "design-doc", "source": source,
                 "author": "", "url": f"https://github.com/{repo}/blob/{sha}/{p}", "path": rel,
                 "format": "markdown", "license": licence, "fetched_at": now,
                 "via": f"gh api repos/{repo}/git/trees/{sha}; raw {p}",
                 "sha256": hashlib.sha256(cleaned.encode()).hexdigest(), "bytes": len(cleaned.encode())}
            if source == "rust":
                e |= {"number": int(name.split("-")[0]), "start_date": start_date(text)}
            entries.append(e)
            kept += 1
        print(f"{source}: {kept} kept of {len(paths)} at {sha[:10]}", file=sys.stderr)
    (out / "manifest.json").write_text(json.dumps(
        {"description": "Go proposals, Rust RFCs and Kubernetes KEPs; see scripts/fetch_design_docs.py",
         "generated_at": now, "seed": args.seed, "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "design docs;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
