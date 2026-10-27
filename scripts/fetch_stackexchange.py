"""Fetch Stack Exchange answers, high- and low-voted, and edited-against-original answer pairs.

    python3 -I scripts/fetch_stackexchange.py /Volumes/Rebuildable/readcost-ref/broad/stackexchange
    PYTHONPATH=src python3 scripts/eval_more.py /Volumes/Rebuildable/readcost-ref/broad

Uses the Stack Exchange API 2.3 without a key (a quota of 300 requests a day
per address, so the script makes about 40). For each site (unix,
softwareengineering, cs, math) it reads one page of 100 answers sorted by
score from the top (``high``) and one page of answers scored 0 or 1
(``low``), with a filter that adds the HTML body and the content licence, and
keeps up to ``--per-group`` answers per group that have at least 80 words of
prose. Category ``se-answer``, source ``<site>/<high|low>``.

For answers in those pages that were edited, it reads every revision with
``/posts/{ids}/revisions`` and pairs the first revision's body (``original``)
with the last (``edited``). A pair is kept when both sides have at least 80
words of prose and the prose differs. Category ``se-revision-pair``, source
the site, with ``pair_id`` and ``role``.

Bodies are converted from HTML to text: code blocks (``<pre>``) are dropped,
inline code stays as backticked text, TeX mathematics (``$...$``) on the math
and cs sites becomes ``[MATH]``, block quotes and images are dropped. Every
item records its CC BY-SA version (per revision for the original side). The
script honours the API's ``backoff`` field and waits a second between
requests. The text stays under the output directory, outside the repository.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
API = "https://api.stackexchange.com/2.3"
SITES = ("unix", "softwareengineering", "cs", "math")
MATH_SITES = {"math", "cs"}
MIN_WORDS = 80
INCLUDE = ("answer.body;answer.content_license;answer.link;answer.last_edit_date;"
           "revision.body;revision.content_license")
GAP = 1.0
_next = 0.0


def get(path: str, **params) -> dict:
    """One API request; waits a second, plus any ``backoff`` the previous response asked for."""
    global _next
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        wait = _next - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code not in (400, 429, 502, 503) or attempt == 2:
                raise
        body = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        _next = time.monotonic() + GAP + body.get("backoff", 0)
        if "error_id" in body:
            print(f"API error {body['error_id']}: {body.get('error_message')}", file=sys.stderr)
            if body["error_id"] == 502:  # throttle violation
                time.sleep(60)
                continue
            raise RuntimeError(body.get("error_message"))
        print(f"{path}: quota_remaining {body.get('quota_remaining')}", file=sys.stderr)
        return body
    raise RuntimeError(f"gave up on {url}")


class _Text(HTMLParser):
    """Stack Exchange post HTML to plain paragraphs; code blocks, quotes and images dropped."""

    BLOCK = frozenset({"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "br", "hr", "tr", "dd", "dt"})
    SKIP = frozenset({"pre", "blockquote", "script", "style", "table"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif not self.skip and tag in self.BLOCK:
            self.out.append("\n\n")
        elif not self.skip and tag == "code":
            self.out.append("`")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif not self.skip and tag in self.BLOCK:
            self.out.append("\n\n")
        elif not self.skip and tag == "code":
            self.out.append("`")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(body: str, math: bool = False) -> str:
    """Paragraphs of a post body, without code blocks; ``[MATH]`` for TeX when ``math``."""
    p = _Text()
    p.feed(body)
    p.close()
    text = "".join(p.out)
    if math:
        text = re.sub(r"\$\$.+?\$\$|\$[^$\n]+\$|\\\[.+?\\\]|\\\(.+?\\\)", "[MATH]", text, flags=re.DOTALL)
    paras = [re.sub(r"[ \t\r\n]+", " ", s).strip() for s in re.split(r"\n\s*\n", text)]
    paras = [s.replace("``", "") for s in paras if s and s != "`"]
    return "\n\n".join(paras) + "\n" if paras else ""


def prose_words(text: str) -> int:
    """Words outside backticked code."""
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", re.sub(r"`[^`]*`", " ", text)))


def pair_revisions(revisions: list[dict]) -> dict[int, tuple[dict, dict]]:
    """Per post, its first and last revision that carry a body; posts with one revision are left out."""
    by_post: dict[int, list[dict]] = {}
    for r in revisions:
        if r.get("revision_number") and r.get("body"):
            by_post.setdefault(r["post_id"], []).append(r)
    out = {}
    for pid, rs in by_post.items():
        rs.sort(key=lambda r: r["revision_number"])
        if len(rs) >= 2 and rs[0]["revision_number"] == 1:
            out[pid] = (rs[0], rs[-1])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-group", type=int, default=25)
    ap.add_argument("--pairs-per-site", type=int, default=25)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    flt = get("filters/create", base="default", unsafe="false", include=INCLUDE)["items"][0]["filter"]
    entries, failures = [], []

    def write(rel: str, text: str, entry: dict) -> None:
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        entries.append(entry | {"path": rel, "format": "markdown", "fetched_at": now,
                                "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})

    for site in SITES:
        math = site in MATH_SITES
        pages = {"high": get("answers", site=site, sort="votes", order="desc", pagesize=100, filter=flt),
                 "low": get("answers", site=site, sort="votes", order="desc", min=0, max=1, pagesize=100,
                            filter=flt)}
        edited: dict[int, dict] = {}
        for group, page in pages.items():
            kept = 0
            for a in page["items"]:
                if a.get("last_edit_date"):
                    edited[a["answer_id"]] = a
                if kept >= args.per_group:
                    continue
                text = html_to_text(a["body"], math)
                if prose_words(text) < MIN_WORDS:
                    failures.append({"id": a["answer_id"], "source": f"{site}/{group}",
                                     "reason": f"under {MIN_WORDS} words of prose"})
                    continue
                write(f"answers/{site}/{group}/{a['answer_id']}.md", text, {
                    "id": f"se-answer/{site}/{a['answer_id']}", "category": "se-answer",
                    "source": f"{site}/{group}", "site": site, "group": group, "score": a["score"],
                    "author": "", "url": a["link"], "license": a.get("content_license") or "CC BY-SA",
                    "via": f"api.stackexchange.com/2.3/answers?site={site}&sort=votes ({group})"})
                kept += 1
            print(f"{site}/{group}: {kept} answers", file=sys.stderr)

        ids = sorted(edited)
        revisions: list[dict] = []
        for i in range(0, len(ids), 100):
            chunk = ";".join(map(str, ids[i:i + 100]))
            page_no = 1
            while True:
                r = get(f"posts/{chunk}/revisions", site=site, pagesize=100, page=page_no, filter=flt)
                revisions += r["items"]
                if not r.get("has_more") or page_no >= 12:
                    break
                page_no += 1
        kept = 0
        for pid, (first, last) in sorted(pair_revisions(revisions).items(),
                                         key=lambda kv: -edited[kv[0]]["score"]):
            if kept >= args.pairs_per_site:
                break
            a, b = html_to_text(first["body"], math), html_to_text(last["body"], math)
            why = None
            if min(prose_words(a), prose_words(b)) < MIN_WORDS:
                why = f"a side under {MIN_WORDS} words of prose"
            elif re.sub(r"\W+", "", a) == re.sub(r"\W+", "", b):
                why = "prose unchanged"
            if why:
                failures.append({"id": pid, "source": f"{site}/pair", "reason": why})
                continue
            link = edited[pid]["link"]
            for role, rev, text in (("original", first, a), ("edited", last, b)):
                write(f"pairs/{site}/{pid}.{role}.md", text, {
                    "id": f"se-revision-pair/{site}/{pid}/{role}", "category": "se-revision-pair",
                    "source": site, "pair_id": f"{site}/{pid}", "role": role,
                    "revision": rev["revision_number"], "score": edited[pid]["score"], "author": "",
                    "url": f"https://{site}.stackexchange.com/posts/{pid}/revisions",
                    "answer_url": link,
                    "license": rev.get("content_license") or edited[pid].get("content_license") or "CC BY-SA",
                    "via": f"api.stackexchange.com/2.3/posts/{pid}/revisions?site={site}"})
            kept += 1
        print(f"{site}: {kept} revision pairs from {len(edited)} edited answers", file=sys.stderr)

    (out / "manifest.json").write_text(json.dumps(
        {"description": "Stack Exchange answers and revision pairs; see scripts/fetch_stackexchange.py",
         "generated_at": now, "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "items;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
