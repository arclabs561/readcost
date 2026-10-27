"""Fetch openly licensed arXiv abstracts and introductions for evaluation.

    python3 -I scripts/fetch_arxiv.py /Volumes/Rebuildable/readcost-ref/broad/arxiv
    python3 scripts/eval_broad.py /Volumes/Rebuildable/readcost-ref/broad

Harvests arXiv's OAI-PMH interface (metadata format ``arXiv``) one datestamp
day at a time, walking back from ``--date`` until each top-level set (cs,
math, physics, q-bio, econ, stat, eess, q-fin) has ``--per-set`` papers whose
primary category belongs to that set and whose ``<license>`` is CC BY, CC
BY-SA or CC0. Papers under arXiv's non-exclusive distribution licence or a
non-commercial or no-derivatives licence are skipped. The datestamp is the
date a record last changed, so a day's records include revised older papers.

Writes each abstract to ``abstract/<set>/<id>.txt``, with inline ``$...$``
mathematics replaced by ``[MATH]``. For papers first submitted in 2024 or
later it then requests ``https://arxiv.org/html/<id>`` (up to ``--intros``
pages, spread evenly over sets) and, when section ``S1`` is titled
"Introduction", writes its paragraphs to ``intro/<set>/<id>.txt``, with each
``<math>`` element replaced by ``[MATH]`` and citations, footnotes, figures
and tables removed. Requests to arxiv.org are spaced at least three seconds
apart, as arXiv asks. Writes ``manifest.json`` in the schema of
scripts/fetch_eval_corpus.py: categories ``arxiv-abstract`` and
``arxiv-intro``, source the set, licence the paper's licence URL. The text
stays under the output directory, outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
OAI = "https://oaipmh.arxiv.org/oai"
SETS = ("cs", "math", "physics", "q-bio", "econ", "stat", "eess", "q-fin")
NS = {"oai": "http://www.openarchives.org/OAI/2.0/", "a": "http://arxiv.org/OAI/arXiv/"}
OPEN_LICENSES = {
    "http://creativecommons.org/licenses/by/4.0/": "CC-BY-4.0",
    "http://creativecommons.org/licenses/by/3.0/": "CC-BY-3.0",
    "http://creativecommons.org/licenses/by-sa/4.0/": "CC-BY-SA-4.0",
    "http://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
}
GAP = 3.1  # seconds between requests to arxiv.org
_last = 0.0


def get(url: str, timeout: int = 90) -> bytes | None:
    """GET with the project's User-Agent, three seconds after the previous request; None on 404."""
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
            if e.code in (429, 503):
                time.sleep(int(e.headers.get("Retry-After") or 30))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
    return None


def set_of(primary: str) -> str:
    """The OAI top-level set of a primary category such as ``cs.LG`` or ``hep-th``."""
    archive = primary.split(".")[0]
    return archive if archive in SETS else "physics"


def license_name(url: str) -> str | None:
    """A short name for a reuse-permitting licence URL, else None."""
    return OPEN_LICENSES.get(url.strip().replace("https://", "http://"))


def strip_tex_math(text: str) -> str:
    """Replace inline and display TeX mathematics with ``[MATH]`` and normalize whitespace.

    arXiv abstracts mark a new paragraph with a newline and indentation.
    """
    text = re.sub(r"\$\$.+?\$\$|\$[^$]+\$|\\\[.+?\\\]|\\\(.+?\\\)", "[MATH]", text, flags=re.DOTALL)
    paras = re.split(r"\n\s+(?=\S)", text.strip())
    return "\n\n".join(re.sub(r"\s+", " ", p).strip() for p in paras if p.strip())


def parse_records(xml: bytes) -> tuple[list[dict], str | None]:
    """Records from one ListRecords response and the resumption token, if any."""
    root = ET.fromstring(xml)
    out = []
    for rec in root.iterfind(".//oai:record", NS):
        meta = rec.find("oai:metadata/a:arXiv", NS)
        if meta is None:
            continue
        cats = (meta.findtext("a:categories", "", NS) or "").split()
        out.append({
            "id": meta.findtext("a:id", "", NS).strip(),
            "created": meta.findtext("a:created", "", NS).strip(),
            "categories": cats,
            "primary": cats[0] if cats else "",
            "license": (meta.findtext("a:license", "", NS) or "").strip(),
            "title": re.sub(r"\s+", " ", meta.findtext("a:title", "", NS) or "").strip(),
            "abstract": meta.findtext("a:abstract", "", NS) or "",
        })
    token = root.findtext(".//oai:resumptionToken", None, NS)
    return out, (token.strip() or None) if token else None


