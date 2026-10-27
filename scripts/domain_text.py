"""Text extraction for scripts/fetch_domains.py: no network, so the tests can run it.

Each function turns one source's raw form (Gutenberg plain text, MediaWiki
extracts, Federal Register text, legislation.gov.uk XML, court opinions,
MedlinePlus XML, OpenAlex inverted indexes) into prose paragraphs.
"""

from __future__ import annotations

import html
import random
import re
import xml.etree.ElementTree as ET

WIKI_END = ("see also", "references", "notes", "sources", "further reading", "external links", "related news",
            "footnotes", "bibliography", "citations", "works cited", "explanatory notes", "interview")

def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))


def cap_paragraphs(paras: list[str], cap: int) -> list[str]:
    """Leading paragraphs up to the first paragraph end at or after ``cap`` words."""
    out, n = [], 0
    for p in paras:
        if n >= cap:
            break
        out.append(p)
        n += words(p)
    return out


# ------------------------------------------------------------------ Gutenberg

def gutenberg_body(text: str) -> str | None:
    """The book between the ``*** START OF`` and ``*** END OF`` lines, or None without them."""
    start = re.search(r"^\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG.*$", text, re.MULTILINE | re.IGNORECASE)
    end = re.search(r"^\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG.*$", text, re.MULTILINE | re.IGNORECASE)
    if not start or not end or end.start() <= start.end():
        return None
    return text[start.end():end.start()]


def unwrap_paragraphs(body: str) -> list[str]:
    """Blank-line-separated paragraphs with hard line breaks joined; headings, rules and short lines dropped."""
    out = []
    for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n")):
        p = re.sub(r"\s+", " ", block).strip()
        if words(p) < 8 or p.upper() == p or re.fullmatch(r"[\W\d_]+", p):
            continue
        out.append(p.replace("_", ""))
    return out


