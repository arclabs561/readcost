"""Fetch a stratified sample of GitHub READMEs by language and star count.

    PYTHONPATH=src python3 scripts/fetch_github_readmes.py /Volumes/Rebuildable/readcost-ref/broad/readmes
    python3 scripts/eval_broad.py /Volumes/Rebuildable/readcost-ref/broad

Draws repositories for each cell of eight languages (Rust, Go, Python,
JavaScript, TypeScript, Java, C++, Haskell) by four star tiers (5..50,
50..500, 500..5000, more than 5000). For each cell it picks ``--windows``
random creation-date windows (a month for the lowest tier, wider windows for
higher tiers, where repositories are scarcer), asks GitHub's repository search
for the total, then reads one random results page, so the sample is not the
top of the search ranking. It keeps non-fork, non-archived repositories whose
licence GitHub identifies (an SPDX id other than NOASSERTION); repositories
with no recognized licence are skipped. It then reads each README raw and
keeps it when it has at least 100 words of prose (outside code blocks, tables,
HTML, badges and link-only lines) and readcost.lang does not call it another
language, up to ``--per-cell`` per cell.

Uses the `gh` CLI, so it needs a GitHub login; searches are spaced 2.1
seconds apart (30 a minute). Writes ``manifest.json`` in the schema of
scripts/fetch_eval_corpus.py, category ``readme``, source ``<language>/<tier>``,
with the SPDX licence, star count, creation date and the README's blob SHA.
The text stays under the output directory, outside the repository.
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
from datetime import UTC, date, datetime
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
LANGS = ("Rust", "Go", "Python", "JavaScript", "TypeScript", "Java", "C++", "Haskell")
# tier name -> (search qualifier, window length in months)
TIERS = {"5-50": ("5..50", 1), "50-500": ("50..500", 3), "500-5000": ("500..5000", 12),
         "5000+": (">5000", 36)}
FIRST_YEAR = {"Rust": 2014, "TypeScript": 2014, "Go": 2012}
SEARCH_GAP = 2.1
NO_LICENCE = {None, "", "NOASSERTION"}
MIN_PROSE_WORDS = 100
_last = 0.0


def gh(args: list[str], raw: bool = False) -> str:
    out = subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}",
                          "-H", "Accept: application/vnd.github.raw" if raw else "Accept: application/vnd.github+json",
                          *args], check=True, capture_output=True, text=True, timeout=120)
    return out.stdout


def search(q: str, page: int, per_page: int) -> dict:
    """One search request, 2.1 s after the last; on an error (usually a secondary rate limit), wait a minute and retry (four tries)."""
    global _last
    for attempt in range(4):
        wait = _last + SEARCH_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            return json.loads(gh(["-X", "GET", "search/repositories", "-f", f"q={q}",
                                  "-f", f"per_page={per_page}", "-f", f"page={page}"]))
        except subprocess.CalledProcessError as e:
            if attempt == 3:
                raise
            print(f"search failed; retrying in 65 s ({e.stderr.strip()[:120]})", file=sys.stderr)
            time.sleep(65)
    raise AssertionError("unreachable")


def window(rng: random.Random, lang: str, months: int) -> str:
    """A random creation-date window of ``months`` months between the language's first year and 2025."""
    first = FIRST_YEAR.get(lang, 2010)
    span = (2025 - first) * 12 - months
    start = rng.randrange(max(span, 1))
    y, m = first + start // 12, start % 12 + 1
    ey, em = y + (m - 1 + months) // 12, (m - 1 + months) % 12 + 1
    end = date(ey, em, 1).toordinal() - 1
    return f"{date(y, m, 1).isoformat()}..{date.fromordinal(end).isoformat()}"


def licence_ok(repo: dict) -> str | None:
    """The SPDX id of a repository whose licence GitHub recognizes, else None."""
    spdx = (repo.get("license") or {}).get("spdx_id")
    return None if spdx in NO_LICENCE else spdx


