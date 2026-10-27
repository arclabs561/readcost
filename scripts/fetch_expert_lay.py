"""Fetch texts written for experts alongside texts on the same subject written for lay readers.

    python3 -I scripts/fetch_expert_lay.py /Volumes/Rebuildable/readcost-ref/broad/expert-lay
    python3 scripts/eval_broad.py /Volumes/Rebuildable/readcost-ref/broad

Three sources, each selectable with ``--parts``:

- ``summaries``: research articles from PLOS Computational Biology, PLOS
  Genetics, PLOS Pathogens, PLOS Neglected Tropical Diseases and eLife, found
  with the Europe PMC search API and read as JATS from its ``fullTextXML``
  endpoint. The abstract is the expert text; the author summary (PLOS) or
  eLife digest (``abstract-type`` summary, executive-summary or
  plain-language-summary) is the lay text. An article is kept only when its
  ``<license>`` is CC BY or CC0, both sides have 80 or more words, and it has
  exactly one of each. Category ``summary-pair``.
- ``wikipedia``: articles in the Simple English Wikipedia categories Computer
  science, Mathematics, Physics and Biology (pages directly in each category)
  and their English Wikipedia counterparts by interlanguage link, read with the
  TextExtracts API as plain text. Section headings and everything from "See
  also", "References", "Notes", "Sources", "Further reading" or "External
  links" on are removed. Both sides must have 150 or more words. The revision
  ids read are recorded. CC BY-SA 4.0. Category ``wiki-pair``.
- ``govuk``: random samples of GOV.UK mainstream ``guide`` pages (written for
  the public) and ``detailed_guide`` pages (written for specialists) from the
  search API, with their HTML bodies from the content API. Open Government
  Licence v3.0. These are two groups, not pairs. Category ``govuk``, source
  the format.

Paired items carry ``pair_id`` and ``role`` (``expert`` or ``lay``). Every
request carries the project's User-Agent, and requests to each host are at
least a second apart. Writes ``manifest.json`` in the schema of
scripts/fetch_eval_corpus.py. The text stays under the output directory,
outside the repository.
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
from datetime import UTC, datetime
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
# journal as Europe PMC names it -> (source label, publication year searched)
JOURNALS = {"PLoS Comput Biol": ("plos-compbiol", 2021), "PLoS Genet": ("plos-genetics", 2021),
            "PLoS Pathog": ("plos-pathogens", 2021), "PLoS Negl Trop Dis": ("plos-ntd", 2021),
            "eLife": ("elife", 2019)}
LAY_TYPES = {"summary", "executive-summary", "plain-language-summary"}
SIMPLE_CATEGORIES = ("Computer science", "Mathematics", "Physics", "Biology")
END_SECTIONS = ("see also", "references", "notes", "sources", "further reading", "external links",
                "related pages", "other websites", "footnotes", "bibliography", "citations")
GAP = 1.0
_last: dict[str, float] = {}


def get(url: str, timeout: int = 60) -> bytes | None:
    """GET with the project's User-Agent, a second after the previous request to the host; None on 404."""
    host = urllib.parse.urlsplit(url).netloc
    for attempt in range(3):
        wait = _last.get(host, 0.0) + GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                        timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503):
                time.sleep(int(e.headers.get("Retry-After") or 20))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
    return None


def get_json(url: str) -> dict:
    body = get(url)
    return json.loads(body) if body else {}


# ------------------------------------------------------------------ JATS

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _jats_text(el: ET.Element) -> str:
    """Text of a JATS element, with formulas as [MATH] and citations, figures and tables left out."""
    def inner(e: ET.Element) -> str:
        return (e.text or "") + "".join(walk(c) + (c.tail or "") for c in e)

    def walk(e: ET.Element) -> str:
        name = _local(e.tag)
        if name in ("inline-formula", "disp-formula", "tex-math"):
            return "[MATH]"
        if name in ("xref", "fig", "table-wrap", "fn", "label", "title", "object-id"):
            return ""
        return inner(e)

    text = inner(el)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[\[(]\s*[,;–\- ]*\s*[\])]", "", text)    # brackets left empty by removed citations
    return re.sub(r"\s+([,.;:])", r"\1", text).strip()


def jats_licence(root: ET.Element) -> str | None:
    """``CC-BY`` or ``CC0`` when the article's licence permits reuse, else None."""
    for lic in root.iter():
        if _local(lic.tag) != "license":
            continue
        urls = [lic.get("{http://www.w3.org/1999/xlink}href") or ""]
        urls += [e.text or "" for e in lic.iter() if _local(e.tag) == "license_ref"]
        urls += [e.get("{http://www.w3.org/1999/xlink}href") or "" for e in lic.iter()]
        urls += [lic.get("license-type") or ""]
        blob = " ".join(urls + ["".join(lic.itertext())]).lower()
        if "publicdomain/zero" in blob or "cc0" in blob:
            return "CC0-1.0"
        attribution = (re.search(r"creativecommons\.org/licenses/by/\d", blob)
                       or "creative commons attribution license" in blob)
        if attribution and not re.search(r"by-nc|by-nd|noncommercial|no derivatives", blob):
            return "CC-BY-4.0"
    return None