def passages(paras: list[str], rng: random.Random, k: int, lo: int = 400, hi: int = 800) -> list[str]:
    """Up to ``k`` non-overlapping runs of whole paragraphs of ``lo`` to ``hi`` words from the middle 80%."""
    n = len(paras)
    starts = list(range(n // 10, n - n // 10))
    rng.shuffle(starts)
    used: set[int] = set()
    out = []
    for s in starts:
        if len(out) >= k:
            break
        run, total, i = [], 0, s
        while i < n and total < lo and i not in used:
            run.append(i)
            total += words(paras[i])
            i += 1
        if lo <= total <= hi:
            used.update(run)
            out.append("\n\n".join(paras[j] for j in run) + "\n")
    return out


def author_years(authors: str) -> tuple[int, int] | None:
    """Birth and death years of the first author in a catalog ``Authors`` field like ``Austen, Jane, 1775-1817``."""
    m = re.search(r"(\d{4})\??-(\d{4})", authors)
    return (int(m.group(1)), int(m.group(2))) if m else None


def literature_kind(row: dict) -> str | None:
    """``novel`` or ``essay`` for an eligible catalog row, else None."""
    if row.get("Language") != "en" or row.get("Type") != "Text":
        return None
    if not re.match(r"P[RS]", row.get("LoCC", "")):
        return None
    years = author_years(row.get("Authors", ""))
    if not years or not (1770 <= years[0] <= 1880 and years[1] <= 1945):
        return None
    subjects = row.get("Subjects", "")
    if re.search(r"\bessays\b", subjects, re.IGNORECASE):
        return "essay"
    if re.search(r"\bFiction\b", subjects) and not re.search(r"Juvenile|Poetry|Drama|Short stories", subjects):
        return "novel"
    return None


# ------------------------------------------------------------------ Wikimedia

def clean_wiki(text: str, dateline: bool = False) -> str:
    """TextExtracts plain text without headings and from the first reference-like section on."""
    keep = []
    for line in text.splitlines():
        m = re.fullmatch(r"\s*(=+)\s*(.*?)\s*\1\s*", line)
        if m:
            if m.group(2).lower() in WIKI_END:
                break
            continue
        keep.append(line.strip())
    if dateline:
        while keep and not keep[0]:
            keep.pop(0)
        if keep and re.fullmatch(r"(\w+day, )?\w+ \d{1,2}, \d{4}", keep[0]):
            keep.pop(0)
    body = "\n".join(keep)
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def featured_topic(section: str) -> str | None:
    """The topic of a Wikipedia:Featured articles section heading, or None to skip it."""
    s = section.lower()
    if "biograph" in s or s in ("individuals", "groups"):
        return "biography"
    if s in ("history", "warfare", "military equipment", "military ships", "military units",
             "wars, battles and events", "royalty and nobility", "archaeology"):
        return "history"
    if s in ("art, architecture, and archaeology", "architecture", "art", "funerary art and memorials", "paintings",
             "literature and theatre", "autobiographies and memoirs", "novels, including graphic novels", "poetry",
             "short stories", "theatre", "music", "classical music works", "albums", "songs", "films",
             "20th century (1900–1999)", "21st century (2000–2099)", "media"):
        return "arts"
    return None


# ------------------------------------------------------------------ law

def federal_register_text(raw: str) -> str:
    """Paragraphs of a GPO plain-text Federal Register document from SUPPLEMENTARY INFORMATION on.

    Without that heading, the text after the first dashed rule (the end of the GPO header).
    """
    text = re.sub(r"(?is)<title>.*?</title>", "", raw)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\n[ \t]*\n?[ \t]*\[\[Page \d+\]\][ \t]*\n(?:[ \t]*\n)?", "\n", text)   # page breaks fall mid-paragraph
    m = (re.search(r"^SUPPLEMENTARY INFORMATION:\s*", text, re.MULTILINE)
         or re.search(r"^-{20,}\s*$", text, re.MULTILINE))
    if m:
        text = text[m.end():]
    paras = re.split(r"\n\s*\n|\n(?=    \S)", text)
    out = []
    for p in paras:
        p = re.sub(r"\s+", " ", p).strip()
        if not p or re.fullmatch(r"[-_=\s]+", p) or p.startswith("[FR Doc"):
            continue
        if p.startswith("BILLING CODE"):
            break
        out.append(p)
    return "\n\n".join(out)


LEG = "{http://www.legislation.gov.uk/namespaces/legislation}"


def uk_notes_paragraphs(xml: bytes) -> tuple[str, list[str]]:
    """(title, paragraphs) of a legislation.gov.uk explanatory notes document."""
    root = ET.fromstring(xml)
    title = next((e.text or "" for e in root.iter() if e.tag.endswith("}title")), "")
    paras = []
    for t in root.iter(f"{LEG}Text"):
        s = re.sub(r"\s+", " ", "".join(t.itertext())).strip()
        if s:
            paras.append(s)
    return title.strip(), paras


def lead_opinion(row: dict) -> dict | None:
    """The single lead (majority) opinion of a COLD Cases row, or None."""
    leads = [o for o in row.get("opinions") or [] if o.get("type") == "020lead" and (o.get("opinion_text") or "").strip()]
    return leads[0] if len(leads) == 1 else None


def opinion_paragraphs(text: str) -> list[str]:
    """Paragraphs of an opinion, without the ``*123`` star-page markers of the printed reporter."""
    text = re.sub(r"(?<!\S)\*\d+(?=\S|\s)", "", text)
    paras = re.split(r"\n\s*\n|\n(?=\s{2,}\S)|\n", text)
    return [re.sub(r"\s+", " ", p).strip() for p in paras if words(p) >= 3]


# ------------------------------------------------------------------ health and scholarship

def medline_topics(xml: bytes) -> list[dict]:
    """English health topics in a MedlinePlus XML file: id, title, url and full-summary HTML."""
    root = ET.fromstring(xml)
    out = []
    for t in root.iter("health-topic"):
        if t.get("language") != "English":
            continue
        out.append({"id": t.get("id"), "title": t.get("title"), "url": t.get("url"),
                    "summary": t.findtext("full-summary") or ""})
    return out


def rebuild_abstract(index: dict[str, list[int]] | None) -> str:
    """Abstract text from an OpenAlex ``abstract_inverted_index``, with a leading "Abstract" label removed."""
    if not index:
        return ""
    pos = sorted((i, w) for w, idx in index.items() for i in idx)
    text = " ".join(w for _, w in pos)
    return re.sub(r"^(abstract)\b[\s.:]*", "", text, flags=re.IGNORECASE).strip()
