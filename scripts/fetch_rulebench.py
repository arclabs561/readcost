"""Rebuild the per-rule benchmark's sentences from their sources.

    python3 scripts/fetch_rulebench.py OUT_DIR

eval/rulebench/rulebench.jsonl holds references, not text: each item has
its rule, expected outcome, source URL, licence, label and the SHA-256 of
its sentence with whitespace collapsed. Only text this repository owns (the
rule examples in src/readcost/features.py) is stored inline. This script
downloads each source (PEPs from python/peps at a pinned commit, GitHub files
at the commit in their URL), extracts sentences the way readcost reads them,
and writes OUT_DIR/rulebench.jsonl with the text of every item whose hash it
finds. scripts/rulebench.py reads that file. Items it cannot find are listed
and left out.
"""

import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

from readcost import Analyzer, Config
from readcost.extract import detect_format, extract
from readcost.features import Context, show

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))  # for fetch_eval_corpus.html_to_markdown
BENCH = ROOT / "eval/rulebench/rulebench.jsonl"
PEPS_COMMIT = "362ca9d17dc2c80ea4af4e3128f9569d8763a3c4"  # scripts/fetch_peps.py run of 2026-10-27


def sentence_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def fetch_url(source: str) -> tuple[str, str]:
    """(URL to download, path that decides the format)."""
    m = re.match(r"https://peps\.python\.org/pep-(\d{4})/?$", source)
    if m:
        path = f"peps/pep-{m.group(1)}.rst"
        return f"https://raw.githubusercontent.com/python/peps/{PEPS_COMMIT}/{path}", path
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/blob/(.+)$", source)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}", m.group(2)
    return source, source.split("?")[0].rstrip("/") + ".html"


def readings(raw: bytes, url: str, path: str) -> list[tuple[str, str]]:
    """(text, format) pairs to read, matching how the evaluation corpus read each source.

    Django's docs are reStructuredText in .txt files. A web page is read both
    as HTML and as the Markdown that scripts/fetch_eval_corpus.py made with
    trafilatura, since the benchmark took sentences from either.
    """
    text = raw.decode("utf-8", "ignore")
    if path.endswith(".html") and not url.startswith("https://raw.githubusercontent.com/"):
        out = [(text, "html")]
        try:
            from fetch_eval_corpus import html_to_markdown

            md = html_to_markdown(raw, url)
            if md:
                out.append((md, "markdown"))
        except ImportError:
            print("trafilatura is not installed; reading web pages as HTML only", file=sys.stderr)
        return out
    if "django/django" in url and path.endswith(".txt"):
        return [(text, "rst")]
    return [(text, detect_format(path, text))]


def sentences(analyzer: Analyzer, source: str) -> dict[str, str]:
    url, path = fetch_url(source)
    req = urllib.request.Request(url, headers={"User-Agent": "readcost-rulebench"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
    out = {}
    for text, fmt in readings(raw, source, path):
        for seg in extract(text, path, fmt):
            ctx.codes = seg.codes
            for sent in analyzer.nlp(seg.text).sents:
                shown = show(ctx, sent.doc, sent.start, sent.end - 1)
                out[sentence_hash(shown)] = shown
    return out


def main(out_dir: Path) -> int:
    items = [json.loads(x) for x in BENCH.read_text().splitlines()]
    analyzer = Analyzer(Config())
    cache: dict[str, dict[str, str]] = {}
    rows, missing = [], []
    for item in items:
        if "text" in item:  # this repository's own text
            rows.append(item)
            continue
        src = item["source"]
        if src not in cache:
            try:
                cache[src] = sentences(analyzer, src)
            except OSError as exc:
                print(f"{src}: {exc}", file=sys.stderr)
                cache[src] = {}
        text = cache[src].get(item["sha256"])
        if text is None:
            missing.append(item)
            continue
        rows.append(item | {"text": text})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rulebench.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} of {len(items)} items -> {out_dir / 'rulebench.jsonl'}")
    for item in missing:
        print(f"not found: {item['rule']} {item['source']} {item['sha256'][:12]}", file=sys.stderr)
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
