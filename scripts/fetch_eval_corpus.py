# /// script
# requires-python = ">=3.11"
# dependencies = ["trafilatura>=1.12"]
# ///
"""Fetch the evaluation corpus into a local directory and write its manifest.

    uv run scripts/fetch_eval_corpus.py ref/eval

The corpus is third-party text under its owners' licenses. It stays on the
local disk and is never committed; only the manifest's metadata and short
quoted examples in docs/evaluation.md leave it. Fetched pages are data:
nothing in them is executed or followed.

Every source is pinned: web pages by URL, GitHub files by the commit SHA
resolved at fetch time, Hacker News and Stack Overflow by item ID. A rerun
skips files that already exist, so the manifest stays stable unless
``--refresh`` is given. ``--ref-root`` points at the READMEs and Go commit
messages fetched earlier (``readme/`` and ``commit/``), which are listed in
the manifest without being copied.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

UA = "readcost-eval/0.1 (+https://github.com/arclabs561/readcost; research corpus)"
CPYTHON_LIB = "/opt/homebrew/opt/python@3.15/Frameworks/Python.framework/Versions/3.15/lib/python3.15"

# ------------------------------------------------------------------ sources
# (author or site, license note, [URLs]). Chosen for writers and docs that
# are widely cited for clear technical prose; post URLs were picked from each
# author's feed or archive on 2026-10-26, preferring essays over link posts.

ESSAYS: dict[str, tuple[str, str, list[str]]] = {
    "paul-graham": ("Paul Graham", "copyright Paul Graham; all rights reserved", [
        f"https://paulgraham.com/{p}.html" for p in (
            "greatwork", "ds", "startupideas", "makersschedule", "avg", "hp",
            "wealth", "gh", "say", "writing44", "simply", "words", "useful", "taste")]),
    "julia-evans": ("Julia Evans", "copyright Julia Evans", [
        "https://jvns.ca/blog/2026/07/17/learning-about-running-sqlite/",
        "https://jvns.ca/blog/2026/05/15/moving-away-from-tailwind--and-learning-to-structure-my-css-/",
        "https://jvns.ca/blog/2026/02/18/man-pages/",
        "https://jvns.ca/blog/2026/01/27/some-notes-on-starting-to-use-django/",
        "https://jvns.ca/blog/2026/01/08/a-data-model-for-git/",
        "https://jvns.ca/blog/2025/10/10/notes-on-switching-to-helix-from-vim/",
        "https://jvns.ca/blog/2025/06/10/how-to-compile-a-c-program/",
        "https://jvns.ca/blog/2025/02/13/how-to-add-a-directory-to-your-path/",
        "https://jvns.ca/blog/2025/02/05/some-terminal-frustrations/",
        "https://jvns.ca/blog/2024/11/26/terminal-rules/",
    ]),
    "dan-luu": ("Dan Luu", "copyright Dan Luu", [
        f"https://danluu.com/{p}/" for p in (
            "ambitious", "brain-off", "bug-blind", "no-slow", "ai-coding",
            "slow-device", "diseconomies-scale", "impossible-agree", "why-video")]),
    "simon-willison": ("Simon Willison", "copyright Simon Willison", [
        "https://simonwillison.net/2026/Oct/12/python-3-15/",
        "https://simonwillison.net/2026/Oct/9/built-using-my-voice/",
        "https://simonwillison.net/2026/Oct/3/default-hard-budget-caps/",
        "https://simonwillison.net/2026/Sep/27/2026-in-llms-so-far/",
        "https://simonwillison.net/2026/Sep/21/jev/",
        "https://simonwillison.net/2026/Sep/8/on-navier-stokes/",
        "https://simonwillison.net/2026/Sep/4/rogue-agent-wikis/",
        "https://simonwillison.net/2026/Sep/2/claudes-new-system-prompt/",
        "https://simonwillison.net/2026/Sep/12/openai-agents-rubygems/",
    ]),
    "russ-cox": ("Russ Cox", "copyright Russ Cox", [
        f"https://research.swtch.com/{p}" for p in (
            "bisect", "testing", "nih", "ub", "sample", "deps", "dogma",
            "boolean", "gochanges", "xz-timeline")]),
    "raymond-chen": ("Raymond Chen", "copyright Microsoft", [
        "https://devblogs.microsoft.com/oldnewthing/20261023-00/?p=112793",
        "https://devblogs.microsoft.com/oldnewthing/20261022-00/?p=112791",
        "https://devblogs.microsoft.com/oldnewthing/20261021-00/?p=112786",
        "https://devblogs.microsoft.com/oldnewthing/20261020-00/?p=112784",
        "https://devblogs.microsoft.com/oldnewthing/20261019-00/?p=112781",
        "https://devblogs.microsoft.com/oldnewthing/20261016-00/?p=112778",
        "https://devblogs.microsoft.com/oldnewthing/20261015-00/?p=112776",
        "https://devblogs.microsoft.com/oldnewthing/20261014-00/?p=112774",
        "https://devblogs.microsoft.com/oldnewthing/20261013-00/?p=112769",
        "https://devblogs.microsoft.com/oldnewthing/20261012-00/?p=112767",
    ]),
    "hillel-wayne": ("Hillel Wayne", "copyright Hillel Wayne", [
        f"https://www.hillelwayne.com/post/{p}/" for p in (
            "predicate-logic", "lfp", "pizza", "z3-examples", "algdt-history",
            "toolbox-languages", "composing-tla", "software-friction",
            "alloy-facts", "tale-of-daniel")]),
    "joel-spolsky": ("Joel Spolsky", "copyright Joel Spolsky", [
        "https://www.joelonsoftware.com/2000/08/09/the-joel-test-12-steps-to-better-code/",
        "https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/",
        "https://www.joelonsoftware.com/2002/11/11/the-law-of-leaky-abstractions/",
        "https://www.joelonsoftware.com/2001/04/21/dont-let-architecture-astronauts-scare-you/",
        "https://www.joelonsoftware.com/2000/10/02/painless-functional-specifications-part-1-why-bother/",
        "https://www.joelonsoftware.com/2005/05/11/making-wrong-code-look-wrong/",
        "https://www.joelonsoftware.com/2018/04/23/strange-and-maddening-rules/",
        "https://www.joelonsoftware.com/2018/04/13/gamification/",
        "https://www.joelonsoftware.com/2019/12/05/so-hows-that-retirement-thing-going-anyway/",
    ]),
    "martin-fowler": ("Martin Fowler", "copyright Martin Fowler", [
        "https://martinfowler.com/bliki/TechnicalDebt.html",
        "https://martinfowler.com/articles/is-quality-worth-cost.html",
        "https://martinfowler.com/bliki/StranglerFigApplication.html",
        "https://martinfowler.com/bliki/Yagni.html",
        "https://martinfowler.com/articles/practitioner-voice.html",
        "https://martinfowler.com/articles/healthy-peer-feedback.html",
        "https://martinfowler.com/articles/2026-dont-like-llms.html",
        "https://martinfowler.com/bliki/SensibleDefault.html",
        "https://martinfowler.com/articles/never-send-slides/slide-principles.html",
        "https://martinfowler.com/articles/are-harnesses-worth-the-cost.html",
    ]),
    "andrew-gallant": ("Andrew Gallant (BurntSushi)", "copyright Andrew Gallant", [
        f"https://burntsushi.net/{p}/" for p in (
            "regex-internals", "bstr", "unwrap", "foss", "csv", "ripgrep",
            "transducers", "rust-error-handling")]),
    "dan-abramov": ("Dan Abramov", "copyright Dan Abramov", [
        f"https://overreacted.io/{p}/" for p in (
            "how-to-fix-any-bug", "where-its-at", "open-social", "beyond-booleans",
            "the-math-is-haunted", "progressive-json", "one-roundtrip-per-navigation",
            "static-as-a-server", "a-social-filesystem")]),
    "brendan-gregg": ("Brendan Gregg", "copyright Brendan Gregg", [
        "https://www.brendangregg.com/blog/2025-11-17/third-stage-engineering.html",
        "https://www.brendangregg.com/blog/2025-08-04/when-to-hire-a-computer-performance-engineering-team-2025-part1.html",
        "https://www.brendangregg.com/blog/2025-05-22/3-years-of-extremely-remote-work.html",
        "https://www.brendangregg.com/blog/2025-05-01/doom-gpu-flame-graphs.html",
        "https://www.brendangregg.com/blog/2024-10-29/ai-flame-graphs.html",
        "https://www.brendangregg.com/blog/2024-07-22/no-more-blue-fridays.html",
        "https://www.brendangregg.com/blog/2025-11-22/intel-is-listening.html",
    ]),
    "eli-bendersky": ("Eli Bendersky", "copyright Eli Bendersky", [
        "https://eli.thegreenplace.net/2026/rusty-thoughts-on-parse-dont-validate/",
        "https://eli.thegreenplace.net/2026/monte-carlo-simulations/",
        "https://eli.thegreenplace.net/2026/notes-on-the-complex-roots-of-unity/",
    ]),
}

WEB_DOCS: dict[str, tuple[str, str, list[str]]] = {
    "sqlite-docs": ("SQLite", "public domain", [
        f"https://sqlite.org/{p}.html" for p in (
            "whentouse", "wal", "isolation", "atomiccommit", "quirks", "datatype3",
            "lockingv3", "testing", "about", "lang_transaction")]),
    "govuk-guidance": ("GOV.UK", "Open Government Licence v3.0", [
        "https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/",
        "https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide/",
        "https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/technical-a-to-z/",
        "https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/understand-content-design/",
        "https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/identify-user-needs/",
        "https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/plan-new-govuk-content/",
        "https://www.gov.uk/service-manual/design/writing-for-user-interfaces",
    ]),
}

# Pages that serve Markdown directly.
RAW_DOCS: dict[str, tuple[str, str, list[str]]] = {
    "stripe-docs": ("Stripe", "copyright Stripe", [
        f"https://docs.stripe.com/{p}.md" for p in (
            "api/idempotent_requests", "api/errors", "api/pagination", "webhooks",
            "keys", "payments/payment-intents", "payments/accept-a-payment",
            "testing", "rate-limits", "error-handling")]),
}

# (repo, branch, license, author label, format, [paths])
GITHUB: dict[str, tuple[str, str, str, str, str, list[str]]] = {
    "go-blog": ("golang/website", "master", "CC BY 4.0 (text)", "The Go Authors", "markdown", [
        f"_content/blog/{p}.md" for p in (
            "errors-are-values", "laws-of-reflection", "slices-intro", "strings",
            "pipelines", "context", "defer-panic-and-recover", "maps",
            "error-handling-and-go", "declaration-syntax", "module-compatibility",
            "using-go-modules", "package-names", "when-generics", "intro-generics",
            "range-functions", "loopvar-preview", "toolchain")]),
    "effective-go": ("golang/website", "master", "CC BY 4.0 (text)", "The Go Authors", "html", [
        "_content/doc/effective_go.html"]),
    "rust-book": ("rust-lang/book", "main", "MIT OR Apache-2.0", "Klabnik, Nichols, Krycho", "markdown", [
        f"src/{p}.md" for p in (
            "ch01-02-hello-world", "ch03-01-variables-and-mutability", "ch03-02-data-types",
            "ch04-01-what-is-ownership", "ch04-02-references-and-borrowing",
            "ch06-01-defining-an-enum", "ch08-01-vectors", "ch08-02-strings",
            "ch09-02-recoverable-errors-with-result", "ch09-03-to-panic-or-not-to-panic",
            "ch10-02-traits", "ch10-03-lifetime-syntax", "ch13-01-closures",
            "ch15-01-box", "ch16-01-threads", "ch16-03-shared-state")]),
    "python-tutorial": ("python/cpython", "main", "PSF-2.0", "Python documentation authors", "rst", [
        f"Doc/tutorial/{p}.rst" for p in (
            "appetite", "interpreter", "introduction", "controlflow", "datastructures",
            "modules", "inputoutput", "errors", "classes", "stdlib", "venv")]),
    "django-docs": ("django/django", "main", "BSD-3-Clause", "Django documentation authors", "rst", [
        f"docs/{p}.txt" for p in (
            "intro/overview", "intro/tutorial01", "intro/tutorial02", "intro/tutorial04",
            "topics/db/models", "topics/db/transactions", "topics/http/views",
            "topics/forms/index", "topics/testing/overview", "misc/design-philosophies",
            "misc/api-stability")]),
    "rust-std": ("rust-lang/rust", "main", "MIT OR Apache-2.0", "The Rust Project", "source", [
        "library/core/src/option.rs", "library/core/src/result.rs", "library/std/src/fs.rs",
        "library/core/src/cell.rs", "library/std/src/sync/poison/mutex.rs",
        "library/core/src/pin.rs"]),
}

CPYTHON_MODULES = [
    "json/__init__.py", "json/decoder.py", "pathlib/__init__.py", "functools.py",
    "subprocess.py", "argparse.py", "logging/__init__.py", "textwrap.py", "shutil.py",
    "heapq.py", "bisect.py", "contextlib.py", "dataclasses.py", "enum.py",
    "collections/__init__.py", "tempfile.py", "threading.py", "queue.py",
    "fractions.py", "statistics.py", "difflib.py", "csv.py", "secrets.py", "zipfile/__init__.py",
]

HN_STORIES = 60       # best stories considered
HN_PER_STORY = 2      # top-ranked live comments taken from each
SO_ANSWERS = 100      # highest-voted Stack Overflow answers


# ------------------------------------------------------------------ helpers

class Fetcher:
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.last: dict[str, float] = {}
        self.token = os.environ.get("GITHUB_TOKEN") or self._gh_token()

    @staticmethod
    def _gh_token() -> str | None:
        try:
            out = subprocess.run(["gh", "auth", "token"], check=False, capture_output=True, text=True, timeout=10)
            return out.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            return None

    def get(self, url: str, headers: dict | None = None) -> bytes:
        host = urllib.parse.urlsplit(url).netloc
        wait = self.delay - (time.monotonic() - self.last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
        finally:
            self.last[host] = time.monotonic()
        return body

    def github_sha(self, repo: str, branch: str) -> str:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.loads(self.get(f"https://api.github.com/repos/{repo}/commits/{branch}", headers))
        return data["sha"]


def slug(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:120]


def html_to_markdown(raw: bytes, url: str) -> str | None:
    import trafilatura

    # Precision mode drops pages laid out with tables and <font> tags (Paul
    # Graham's); fall back to the default, then to recall mode.
    doc = raw.decode("utf-8", errors="replace")
    best = None
    for mode in ({"favor_precision": True}, {}, {"favor_recall": True}):
        md = trafilatura.extract(
            doc, url=url, output_format="markdown", include_formatting=True,
            include_links=False, include_images=False, include_comments=False,
            include_tables=False, **mode)
        if md and len(md.split()) >= 100:
            return split_paragraphs(md)
        best = best or md
    return split_paragraphs(best) if best else best


END = re.compile(r"[.!?:)\"\u201d\u2019]$")
BLOCK_START = re.compile(r"^(#|[-*+] |\d+[.)] |>|\||```)")


def split_paragraphs(md: str) -> str:
    """Put a blank line after each line that ends a paragraph.

    trafilatura separates some sites' paragraphs (Paul Graham's, for one) by
    a single newline, which Markdown joins into one paragraph. A line that
    ends a sentence, or a short line such as a date, followed by a line that
    starts with a capital is taken to end its paragraph. Hard-wrapped lines
    inside a sentence end mid-clause and are left alone.
    """
    lines = md.splitlines()
    out: list[str] = []
    fenced = False
    for k, line in enumerate(lines):
        out.append(line)
        if line.startswith("```"):
            fenced = not fenced
        nxt = lines[k + 1] if k + 1 < len(lines) else ""
        if fenced or not line.strip() or not nxt.strip() or BLOCK_START.match(line) or BLOCK_START.match(nxt):
            continue
        short = len(line.split()) < 8 and not line.rstrip().endswith((",", "-", ";"))
        if (END.search(line.rstrip()) or short) and (nxt[:1].isupper() or nxt[:1] in "(\u201c\""):
            out.append("")
    return "\n".join(out) + "\n"


def html_fragment(body: str, title: str = "") -> str:
    """Wrap an HTML fragment (a comment or answer body) as a document."""
    head = f"<title>{html.escape(title)}</title>" if title else ""
    return f"<html><head>{head}</head><body>\n{body}\n</body></html>\n"


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--ref-root", type=Path, default=Path("ref"))
    ap.add_argument("--refresh", action="store_true", help="refetch files that already exist")
    ap.add_argument("--only", default="", help="comma-separated source ids to fetch")
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    old: dict[str, dict] = {}
    old_failures: list[dict] = []
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text())
        old = {e["id"]: e for e in prior["entries"]}
        old_failures = prior.get("failures", [])
    only = {s for s in args.only.split(",") if s}
    f = Fetcher()
    entries: dict[str, dict] = {}
    failures: list[dict] = []

    def want(source: str) -> bool:
        return not only or source in only

    def record(entry: dict, text: str | bytes | None) -> None:
        path = out / entry["path"]
        if text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = text.encode("utf-8") if isinstance(text, str) else text
            path.write_bytes(data)
        data = path.read_bytes()
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["bytes"] = len(data)
        entries[entry["id"]] = entry
        print(f"ok   {entry['id']}", file=sys.stderr)

    def reuse(eid: str) -> bool:
        """Keep an earlier fetch unless --refresh; True if reused."""
        e = old.get(eid)
        if e and not args.refresh and (out / e["path"]).exists():
            entries[eid] = e
            return True
        return False

    def fail(eid: str, url: str, err: object) -> None:
        failures.append({"id": eid, "url": url, "error": str(err)[:200]})
        print(f"FAIL {eid}: {err}", file=sys.stderr)

    # Essays and web docs: HTML pages reduced to Markdown by trafilatura.
    for category, table in (("essay", ESSAYS), ("docs", WEB_DOCS)):
        for source, (author, lic, urls) in table.items():
            if not want(source):
                continue
            for url in urls:
                eid = f"{source}/{slug(url)}"
                if reuse(eid):
                    continue
                try:
                    md = html_to_markdown(f.get(url), url)
                except (urllib.error.URLError, OSError, ValueError) as exc:
                    fail(eid, url, exc)
                    continue
                if not md or len(md.split()) < 100:
                    fail(eid, url, "extraction produced under 100 words")
                    continue
                record({"id": eid, "category": category, "source": source, "author": author,
                        "url": url, "path": f"{category}/{source}/{slug(url)}.md", "format": "markdown",
                        "license": lic, "fetched_at": now(), "via": "trafilatura markdown"}, md)

    for source, (author, lic, urls) in RAW_DOCS.items():
        if not want(source):
            continue
        for url in urls:
            eid = f"{source}/{slug(url)}"
            if reuse(eid):
                continue
            try:
                body = f.get(url).decode("utf-8", errors="replace")
            except (urllib.error.URLError, OSError) as exc:
                fail(eid, url, exc)
                continue
            if body.lstrip().startswith("<"):
                fail(eid, url, "served HTML, not Markdown")
                continue
            record({"id": eid, "category": "docs", "source": source, "author": author, "url": url,
                    "path": f"docs/{source}/{slug(url)}.md", "format": "markdown", "license": lic,
                    "fetched_at": now(), "via": "raw markdown"}, body)

    # GitHub files at a pinned commit.
    shas: dict[tuple[str, str], str] = {}
    ext = {"markdown": ".md", "rst": ".rst", "html": ".html"}
    for source, (repo, branch, lic, author, fmt, paths) in GITHUB.items():
        if not want(source):
            continue
        category = "code" if fmt == "source" else "docs"
        for p in paths:
            eid = f"{source}/{p}"
            if reuse(eid):
                continue
            try:
                if (repo, branch) not in shas:
                    shas[(repo, branch)] = f.github_sha(repo, branch)
                sha = shas[(repo, branch)]
                url = f"https://raw.githubusercontent.com/{repo}/{sha}/{p}"
                body = f.get(url)
            except (urllib.error.URLError, OSError, KeyError) as exc:
                fail(eid, f"{repo}:{p}", exc)
                continue
            name = p.replace("/", "__")
            if fmt != "source":
                name = re.sub(r"\.(md|txt|rst|html)$", "", name) + ext[fmt]
            record({"id": eid, "category": category, "source": source, "author": author,
                    "url": f"https://github.com/{repo}/blob/{sha}/{p}", "path": f"{category}/{source}/{name}",
                    "format": fmt, "license": lic, "fetched_at": now(), "via": f"github {repo}@{sha[:12]}"}, body)

    # CPython standard library from the local install (docstrings and comments).
    if want("cpython-stdlib"):
        lib = Path(CPYTHON_LIB)
        version = "unknown"
        try:
            version = subprocess.run([str(lib.parent.parent / "bin" / "python3"), "-I", "-c",
                                      "import sys; print(sys.version.split()[0])"],
                                     check=False, capture_output=True, text=True, timeout=10).stdout.strip() or version
        except (OSError, subprocess.SubprocessError):
            pass
        for mod in CPYTHON_MODULES:
            eid = f"cpython-stdlib/{mod}"
            src = lib / mod
            if not src.exists():
                fail(eid, str(src), "missing in local install")
                continue
            record({"id": eid, "category": "code", "source": "cpython-stdlib", "author": "CPython contributors",
                    "url": f"file://{src}", "path": f"code/cpython-stdlib/{mod.replace('/', '__')}",
                    "format": "source", "license": "PSF-2.0", "fetched_at": now(),
                    "via": f"local install, Python {version}"}, src.read_bytes())

    # Hacker News: the top-ranked live comments on the current best stories.
    if want("hacker-news"):
        base = "https://hacker-news.firebaseio.com/v0"
        prior = [e for e in old.values() if e["source"] == "hacker-news"]
        if prior and not args.refresh:
            for e in prior:
                if (out / e["path"]).exists():
                    entries[e["id"]] = e
        else:
            try:
                best = json.loads(f.get(f"{base}/beststories.json"))[:HN_STORIES]
            except (urllib.error.URLError, OSError) as exc:
                best = []
                fail("hacker-news", base, exc)
            for sid in best:
                try:
                    story = json.loads(f.get(f"{base}/item/{sid}.json")) or {}
                except (urllib.error.URLError, OSError) as exc:
                    fail(f"hacker-news/{sid}", base, exc)
                    continue
                taken = 0
                for cid in story.get("kids", [])[:6]:
                    if taken >= HN_PER_STORY:
                        break
                    try:
                        c = json.loads(f.get(f"{base}/item/{cid}.json")) or {}
                    except (urllib.error.URLError, OSError) as exc:
                        fail(f"hacker-news/{cid}", base, exc)
                        continue
                    if c.get("deleted") or c.get("dead") or not c.get("text"):
                        continue
                    taken += 1
                    record({"id": f"hacker-news/{cid}", "category": "discussion", "source": "hacker-news",
                            "author": c.get("by", ""), "url": f"https://news.ycombinator.com/item?id={cid}",
                            "path": f"discussion/hacker-news/{cid}.html", "format": "html",
                            "license": "Hacker News terms of use", "fetched_at": now(),
                            "via": f"firebase API; comment on story {sid}"},
                           html_fragment(f"<p>{c['text']}</p>"))

    # Stack Overflow: the highest-voted answers (no key needed at this volume).
    if want("stack-overflow"):
        prior = [e for e in old.values() if e["source"] == "stack-overflow"]
        if prior and not args.refresh:
            for e in prior:
                if (out / e["path"]).exists():
                    entries[e["id"]] = e
        else:
            url = ("https://api.stackexchange.com/2.3/answers?order=desc&sort=votes&site=stackoverflow"
                   f"&pagesize={SO_ANSWERS}&filter=withbody")
            try:
                items = json.loads(f.get(url)).get("items", [])
            except (urllib.error.URLError, OSError) as exc:
                items = []
                fail("stack-overflow", url, exc)
            for a in items:
                aid = a["answer_id"]
                record({"id": f"stack-overflow/{aid}", "category": "discussion", "source": "stack-overflow",
                        "author": a.get("owner", {}).get("display_name", ""),
                        "url": f"https://stackoverflow.com/a/{aid}", "path": f"discussion/stack-overflow/{aid}.html",
                        "format": "html", "license": "CC BY-SA 4.0", "fetched_at": now(),
                        "via": f"api.stackexchange.com 2.3; score {a.get('score')}"},
                       html_fragment(a.get("body", "")))

    # Earlier fetches: listed in place, not copied.
    root = args.ref_root
    if want("readme") and (root / "readme").is_dir():
        for p in sorted((root / "readme").glob("*.md")):
            repo = p.stem.replace("__", "/")
            record({"id": f"readme/{repo}", "category": "readme", "source": "github-readmes", "author": repo,
                    "url": f"https://github.com/{repo}", "path": str(p), "format": "markdown",
                    "license": "per repository", "fetched_at": "2026-10-26 (earlier fetch, SOURCES.json)",
                    "via": "existing"}, None)
    if want("commit") and (root / "commit").is_dir():
        for p in sorted((root / "commit").glob("*.txt")):
            record({"id": f"commit/{p.stem}", "category": "commit", "source": "go-commits", "author": "golang/go",
                    "url": "https://github.com/golang/go", "path": str(p), "format": "commit",
                    "license": "BSD-3-Clause", "fetched_at": "2026-10-26 (earlier fetch, SOURCES.json)",
                    "via": "existing"}, None)

    # Keep earlier entries for sources that this run did not touch.
    for eid, e in old.items():
        if eid not in entries and not want(e["source"]):
            entries[eid] = e
    manifest = {
        "description": "readcost evaluation corpus; text is third-party and stays local",
        "generated_at": now(),
        "entries": [entries[k] for k in sorted(entries)],
        # Failures of sources that this run did not try are carried over.
        "failures": [x for x in old_failures if not want(x["id"].split("/")[0])] + failures,
    }
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(entries)} entries, {len(failures)} failures -> {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
