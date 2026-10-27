"""Fetch manual pages from OpenBSD and the Linux man-pages project and keep their DESCRIPTION sections.

    python3 -I scripts/fetch_man_pages.py /Volumes/Rebuildable/readcost-ref/broad/man-pages
    PYTHONPATH=src python3 scripts/eval_more.py /Volumes/Rebuildable/readcost-ref/broad

- ``openbsd``: the openbsd/src mirror on GitHub. Lists ``bin``, ``usr.bin``
  (section 1) and ``lib/libc`` (sections 2 and 3) with the tree API (``gh
  api``, so it needs a GitHub login), draws a seeded random ``--per-section``
  pages per section, and reads each raw at the listed commit, a quarter second
  apart.
- ``linux``: the newest man-pages release tarball from cdn.kernel.org,
  downloaded once into ``linux-src/`` under the output directory and unpacked
  there with tarfile's ``data`` filter; ``--per-section`` pages per section 1,
  2 and 3, seeded, leaving out ``.so`` redirections.

Each page is rendered with the system ``mandoc -T utf8 -O width=1000`` piped
through ``col -b``; the DESCRIPTION section is kept, with wrapped lines joined
into paragraphs, when it has at least 150 words. Licences are read per file:
the SPDX identifier when there is one, otherwise the copyright comment is
classified as ISC, BSD (2-, 3- or 4-clause by its numbered conditions) or
public domain; pages whose licence cannot be classified are skipped. Category
``man-page``, source ``<openbsd|linux>/<section>``. The text stays under the
output directory, outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
OPENBSD = "openbsd/src"
KERNEL = "https://cdn.kernel.org/pub/linux/docs/man-pages/"
SECTIONS = ("1", "2", "3")
MIN_WORDS = 150
GAP = 0.25
_last = 0.0


def gh(args: list[str]) -> str:
    return subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}", *args], check=True,
                          capture_output=True, text=True, timeout=300).stdout


def get(url: str, timeout: int = 120) -> bytes | None:
    global _last
    for attempt in range(3):
        wait = _last + GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                        timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    return None


def page_licence(src: str) -> str | None:
    """The licence of a roff page from its SPDX line or its copyright comment, else None."""
    if m := re.search(r"SPDX-License-Identifier:\s*(\S[^\n]*)", src):
        return m.group(1).strip()
    comments = " ".join(re.findall(r'^\.\\"(.*)$', src, re.MULTILINE))
    comments = re.sub(r"\s+", " ", comments).lower()
    if "permission to use, copy, modify, and" in comments and "distribute this software" in comments:
        return "ISC"
    if "redistribution and use in source and binary forms" in comments:
        if "advertising materials" in comments:
            return "BSD-4-Clause"
        return "BSD-3-Clause" if re.search(r"\b3\. ", comments) else "BSD-2-Clause"
    if "public domain" in comments:
        return "public domain"
    return None


def render(src: bytes) -> str:
    """The page as plain text, unwrapped, from mandoc and col -b."""
    out = subprocess.run(["mandoc", "-T", "utf8", "-O", "width=1000"], input=src, capture_output=True,
                         timeout=60, check=False).stdout
    return subprocess.run(["col", "-b"], input=out, capture_output=True, timeout=60, check=True).stdout.decode(
        "utf-8", errors="replace")


def description(rendered: str) -> str:
    """The DESCRIPTION section of rendered text, as paragraphs separated by blank lines."""
    lines = rendered.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "DESCRIPTION" and not ln.startswith(" "))
    except StopIteration:
        return ""
    paras, cur = [], []
    for ln in lines[start + 1:]:
        if ln and not ln[0].isspace():
            break
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras) + "\n" if paras else ""


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))


def openbsd_candidates(rng: random.Random, n: int) -> tuple[str, dict[str, list[str]]]:
    sha = json.loads(gh([f"repos/{OPENBSD}/commits/master"]))["sha"]
    top = {x["name"]: x["sha"] for x in json.loads(gh([f"repos/{OPENBSD}/contents/?ref={sha}"]))}
    lib = {x["name"]: x["sha"] for x in json.loads(gh([f"repos/{OPENBSD}/contents/lib?ref={sha}"]))}
    files: list[str] = []
    for prefix, tsha in (("bin", top["bin"]), ("usr.bin", top["usr.bin"]), ("lib/libc", lib["libc"])):
        tree = json.loads(gh([f"repos/{OPENBSD}/git/trees/{tsha}?recursive=1"]))
        files += [f"{prefix}/{t['path']}" for t in tree["tree"] if t["type"] == "blob"]
    by_sec = {s: sorted(f for f in files if f.endswith(f".{s}") and (s != "1" or not f.startswith("lib/")))
              for s in SECTIONS}
    for v in by_sec.values():
        rng.shuffle(v)
    return sha, by_sec


def linux_candidates(out: Path, rng: random.Random) -> tuple[str, dict[str, list[Path]]]:
    listing = get(KERNEL).decode()
    name = max(set(re.findall(r"man-pages-[\d.]+\.tar\.xz", listing)),
               key=lambda s: [int(x) for x in re.findall(r"\d+", s)])
    src = out / "linux-src"
    src.mkdir(exist_ok=True, mode=0o700)
    tar = src / name
    if not tar.exists():
        tar.write_bytes(get(KERNEL + name, timeout=600))
    root = src / name.removesuffix(".tar.xz")
    if not root.exists():
        with tarfile.open(tar) as t:
            t.extractall(src, filter="data")
    by_sec = {}
    for s in SECTIONS:
        pages = sorted(p for p in root.rglob(f"man{s}/*.{s}") if p.is_file()
                       and not _first_request(p.read_text(errors="replace")).startswith(".so "))
        rng.shuffle(pages)
        by_sec[s] = pages
    return name, by_sec


def _first_request(src: str) -> str:
    """The first line that is not a roff comment."""
    return next((ln for ln in src.splitlines() if ln.strip() and not ln.startswith('.\\"')), "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-section", type=int, default=34)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries, failures = [], []

    def consider(system: str, sec: str, name: str, src: bytes, url: str, via: str) -> bool:
        text = src.decode("utf-8", errors="replace")
        lic = page_licence(text)
        if not lic:
            failures.append({"page": name, "source": f"{system}/{sec}", "reason": "licence not classified"})
            return False
        desc = description(render(src))
        if words(desc) < MIN_WORDS:
            failures.append({"page": name, "source": f"{system}/{sec}", "reason": f"DESCRIPTION under {MIN_WORDS} words"})
            return False
        rel = f"{system}/{sec}/{name}.txt"
        (out / system / sec).mkdir(parents=True, exist_ok=True, mode=0o700)
        (out / rel).write_text(desc)
        entries.append({"id": f"man-page/{system}/{name}", "category": "man-page", "source": f"{system}/{sec}",
                        "author": "", "url": url, "path": rel, "format": "text", "license": lic,
                        "fetched_at": now, "via": via, "sha256": hashlib.sha256(desc.encode()).hexdigest(),
                        "bytes": len(desc.encode())})
        return True

    sha, cands = openbsd_candidates(rng, args.per_section)
    for sec, files in cands.items():
        kept = 0
        for f in files:
            if kept >= args.per_section:
                break
            src = get(f"https://raw.githubusercontent.com/{OPENBSD}/{sha}/{urllib.parse.quote(f)}")
            if src is None:
                failures.append({"page": f, "source": f"openbsd/{sec}", "reason": "fetch failed"})
                continue
            kept += consider("openbsd", sec, Path(f).name, src, f"https://github.com/{OPENBSD}/blob/{sha}/{f}",
                             f"raw github.com/{OPENBSD}/{sha}/{f}; mandoc -T utf8 | col -b")
        print(f"openbsd/{sec}: {kept}", file=sys.stderr)

    release, lcands = linux_candidates(out, rng)
    for sec, pages in lcands.items():
        kept = 0
        for p in pages:
            if kept >= args.per_section:
                break
            kept += consider("linux", sec, p.name, p.read_bytes(),
                             f"https://man7.org/linux/man-pages/man{sec}/{p.name}.html",
                             f"{KERNEL}{release}; mandoc -T utf8 | col -b")
        print(f"linux/{sec}: {kept} of {len(pages)} from {release}", file=sys.stderr)

    (out / "manifest.json").write_text(json.dumps(
        {"description": "OpenBSD and Linux man page DESCRIPTION sections; see scripts/fetch_man_pages.py",
         "generated_at": now, "seed": args.seed, "openbsd_commit": sha, "linux_release": release,
         "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "pages;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