def prose_text(md: str) -> str:
    """The running prose of a Markdown or reStructuredText README: no code, tables, HTML or badges."""
    md = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", md)        # fenced code
    md = re.sub(r"(?s)<!--.*?-->", "", md)
    md = re.sub(r"(?s)<(pre|code|table|picture|svg)\b.*?</\1>", "", md, flags=re.IGNORECASE)
    md = re.sub(r"<[^>]+>", " ", md)                                     # other HTML tags
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)                         # images and badges
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)                     # links keep their text
    keep = []
    for line in md.splitlines():
        s = line.strip()
        if (not s or s.startswith(("|", ".. ", ":", "#")) or line.startswith(("    ", "\t"))
                or re.fullmatch(r"[#=\-*_~`+^\s]+", s)):
            continue
        s = re.sub(r"^([-*+]|\d+[.)])\s+", "", s)
        s = re.sub(r"https?://\S+", "", s)
        if len(re.findall(r"[A-Za-z]{2,}", s)) >= 3:
            keep.append(s)
    return "\n".join(keep)


def prose_words(md: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", prose_text(md)))


def readme_format(name: str) -> str:
    low = name.lower()
    if low.endswith((".md", ".markdown", ".mdown")):
        return "markdown"
    if low.endswith(".rst"):
        return "rst"
    return "text"


def keep_readme(text: str, other_language) -> str | None:
    """None when a README is kept, else the reason it was dropped."""
    if prose_words(text) < MIN_PROSE_WORDS:
        return f"under {MIN_PROSE_WORDS} words of prose"
    lang = other_language(prose_text(text))
    if lang:
        return f"not English ({lang})"
    return None


def main() -> int:
    from readcost.lang import other_language

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-cell", type=int, default=12)
    ap.add_argument("--windows", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries, failures = [], []
    seen: set[str] = set()
    for lang in LANGS:
        for tier, (stars, months) in TIERS.items():
            cands = []
            for _ in range(args.windows):
                q = f"language:{lang} stars:{stars} created:{window(rng, lang, months)} fork:false archived:false"
                total = search(q, 1, 1)["total_count"]
                if not total:
                    continue
                pages = max(1, min(total, 1000) // 30)
                items = search(q, rng.randrange(pages) + 1, 30)["items"]
                rng.shuffle(items)
                cands += [(q, it) for it in items]
            kept = 0
            source = f"{lang.lower().replace('+', 'p')}/{tier}"
            for q, it in cands:
                if kept >= args.per_cell:
                    break
                name = it["full_name"]
                spdx = licence_ok(it)
                if name in seen:
                    continue
                seen.add(name)
                if not spdx:
                    failures.append({"repo": name, "source": source, "reason": "no recognized licence"})
                    continue
                try:
                    meta = json.loads(gh([f"repos/{name}/readme"]))
                    text = gh([f"repos/{name}/readme"], raw=True)
                except subprocess.CalledProcessError:
                    failures.append({"repo": name, "source": source, "reason": "no README"})
                    continue
                why = keep_readme(text, other_language)
                if why:
                    failures.append({"repo": name, "source": source, "reason": why})
                    continue
                fmt = readme_format(meta["name"])
                ext = {"markdown": "md", "rst": "rst", "text": "txt"}[fmt]
                rel = f"{source}/{name.replace('/', '__')}.{ext}"
                path = out / rel
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                path.write_text(text)
                entries.append({"id": f"readme/{source}/{name}", "category": "readme", "source": source,
                                "language": lang, "tier": tier, "stars": it["stargazers_count"],
                                "created": it["created_at"], "spdx": spdx, "author": "",
                                "url": meta.get("html_url") or f"https://github.com/{name}", "path": rel,
                                "format": fmt, "license": spdx, "fetched_at": now,
                                "via": f"gh api search/repositories q={q!r}; repos/{name}/readme@{meta['sha']}",
                                "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})
                kept += 1
            print(f"{source}: {kept} kept of {len(cands)} candidates", file=sys.stderr)
    (out / "manifest.json").write_text(json.dumps(
        {"description": "READMEs by language and star tier; see scripts/fetch_github_readmes.py",
         "generated_at": now, "seed": args.seed, "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "READMEs;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