def jats_abstracts(root: ET.Element) -> tuple[list[str], list[str]]:
    """(expert abstracts, lay summaries) of a JATS article's front matter, as paragraph text."""
    expert, lay = [], []
    front = next((e for e in root.iter() if _local(e.tag) == "article-meta"), root)
    for ab in front.iter():
        if _local(ab.tag) != "abstract":
            continue
        kind = (ab.get("abstract-type") or "").lower()
        paras = [_jats_text(p) for p in ab.iter() if _local(p.tag) == "p"]
        text = "\n\n".join(p for p in paras if p)
        if not text:
            continue
        if kind in LAY_TYPES:
            lay.append(text)
        elif not kind:
            expert.append(text)
    return expert, lay


# ------------------------------------------------------------------ Wikipedia

def clean_extract(text: str) -> str:
    """A TextExtracts plain-text article without headings and without the reference sections at the end."""
    keep = []
    for line in text.splitlines():
        m = re.fullmatch(r"\s*(=+)\s*(.*?)\s*\1\s*", line)
        if m:
            if m.group(2).lower() in END_SECTIONS:
                break
            continue
        keep.append(line.strip())
    body = "\n".join(keep)
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def wiki_page(host: str, title: str) -> dict | None:
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "extracts|revisions|langlinks",
                                "explaintext": 1, "rvprop": "ids", "lllang": "en", "redirects": 1,
                                "format": "json", "formatversion": 2})
    d = get_json(f"https://{host}/w/api.php?{q}")
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    p = pages[0]
    return {"title": p["title"], "pageid": p["pageid"], "revid": p["revisions"][0]["revid"],
            "extract": p.get("extract", ""), "en": (p.get("langlinks") or [{}])[0].get("title")}


# ------------------------------------------------------------------ main

