"""Fetch openly licensed samples from non-technical domains: literature, news, law, health, scholarship.

    REF=/Volumes/Rebuildable/readcost-ref/broad
    python3 -I scripts/fetch_domains.py $REF/literature --parts literature
    python3 -I scripts/fetch_domains.py $REF/news --parts news
    python3 -I scripts/fetch_domains.py $REF/law --parts federal-register,uk-notes,courts
    python3 -I scripts/fetch_domains.py $REF/health --parts medlineplus
    python3 -I scripts/fetch_domains.py $REF/openalex --parts openalex
    python3 -I scripts/fetch_domains.py $REF/wiki-featured --parts featured

Parts (``--parts``, comma-separated; each part's earlier entries in the
output directory's manifest are replaced, the others kept):

- ``literature``: passages from Project Gutenberg books by authors born
  1770 to 1880 and dead by 1945, in English, with Library of Congress class PR
  or PS (English and American literature). Novels are books whose subjects
  contain "Fiction"; essays are books whose subjects contain "essays". Books
  whose Gutenberg header mentions copyright are skipped. The
  book list comes from Gutenberg's ``pg_catalog.csv.gz``; texts from
  ``/cache/epub/<n>/pg<n>.txt``, with the header and the licence text outside
  the ``*** START`` and ``*** END`` lines removed. Up to ``--per-book``
  passages per book, each a run of whole paragraphs of 400 to 800 words from
  the middle 80% of the book. Public domain in the USA. Category
  ``literature``, source ``novel`` or ``essay``.
- ``news``: Wikinews articles, at most two from each of random day categories
  (``Category:<Month> <day>, <year>``, 2005 to 2024), as plain text from TextExtracts with the dateline,
  headings and the sections from "Sources" on removed. The licence is read
  from the site's ``rightsinfo``. Category ``news``, source ``wikinews``.
- ``federal-register``: rules, proposed rules and notices from the Federal
  Register API, a random results page per type and year (2001 to 2025). The
  text is the GPO plain text from "SUPPLEMENTARY INFORMATION:" on (the whole
  text when absent), unwrapped, with page markers removed, cut at a paragraph
  end after ``--cap`` words. US government work, public domain. Category
  ``regulation``, source ``federal-register``.
- ``uk-notes``: explanatory notes to UK Public General Acts, 2000 to 2025,
  from legislation.gov.uk's XML, every ``Text`` element in order, cut after
  ``--cap`` words. Open Government Licence v3.0. Category ``regulation``,
  source ``uk-explanatory-notes``.
- ``courts``: lead (majority) opinions, opinion type ``020lead``, from
  random rows of the COLD Cases dataset (harvard-lil/cold-cases, CourtListener
  and Caselaw Access Project data, CC0) read with the Hugging Face datasets
  server. CourtListener's own opinion API needs a token. Combined opinions,
  concurrences and dissents are skipped. Cut after ``--cap`` words. Category
  ``court-opinion``, source the court type.
- ``medlineplus``: MedlinePlus health topic summaries (English) from the
  NLM's daily XML file, as HTML. Public domain (US NLM). Category
  ``health-lay``, source ``medlineplus``.
- ``openalex``: OpenAlex works whose best open-access location is CC BY or
  CC0, in English, with an abstract, sampled (``sample`` with ``seed``) from
  sociology and political science, history, economics and psychology. The
  abstract is rebuilt from ``abstract_inverted_index``. No email or key is
  sent, so requests use OpenAlex's shared keyless budget. Category
  ``abstract-social-humanities``, source the field.
- ``featured``: English Wikipedia Featured Articles listed under history,
  warfare and royalty (``history``), art, literature, theatre, music and media
  (``arts``) and every biographies section (``biography``) of
  Wikipedia:Featured articles, as TextExtracts plain text without headings and
  reference sections, cut after ``--cap`` words. CC BY-SA 4.0. Category
  ``wikipedia-featured``, source the topic.

USPTO patents were not added: PatentsView and the USPTO Open Data Portal need
an API key. Every request carries the project's User-Agent, and requests to
each host are at least a second apart (two for gutenberg.org). Writes
``manifest.json`` in the schema of scripts/fetch_eval_corpus.py. The text
stays under the output directory, outside the repository.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from domain_text import (  # the parsers, kept apart so tests need no network
    cap_paragraphs,
    clean_wiki,
    featured_topic,
    federal_register_text,
    gutenberg_body,
    lead_opinion,
    literature_kind,
    medline_topics,
    opinion_paragraphs,
    passages,
    rebuild_abstract,
    uk_notes_paragraphs,
    unwrap_paragraphs,
    words,
)

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
GAP = {"www.gutenberg.org": 2.0}
_last: dict[str, float] = {}
PARTS = ("literature", "news", "federal-register", "uk-notes", "courts", "medlineplus", "openalex", "featured")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
OPENALEX_FIELDS = {"sociology": "primary_topic.subfield.id:3312", "history": "primary_topic.subfield.id:1202",
                   "economics": "primary_topic.field.id:20", "psychology": "primary_topic.field.id:32"}
OPENALEX_LICENCES = {"cc-by": "CC-BY", "cc0": "CC0-1.0"}


def get(url: str, timeout: int = 120) -> bytes | None:
    """GET with the project's User-Agent, at least a second after the previous request to the host; None on 404."""
    host = urllib.parse.urlsplit(url).netloc
    for attempt in range(3):
        wait = _last.get(host, 0.0) + GAP.get(host, 1.0) - time.monotonic()
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