class _IntroParser(HTMLParser):
    """Collect paragraph text from section S1 of an arXiv LaTeXML page."""

    SKIP = ("ltx_cite", "ltx_note", "ltx_figure", "ltx_table", "ltx_bibliography", "ltx_float",
            "ltx_tag", "ltx_equation", "ltx_equationgroup")
    VOID = frozenset({"br", "img", "hr", "meta", "link", "input", "col", "source", "wbr"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []   # (tag, opens a skipped region)
        self.in_s1 = 0          # depth of the open S1 section element, 0 when outside
        self.skip = 0
        self.math = 0
        self.in_title = False
        self.title = ""
        self.paras: list[str] = []
        self.cur: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "section" and a.get("id") == "S1":
            self.in_s1 = len(self.stack) + 1
        skipped = self.in_s1 and any(c in cls.split() for c in self.SKIP)
        self.stack.append((tag, bool(skipped)))
        if not self.in_s1:
            return
        if skipped:
            self.skip += 1
            if tag == "cite" or "ltx_cite" in cls:
                self._add(" ")
            return
        if tag == "math":
            self.math += 1
            if self.math == 1 and not self.skip:
                self._add("[MATH]")
        elif tag == "h2" and "ltx_title_section" in cls:
            self.in_title = True
        elif tag == "p" and "ltx_p" in cls and not self.skip:
            self.cur = []

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        # Pop to the matching tag; LaTeXML output is well formed, so this rarely skips.
        while self.stack:
            t, skipped = self.stack.pop()
            if skipped:
                self.skip -= 1
            if self.in_s1 and t == "math":
                self.math = max(0, self.math - 1)
            if self.in_s1 and t == "h2":
                self.in_title = False
            if self.in_s1 and t == "p" and self.cur is not None and not self.skip:
                text = re.sub(r"\s+", " ", "".join(self.cur)).strip()
                text = re.sub(r"\s+([,.;:)])", r"\1", text).replace("( ", "(")
                if text:
                    self.paras.append(text)
                self.cur = None
            if self.in_s1 and len(self.stack) < self.in_s1:
                self.in_s1 = 0
            if t == tag:
                break

    def handle_data(self, data):
        if not self.in_s1 or self.skip or self.math:
            return
        if self.in_title:
            self.title += data
        self._add(data)

    def _add(self, s: str) -> None:
        if self.cur is not None:
            self.cur.append(s)


def parse_intro(page: str) -> str | None:
    """The introduction (section S1) as plain paragraphs, or None when S1 is not an introduction."""
    p = _IntroParser()
    p.feed(page)
    title = re.sub(r"^[\dIVX.]+\s+", "", p.title.strip())
    if not title.lower().startswith("introduction") or not p.paras:
        return None
    return "\n\n".join(p.paras) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--date", default="2026-10-20", help="first datestamp day to harvest")
    ap.add_argument("--per-set", type=int, default=50)
    ap.add_argument("--intros", type=int, default=150)
    ap.add_argument("--max-days", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    licence_counts: dict[str, int] = {}
    chosen: dict[str, list[dict]] = {s: [] for s in SETS}
    seen: set[str] = set()
    for s in SETS:
        day = date.fromisoformat(args.date)
        for _ in range(args.max_days):
            if len(chosen[s]) >= args.per_set:
                break
            d = day.isoformat()
            url = f"{OAI}?" + urllib.parse.urlencode({"verb": "ListRecords", "metadataPrefix": "arXiv",
                                                      "set": s, "from": d, "until": d})
            pool: list[dict] = []
            while url:
                body = get(url)
                if body is None:
                    break
                if b"noRecordsMatch" in body:
                    break
                recs, token = parse_records(body)
                pool += recs
                if len(pool) >= 1500 or not token:
                    break
                url = f"{OAI}?" + urllib.parse.urlencode({"verb": "ListRecords", "resumptionToken": token})
            for r in pool:
                key = license_name(r["license"]) or r["license"] or "none"
                licence_counts[key] = licence_counts.get(key, 0) + 1
            ok = [r for r in pool if license_name(r["license"]) and set_of(r["primary"]) == s
                  and r["id"] not in seen and len(r["abstract"].split()) >= 50]
            rng.shuffle(ok)
            for r in ok[: args.per_set - len(chosen[s])]:
                chosen[s].append(r)
                seen.add(r["id"])
            print(f"{s} {d}: {len(pool)} records, {len(ok)} usable, {len(chosen[s])} kept", file=sys.stderr)
            day -= timedelta(days=1)

    entries: list[dict] = []

    def record(category: str, s: str, r: dict, sub: str, text: str, url: str, via: str) -> None:
        rel = f"{sub}/{s}/{r['id'].replace('/', '_')}.txt"
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        entries.append({"id": f"{category}/{s}/{r['id']}", "category": category, "source": s,
                        "paper": r["id"], "primary": r["primary"], "created": r["created"],
                        "author": "", "url": url, "path": rel, "format": "text",
                        "license": license_name(r["license"]), "license_url": r["license"],
                        "fetched_at": now, "via": via,
                        "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})

    for s in SETS:
        for r in chosen[s]:
            record("arxiv-abstract", s, r, "abstract", strip_tex_math(html.unescape(r["abstract"])) + "\n",
                   f"https://arxiv.org/abs/{r['id']}", "OAI-PMH ListRecords metadataPrefix=arXiv")

    per_set = -(-args.intros // len(SETS))
    failures = []
    for s in SETS:
        cands = [r for r in chosen[s] if r["created"] >= "2024-01-01"]
        got = 0
        for r in cands:
            if got >= per_set:
                break
            page = get(f"https://arxiv.org/html/{r['id']}")
            intro = parse_intro(page.decode("utf-8", "replace")) if page else None
            if intro is None:
                failures.append({"paper": r["id"], "reason": "no HTML" if page is None else "S1 is not an introduction"})
                continue
            record("arxiv-intro", s, r, "intro", intro, f"https://arxiv.org/html/{r['id']}#S1",
                   "arxiv.org/html LaTeXML section S1")
            got += 1
        print(f"{s}: {got} introductions", file=sys.stderr)

    (out / "manifest.json").write_text(json.dumps(
        {"description": "arXiv abstracts and introductions under CC BY, CC BY-SA or CC0; see scripts/fetch_arxiv.py",
         "generated_at": now, "harvest_start": args.date, "licence_counts_seen": licence_counts,
         "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "texts;", len(failures), "introductions skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