def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--parts", default="summaries,wikipedia,govuk")
    ap.add_argument("--summaries", type=int, default=150, help="pairs, spread over the five journals")
    ap.add_argument("--wiki", type=int, default=150, help="pairs")
    ap.add_argument("--govuk", type=int, default=100, help="pages of each format")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    parts = set(args.parts.split(","))
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path = out / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"entries": [], "failures": []}
    cats = {"summaries": "summary-pair", "wikipedia": "wiki-pair", "govuk": "govuk"}
    redo = {cats[p] for p in parts}
    entries = [e for e in old["entries"] if e["category"] not in redo]
    failures = [f for f in old["failures"] if f.get("category") not in redo]

    def record(category, source, item_id, url, text, fmt, licence, via, **extra) -> None:
        ext = {"text": "txt", "html": "html"}[fmt]
        rel = f"{category}/{source}/{item_id.replace('/', '_')}.{ext}"
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        entries.append({"id": f"{category}/{source}/{item_id}", "category": category, "source": source,
                        "author": "", "url": url, "path": rel, "format": fmt, "license": licence,
                        "fetched_at": now, "via": via, **extra,
                        "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})

    if "summaries" in parts:
        per = -(-args.summaries // len(JOURNALS))
        for journal, (source, year) in JOURNALS.items():
            q = f'JOURNAL:"{journal}" AND OPEN_ACCESS:y AND PUB_YEAR:{year} AND SRC:MED'
            d = get_json(f"{EPMC}/search?" + urllib.parse.urlencode(
                {"query": q, "format": "json", "pageSize": 300, "resultType": "lite"}))
            ids = [r["pmcid"] for r in d.get("resultList", {}).get("result", []) if r.get("pmcid")]
            rng.shuffle(ids)
            got = 0
            for pmcid in ids:
                if got >= per:
                    break
                body = get(f"{EPMC}/{pmcid}/fullTextXML")
                if not body:
                    failures.append({"category": "summary-pair", "item": pmcid, "reason": "no full text"})
                    continue
                try:
                    root = ET.fromstring(body)
                except ET.ParseError:
                    failures.append({"category": "summary-pair", "item": pmcid, "reason": "XML parse error"})
                    continue
                lic = jats_licence(root)
                if not lic:
                    failures.append({"category": "summary-pair", "item": pmcid, "reason": "licence not CC BY or CC0"})
                    continue
                expert, lay = jats_abstracts(root)
                if len(expert) != 1 or len(lay) != 1:
                    failures.append({"category": "summary-pair", "item": pmcid,
                                     "reason": f"{len(expert)} abstracts, {len(lay)} lay summaries"})
                    continue
                if words(expert[0]) < 80 or words(lay[0]) < 80:
                    failures.append({"category": "summary-pair", "item": pmcid, "reason": "a side under 80 words"})
                    continue
                url = f"https://europepmc.org/article/PMC/{pmcid}"
                for role, text in (("expert", expert[0]), ("lay", lay[0])):
                    record("summary-pair", source, f"{pmcid}-{role}", url, text + "\n", "text", lic,
                           f"Europe PMC fullTextXML {pmcid}", pair_id=pmcid, role=role)
                got += 1
            print(f"{source}: {got} pairs from {len(ids)} search hits", file=sys.stderr)

    if "wikipedia" in parts:
        titles: list[tuple[str, str]] = []
        for cat in SIMPLE_CATEGORIES:
            q = urllib.parse.urlencode({"action": "query", "list": "categorymembers", "cmtitle": f"Category:{cat}",
                                        "cmnamespace": 0, "cmlimit": 500, "format": "json", "formatversion": 2})
            members = get_json(f"https://simple.wikipedia.org/w/api.php?{q}").get("query", {}).get("categorymembers", [])
            titles += [(cat, m["title"]) for m in members]
        rng.shuffle(titles)
        seen: set[str] = set()
        got = 0
        for cat, title in titles:
            if got >= args.wiki:
                break
            if title in seen:
                continue
            seen.add(title)
            simple = wiki_page("simple.wikipedia.org", title)
            if not simple or not simple["en"]:
                failures.append({"category": "wiki-pair", "item": title, "reason": "no English counterpart"})
                continue
            st = clean_extract(simple["extract"])
            if words(st) < 150:
                failures.append({"category": "wiki-pair", "item": title, "reason": "Simple article under 150 words"})
                continue
            en = wiki_page("en.wikipedia.org", simple["en"])
            et = clean_extract(en["extract"]) if en else ""
            if words(et) < 150:
                failures.append({"category": "wiki-pair", "item": title, "reason": "English article missing or short"})
                continue
            source = cat.lower().replace(" ", "-")
            pid = f"{simple['pageid']}"
            record("wiki-pair", source, f"{pid}-lay", f"https://simple.wikipedia.org/w/index.php?oldid={simple['revid']}",
                   st, "text", "CC-BY-SA-4.0", "simple.wikipedia.org TextExtracts explaintext",
                   pair_id=pid, role="lay", title=simple["title"], revid=simple["revid"])
            record("wiki-pair", source, f"{pid}-expert", f"https://en.wikipedia.org/w/index.php?oldid={en['revid']}",
                   et, "text", "CC-BY-SA-4.0", "en.wikipedia.org TextExtracts explaintext",
                   pair_id=pid, role="expert", title=en["title"], revid=en["revid"])
            got += 1
        print(f"wikipedia: {got} pairs from {len(seen)} Simple articles tried", file=sys.stderr)

    if "govuk" in parts:
        for fmt in ("guide", "detailed_guide"):
            links: list[str] = []
            start = 0
            while True:
                d = get_json("https://www.gov.uk/api/search.json?" + urllib.parse.urlencode(
                    {"filter_format": fmt, "count": 1000, "start": start, "fields": "link"}))
                batch = [r["link"] for r in d.get("results", [])]
                links += batch
                start += 1000
                if not batch or start >= d.get("total", 0):
                    break
            rng.shuffle(links)
            got = 0
            for link in links:
                if got >= args.govuk:
                    break
                d = get_json(f"https://www.gov.uk/api/content{link}")
                if d.get("locale", "en") != "en" or d.get("schema_name") != fmt:
                    failures.append({"category": "govuk", "item": link, "reason": "not English or schema differs"})
                    continue
                det = d.get("details", {})
                bodies = [p.get("body") for p in det.get("parts", [])] if fmt == "guide" else [det.get("body")]
                chunks = []
                for b in bodies:
                    if isinstance(b, list):   # multiple content types: take the HTML one
                        b = next((x["content"] for x in b if x.get("content_type") == "text/html"), "")
                    if b:
                        chunks.append(b)
                body = "\n".join(chunks)
                if words(re.sub(r"<[^>]+>", " ", html.unescape(body))) < 150:
                    failures.append({"category": "govuk", "item": link, "reason": "under 150 words"})
                    continue
                record("govuk", fmt, link.strip("/").replace("/", "_"), f"https://www.gov.uk{link}",
                       body + "\n", "html", "OGL-UK-3.0", "GOV.UK content API",
                       content_id=d.get("content_id"), updated_at=d.get("public_updated_at"))
                got += 1
            print(f"govuk {fmt}: {got} of {len(links)} listed", file=sys.stderr)

    manifest_path.write_text(json.dumps(
        {"description": "expert and lay texts; see scripts/fetch_expert_lay.py", "generated_at": now,
         "seed": args.seed, "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "texts;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