def wiki_extract(host: str, title: str) -> dict | None:
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "extracts|revisions",
                                "explaintext": 1, "rvprop": "ids", "redirects": 1, "format": "json",
                                "formatversion": 2})
    pages = get_json(f"https://{host}/w/api.php?{q}").get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "revisions" not in pages[0]:
        return None
    p = pages[0]
    return {"title": p["title"], "pageid": p["pageid"], "revid": p["revisions"][0]["revid"],
            "extract": p.get("extract", "")}


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--parts", default=",".join(PARTS))
    ap.add_argument("--novels", type=int, default=45, help="books")
    ap.add_argument("--essays", type=int, default=30, help="books")
    ap.add_argument("--per-book", type=int, default=2)
    ap.add_argument("--n", type=int, default=120, help="items per part (literature: see --novels, --essays)")
    ap.add_argument("--cap", type=int, default=2000, help="words kept from long documents")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    parts = set(args.parts.split(","))
    if parts - set(PARTS):
        ap.error(f"unknown parts: {sorted(parts - set(PARTS))}")
    rng = random.Random(args.seed)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path = out / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"entries": [], "failures": []}
    entries = [e for e in old["entries"] if e.get("part") not in parts]
    failures = [f for f in old["failures"] if f.get("part") not in parts]

    def fail(part: str, item, reason: str) -> None:
        failures.append({"part": part, "item": str(item), "reason": reason})

    def record(part, category, source, item_id, url, text, fmt, licence, via, **extra) -> None:
        ext = {"text": "txt", "html": "html"}[fmt]
        rel = f"{category}/{source}/{re.sub(r'[^A-Za-z0-9._-]+', '_', str(item_id))}.{ext}"
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        entries.append({"id": f"{category}/{source}/{item_id}", "category": category, "source": source,
                        "part": part, "author": "", "url": url, "path": rel, "format": fmt, "license": licence,
                        "fetched_at": now, "via": via, **extra,
                        "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})

    if "literature" in parts:
        raw = get("https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz")
        rows = list(csv.DictReader(io.StringIO(gzip.decompress(raw).decode("utf-8"))))
        pools: dict[str, list[dict]] = {"novel": [], "essay": []}
        for row in rows:
            kind = literature_kind(row)
            if kind:
                pools[kind].append(row)
        for kind, want in (("novel", args.novels), ("essay", args.essays)):
            pool = pools[kind]
            rng.shuffle(pool)
            books, authors = 0, set()
            for row in pool:
                if books >= want:
                    break
                author = row["Authors"].split(";")[0]
                if author in authors:      # one book per author
                    continue
                n = row["Text#"]
                body = get(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt")
                text = body.decode("utf-8", errors="replace") if body else ""
                inner = gutenberg_body(text) if text else None
                if not inner:
                    fail("literature", n, "no text or no START/END lines")
                    continue
                if "copyright" in text[:text.find(inner)].lower():   # Gutenberg's header flags copyrighted books
                    fail("literature", n, "Gutenberg header mentions copyright")
                    continue
                got = passages(unwrap_paragraphs(inner), rng, args.per_book)
                if not got:
                    fail("literature", n, "no passage of 400 to 800 words")
                    continue
                authors.add(author)
                books += 1
                for i, p in enumerate(got):
                    record("literature", "literature", kind, f"pg{n}-{i}", f"https://www.gutenberg.org/ebooks/{n}",
                           p, "text", "Public domain (US)", f"gutenberg.org/cache/epub/{n}/pg{n}.txt",
                           title=row["Title"].replace("\n", " "), creator=author, issued=row["Issued"],
                           book=n)
            print(f"literature {kind}: {books} books of {len(pool)} eligible", file=sys.stderr)

    if "news" in parts:
        rights = get_json("https://en.wikinews.org/w/api.php?action=query&meta=siteinfo&siprop=rightsinfo"
                          "&format=json&formatversion=2")["query"]["rightsinfo"]
        licence = {"Creative Commons Attribution 4.0": "CC-BY-4.0",
                   "Creative Commons Attribution 2.5": "CC-BY-2.5"}.get(rights["text"], rights["text"])
        start = datetime(2005, 1, 1).toordinal()
        days = [datetime.fromordinal(start + rng.randrange(datetime(2025, 1, 1).toordinal() - start))
                for _ in range(args.n * 4)]
        got, seen = 0, set()
        for day in days:
            if got >= args.n:
                break
            q = urllib.parse.urlencode({"action": "query", "list": "categorymembers",
                                        "cmtitle": f"Category:{MONTHS[day.month - 1]} {day.day}, {day.year}",
                                        "cmnamespace": 0, "cmlimit": 200, "format": "json", "formatversion": 2})
            members = get_json(f"https://en.wikinews.org/w/api.php?{q}").get("query", {}).get("categorymembers", [])
            rng.shuffle(members)
            took = 0
            for mem in members:
                if took >= 2 or got >= args.n:
                    break
                if mem["title"] in seen:
                    continue
                seen.add(mem["title"])
                p = wiki_extract("en.wikinews.org", mem["title"])
                text = clean_wiki(p["extract"], dateline=True) if p else ""
                if words(text) < 150:
                    fail("news", mem["title"], "under 150 words")
                    continue
                record("news", "news", "wikinews", p["pageid"],
                       f"https://en.wikinews.org/w/index.php?oldid={p['revid']}", text, "text", licence,
                       "en.wikinews.org TextExtracts explaintext", title=p["title"], revid=p["revid"],
                       date=day.date().isoformat())
                took += 1
                got += 1
        print(f"news: {got} articles ({len(seen)} tried); licence per rightsinfo: {rights['text']}", file=sys.stderr)

    if "federal-register" in parts:
        cells = [(y, t) for y in range(2001, 2026) for t in ("RULE", "PRORULE", "NOTICE")]
        rng.shuffle(cells)
        got = 0
        for y, t in cells:
            if got >= args.n:
                break
            base = {"per_page": 20, "conditions[type][]": t, "conditions[publication_date][year]": y,
                    "fields[]": ["document_number", "raw_text_url", "html_url", "title", "type", "publication_date",
                                 "agencies"]}
            q = urllib.parse.urlencode(base | {"page": 1}, doseq=True)
            first = get_json(f"https://www.federalregister.gov/api/v1/documents.json?{q}")
            pages = min(first.get("total_pages") or 0, 50)
            if not pages:
                continue
            q = urllib.parse.urlencode(base | {"page": rng.randrange(pages) + 1}, doseq=True)
            docs = get_json(f"https://www.federalregister.gov/api/v1/documents.json?{q}").get("results", [])
            rng.shuffle(docs)
            for d in docs[:4]:
                if got >= args.n:
                    break
                raw = get(d["raw_text_url"]) if d.get("raw_text_url") else None
                if not raw:
                    fail("federal-register", d["document_number"], "no plain text")
                    continue
                paras = federal_register_text(raw.decode("utf-8", errors="replace")).split("\n\n")
                text = "\n\n".join(cap_paragraphs(paras, args.cap)) + "\n"
                if words(text) < 150:
                    fail("federal-register", d["document_number"], "under 150 words")
                    continue
                record("federal-register", "regulation", "federal-register", d["document_number"], d["html_url"],
                       text, "text", "Public domain (US government work)", "federalregister.gov API raw_text_url",
                       doc_type=d.get("type"), date=d.get("publication_date"), title=d.get("title"),
                       agency=", ".join(a.get("name") or "" for a in d.get("agencies") or []))
                got += 1
        print(f"federal-register: {got} documents", file=sys.stderr)

    if "uk-notes" in parts:
        acts = []
        for y in range(2000, 2026):
            feed = get(f"https://www.legislation.gov.uk/ukpga/{y}/data.feed")
            if not feed:
                continue
            root = ET.fromstring(feed)
            ids = [e.findtext("{http://www.w3.org/2005/Atom}id") for e in root.iter("{http://www.w3.org/2005/Atom}entry")]
            acts += [i.replace("http://www.legislation.gov.uk/id/", "") for i in ids if i and "/id/ukpga/" in i]
        rng.shuffle(acts)
        got = 0
        for act in acts:
            if got >= args.n:
                break
            xml = get(f"https://www.legislation.gov.uk/{act}/notes/data.xml")
            if not xml:
                fail("uk-notes", act, "no explanatory notes")
                continue
            try:
                title, paras = uk_notes_paragraphs(xml)
            except ET.ParseError:
                fail("uk-notes", act, "XML parse error")
                continue
            text = "\n\n".join(cap_paragraphs(paras, args.cap)) + "\n"
            if words(text) < 150:
                fail("uk-notes", act, "under 150 words")
                continue
            record("uk-notes", "regulation", "uk-explanatory-notes", act,
                   f"https://www.legislation.gov.uk/{act}/notes", text, "text", "OGL-UK-3.0",
                   "legislation.gov.uk notes/data.xml", title=title)
            got += 1
        print(f"uk-notes: {got} of {len(acts)} acts listed (first feed page per year)", file=sys.stderr)

    if "courts" in parts:
        ds = "dataset=harvard-lil/cold-cases&config=default&split=train"
        total = get_json(f"https://datasets-server.huggingface.co/size?{ds.split('&')[0]}")["size"]["dataset"]["num_rows"]
        got, tried = 0, 0
        while got < args.n and tried < args.n * 5:
            tried += 1
            off = rng.randrange(total)
            rows = get_json(f"https://datasets-server.huggingface.co/rows?{ds}&offset={off}&length=1").get("rows", [])
            if not rows:
                fail("courts", off, "no row")
                continue
            row = rows[0]["row"]
            op = lead_opinion(row)
            if not op:
                fail("courts", row.get("id"), "no single lead opinion")
                continue
            text = "\n\n".join(cap_paragraphs(opinion_paragraphs(op["opinion_text"]), args.cap)) + "\n"
            if words(text) < 150:
                fail("courts", row.get("id"), "under 150 words")
                continue
            court_type = {"F": "federal", "S": "state", "SA": "state-appellate", "FB": "federal-bankruptcy",
                          "FS": "federal-special", "ST": "state-trial"}.get(row.get("court_type"), "other")
            record("courts", "court-opinion", court_type, row["id"],
                   f"https://www.courtlistener.com/opinion/{row['id']}/{row.get('slug') or ''}/", text, "text",
                   "CC0-1.0 (public domain)", f"datasets-server harvard-lil/cold-cases offset {off}",
                   court=row.get("court_full_name"), date=row.get("date_filed"), case=row.get("case_name"),
                   opinion_id=op.get("opinion_id"))
            got += 1
        print(f"courts: {got} lead opinions from {tried} random rows", file=sys.stderr)

    if "medlineplus" in parts:
        page = (get("https://medlineplus.gov/xml.html") or b"").decode()
        names = sorted(set(re.findall(r"xml/mplus_topics_\d{4}-\d{2}-\d{2}\.xml", page)))
        url = f"https://medlineplus.gov/{names[-1]}"
        topics = medline_topics(get(url, timeout=300))
        rng.shuffle(topics)
        got = 0
        for t in topics:
            if got >= args.n:
                break
            if words(html.unescape(re.sub(r"<[^>]+>", " ", t["summary"]))) < 150:
                fail("medlineplus", t["id"], "under 150 words")
                continue
            record("medlineplus", "health-lay", "medlineplus", t["id"], t["url"], t["summary"] + "\n", "html",
                   "Public domain (US NLM)", names[-1], title=t["title"])
            got += 1
        print(f"medlineplus: {got} of {len(topics)} English topics", file=sys.stderr)

    if "openalex" in parts:
        per = -(-args.n // len(OPENALEX_FIELDS))
        for field, flt in OPENALEX_FIELDS.items():
            q = urllib.parse.urlencode({
                "filter": f"{flt},best_oa_location.license:cc-by|cc0,has_abstract:true,language:en,type:article",
                "sample": per * 2, "seed": args.seed, "per_page": per * 2,
                "select": "id,doi,title,publication_year,best_oa_location,abstract_inverted_index,primary_topic"})
            works = get_json(f"https://api.openalex.org/works?{q}").get("results", [])
            got = 0
            for w in works:
                if got >= per:
                    break
                lic = OPENALEX_LICENCES.get((w.get("best_oa_location") or {}).get("license"))
                if not lic:
                    fail("openalex", w["id"], "licence not CC BY or CC0")
                    continue
                text = rebuild_abstract(w.get("abstract_inverted_index"))
                if words(text) < 100:
                    fail("openalex", w["id"], "abstract under 100 words")
                    continue
                loc = w["best_oa_location"]
                record("openalex", "abstract-social-humanities", field, w["id"].rsplit("/", 1)[-1],
                       w.get("doi") or loc.get("landing_page_url") or w["id"], text + "\n", "text", lic,
                       "api.openalex.org works abstract_inverted_index", title=w.get("title"),
                       year=w.get("publication_year"),
                       subfield=((w.get("primary_topic") or {}).get("subfield") or {}).get("display_name"))
                got += 1
            print(f"openalex {field}: {got} of {len(works)} sampled", file=sys.stderr)

    if "featured" in parts:
        fa = "Wikipedia:Featured articles"
        q = urllib.parse.urlencode({"action": "parse", "page": fa, "prop": "sections", "format": "json",
                                    "formatversion": 2})
        sections = get_json(f"https://en.wikipedia.org/w/api.php?{q}")["parse"]["sections"]
        pools: dict[str, list[str]] = {"history": [], "arts": [], "biography": []}
        for s in sections:
            topic = featured_topic(re.sub(r"<[^>]+>", "", s["line"]))
            if not topic:
                continue
            q = urllib.parse.urlencode({"action": "parse", "page": fa, "section": s["index"], "prop": "links",
                                        "format": "json", "formatversion": 2})
            links = get_json(f"https://en.wikipedia.org/w/api.php?{q}").get("parse", {}).get("links", [])
            pools[topic] += [lk["title"] for lk in links if lk.get("ns") == 0 and lk.get("exists")]
        per = -(-args.n // len(pools))
        seen: set[str] = set()
        for topic, titles in pools.items():
            titles = sorted(set(titles) - seen)
            rng.shuffle(titles)
            got = 0
            for title in titles:
                if got >= per:
                    break
                seen.add(title)
                p = wiki_extract("en.wikipedia.org", title)
                text = clean_wiki(p["extract"]) if p else ""
                if words(text) < 150:
                    fail("featured", title, "missing or under 150 words")
                    continue
                full = words(text)
                text = "\n".join(cap_paragraphs(text.split("\n"), args.cap)).strip() + "\n"
                record("featured", "wikipedia-featured", topic, p["pageid"],
                       f"https://en.wikipedia.org/w/index.php?oldid={p['revid']}", text, "text", "CC-BY-SA-4.0",
                       "en.wikipedia.org TextExtracts explaintext", title=p["title"], revid=p["revid"],
                       words_full=full)
                got += 1
            print(f"featured {topic}: {got} of {len(titles)} listed", file=sys.stderr)

    manifest_path.write_text(json.dumps(
        {"description": "non-technical domain samples; see scripts/fetch_domains.py", "generated_at": now,
         "seed": args.seed, "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "texts;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
