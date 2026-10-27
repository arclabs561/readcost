"""Fetch MDN Web Docs pages, reference pages and guides, from the mdn/content repository.

    python3 -I scripts/fetch_mdn.py /Volumes/Rebuildable/readcost-ref/broad/mdn
    PYTHONPATH=src python3 scripts/eval_more.py /Volumes/Rebuildable/readcost-ref/broad

Lists ``files/en-us`` of mdn/content with one recursive tree request (``gh
api``, so it needs a GitHub login), keeps the ``index.md`` files under
``web/``, ``learn_web_development/`` and ``webassembly/``, and splits them into
likely guides (paths with a ``guide``, ``guides`` or ``tutorial`` segment, and
the learning area) and the rest. It reads a seeded random order of each list
raw from raw.githubusercontent.com at the listed commit, a quarter second
apart, without cloning, and classifies each page by the ``page-type`` in its
front matter: ``guide`` for guide, tutorial and learning-area page types,
skipped for landing and listing pages, ``reference`` otherwise. It stops at
``--per-group`` pages of 150 or more prose words per group.

Before writing, the front matter is removed; cross-reference macros such as
``{{domxref("Window.open", "open()")}}`` become their display text and every
other ``{{macro}}`` is removed; the "Specifications", "Browser
compatibility" and "See also" sections are dropped, and ``> [!NOTE]``
markers are removed. Code blocks stay for readcost's Markdown reader to skip.
Prose on MDN is CC BY-SA 2.5 (code samples are CC0 and are skipped by the
reader). Category ``mdn``, source ``reference`` or ``guide``, with the page
type. The text stays under the output directory, outside the repository.
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
REPO = "mdn/content"
ROOTS = ("web/", "learn_web_development/", "webassembly/")
GUIDE_TYPES = {"guide", "tutorial", "tutorial-chapter", "learn-module-chapter", "learn-module",
               "learn-module-assessment", "learn-topic", "learn-area", "learn-faq", "how-to"}
SKIP_TYPES = {"landing-page", "listing-page", ""}
XREF = {"domxref", "cssxref", "jsxref", "htmlelement", "httpheader", "httpmethod", "httpstatus", "glossary",
        "svgelement", "svgattr", "htmlattrxref", "mathmlelement", "event", "csp", "webextapiref", "wasmxref"}
DROP_SECTIONS = ("specifications", "browser compatibility", "see also")
MIN_WORDS = 150
GAP = 0.25
_last = 0.0


def gh(args: list[str]) -> str:
    """``gh api``, retried twice: the 7 MB tree response sometimes fails."""
    for attempt in range(3):
        try:
            return subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}", *args], check=True,
                                  capture_output=True, text=True, timeout=300).stdout
        except subprocess.CalledProcessError as e:
            if attempt == 2:
                raise
            print(f"gh api failed, retrying: {e.stderr.strip()[:200]}", file=sys.stderr)
            time.sleep(30)
    raise AssertionError("unreachable")


def raw(sha: str, path: str) -> str | None:
    global _last
    url = f"https://raw.githubusercontent.com/{REPO}/{sha}/{urllib.parse.quote(path)}"
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


def split_front_matter(md: str) -> tuple[dict[str, str], str]:
    """Top-level ``key: value`` pairs of the YAML front matter, and the body after it."""
    m = re.match(r"(?s)\A---\n(.*?)\n---\n?", md)
    if not m:
        return {}, md
    meta = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip("\"'")
    return meta, md[m.end():]


def _macro(m: re.Match) -> str:
    name = m.group(1).lower()
    args = re.findall(r"\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)'", m.group(2) or "")
    args = [a or b for a, b in args]
    if name in XREF and args:
        return args[1] if len(args) > 1 and args[1] else args[0]
    return ""


def clean_mdn(body: str) -> str:
    """MDN Markdown with macros resolved or removed and reference-only sections dropped."""
    body = re.sub(r"\{\{\s*([A-Za-z_][\w-]*)\s*(?:\((.*?)\))?\s*\}\}", _macro, body)
    out, drop, in_code = [], False, False
    for line in body.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_code = not in_code
        if not in_code and (h := re.match(r"^(#{1,6})\s+(.*)$", line)):
            drop = h.group(2).strip().lower() in DROP_SECTIONS
        if drop:
            continue
        if not in_code:
            line = re.sub(r"^(\s*>\s*)\[!(NOTE|WARNING|CALLOUT|TIP|IMPORTANT)\]\s*", r"\1", line)
            if line.strip() == ">":
                continue
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def prose_words(md: str) -> int:
    md = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", md)
    md = re.sub(r"`[^`]*`", " ", md)
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", md))


def is_guide_path(path: str) -> bool:
    segs = path.split("/")
    return path.startswith("learn_web_development/") or any(s in ("guide", "guides", "tutorial", "tutorials")
                                                            for s in segs)


def group_of(page_type: str) -> str | None:
    if page_type in SKIP_TYPES:
        return None
    return "guide" if page_type in GUIDE_TYPES else "reference"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-group", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sha = json.loads(gh([f"repos/{REPO}/commits/main"]))["sha"]
    en = next(x["sha"] for x in json.loads(gh([f"repos/{REPO}/contents/files?ref={sha}"])) if x["name"] == "en-us")
    tree = json.loads(gh([f"repos/{REPO}/git/trees/{en}?recursive=1"]))
    paths = sorted(t["path"] for t in tree["tree"]
                   if t["path"].endswith("/index.md") and t["path"].startswith(ROOTS))
    pools = {"guide": [p for p in paths if is_guide_path(p)], "reference": [p for p in paths if not is_guide_path(p)]}
    for pool in pools.values():
        rng.shuffle(pool)
    entries, failures = [], []
    kept = {"guide": 0, "reference": 0}
    for pool_name in ("guide", "reference"):
        for p in pools[pool_name]:
            if kept[pool_name] >= args.per_group:
                break
            full = f"files/en-us/{p}"
            text = raw(sha, full)
            if text is None:
                failures.append({"path": full, "reason": "fetch failed"})
                continue
            meta, body = split_front_matter(text)
            group = group_of(meta.get("page-type", ""))
            if group is None or kept[group] >= args.per_group:
                failures.append({"path": full, "reason": f"page-type {meta.get('page-type')!r} not wanted"})
                continue
            cleaned = clean_mdn(body)
            if prose_words(cleaned) < MIN_WORDS:
                failures.append({"path": full, "reason": f"under {MIN_WORDS} words of prose"})
                continue
            slug = meta.get("slug") or p[:-len("/index.md")]
            rel = f"{group}/{p[:-len('/index.md')].replace('/', '__')}.md"
            (out / group).mkdir(exist_ok=True, mode=0o700)
            (out / rel).write_text(cleaned)
            entries.append({"id": f"mdn/{group}/{slug}", "category": "mdn", "source": group,
                            "page_type": meta.get("page-type"), "author": "",
                            "url": f"https://developer.mozilla.org/en-US/docs/{slug}", "path": rel,
                            "format": "markdown", "license": "CC-BY-SA-2.5", "fetched_at": now,
                            "via": f"raw github.com/{REPO}/{sha}/{full}",
                            "sha256": hashlib.sha256(cleaned.encode()).hexdigest(),
                            "bytes": len(cleaned.encode())})
            kept[group] += 1
        print(f"after {pool_name} pool: {kept}", file=sys.stderr)
    (out / "manifest.json").write_text(json.dumps(
        {"description": "MDN reference and guide pages; see scripts/fetch_mdn.py", "generated_at": now,
         "seed": args.seed, "commit": sha, "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "pages;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
