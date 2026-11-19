"""Draw the sample of docs/prereg/kinds-precision.md: precision by kind of document.

    uv run python scripts/kinds_precision.py search    # eval/kinds/*.tsv, eval/kinds/search-log.json (needs gh)
    uv run python scripts/kinds_precision.py fetch     # clones; ref/kinds/files/, ref/kinds/fetch-state.json
    uv run python scripts/kinds_precision.py check     # every stratum: ref/kinds/checked.jsonl
    uv run python scripts/kinds_precision.py sample    # ref/kinds/sample.jsonl, eval/kinds/sample.jsonl
    uv run python scripts/kinds_precision.py batches   # rater batches and rubrics under --batches

Each step reads the output of the one before. `search` uses GitHub's repository
and code search through `gh`; `fetch` makes one blobless clone per repository
and reads only the chosen files. Fetched text stays under ref/kinds/ (it
belongs to the repositories' authors); the repository gets the candidate
lists and pointers. Round 2's machinery (near misses, decoys, rater views)
comes from scripts/breadth_precision.py; round 1's helpers from
scripts/heldout_precision.py. `check` stops unless src/ and uv.lock equal
commit 663e0cc.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import breadth_precision as bp
import heldout_precision as hp

ROOT = Path(__file__).resolve().parent.parent
FROZEN = "663e0cc"
SEED = "20261119c"
SINCE = "2026-11-01"

DEFAULT_RULES, OPT_IN_RULES, RULES, LOOSE = bp.DEFAULT_RULES, bp.OPT_IN_RULES, bp.RULES, bp.LOOSE

DOC_STRATA = ("tutorial", "reference", "explanation", "design", "runbook", "changelog", "blog", "standards")
CODE_STRATA = ("code-doc", "code-ordinary")
STRATA = (*DOC_STRATA, *CODE_STRATA, "contrast")
TECHNICAL = (*DOC_STRATA, *CODE_STRATA)

KIND = {
    "tutorial": "tutorial or how-to guide",
    "reference": "reference documentation (API, command-line or configuration reference, man page)",
    "explanation": "explanation or concept documentation",
    "design": "design document, RFC, proposal or architecture decision record",
    "runbook": "runbook, postmortem or incident document",
    "changelog": "changelog or release notes",
    "blog": "blog post in a project's repository",
    "standards": "Internet-Draft (IETF standards text)",
    "contrast": "legal or policy document (terms of service, privacy statement)",
}
LANG_NAME = {
    ".py": "Python", ".pyi": "Python", ".rs": "Rust", ".go": "Go", ".js": "JavaScript", ".mjs": "JavaScript",
    ".cjs": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java",
    ".kt": "Kotlin", ".scala": "Scala", ".swift": "Swift", ".cs": "C#", ".c": "C", ".h": "C", ".cc": "C++",
    ".cpp": "C++", ".hpp": "C++", ".rb": "Ruby", ".sh": "shell script", ".bash": "shell script",
}
SRC_EXT = tuple(LANG_NAME)
C_FAMILY = (".go", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".java", ".kt", ".scala", ".swift", ".cs", ".c",
            ".h", ".cc", ".cpp", ".hpp")

# --- populations ---

POP_A = "stars:{lo}..{hi} pushed:>=2026-11-01 created:<2026-01-01 fork:false archived:false"
POP_B = (POP_A + " " + " ".join(f"-language:{lang}" for lang in bp.LANGS))
STARS = {"a": (20001, 1000000), "b": (200, 20000)}
WALK_N = {"a": 400, "b": 600}
OWNER_CAP = 2
DRAFTS_Q = "draft-ietf in:name fork:false archived:false created:<2026-01-01"
DRAFTS_N, DRAFTS_OWNER_CAP = 80, 5
CODE_QUERIES = ("filename:runbook extension:md", "path:runbooks extension:md", "filename:postmortem extension:md",
                "path:postmortems extension:md", "filename:post-mortem extension:md",
                "filename:incident extension:md")
CODE_SEARCH_GAP = 6.5   # code search allows 10 requests a minute
CODE_PAGES = 10

# repo -> (path prefix, fixed stratum or None for the kind rule)
NAMED = {
    "github/docs": ("content/", None),
    "kubernetes/website": ("content/en/", None),
    "rust-lang/blog.rust-lang.org": ("", "blog"),
    "swiftlang/swift-evolution": ("proposals/", "design"),
    "Kotlin/KEEP": ("proposals/", "design"),
    "openshift/runbooks": ("", "runbook"),
    "prometheus-operator/runbooks": ("content/", "runbook"),
}
CONTRAST = "github/site-policy"

# --- the kind rule (registered table) ---

DIRS = {
    "changelog": {"changelog", "changelogs", "changelog.d", "changes", "release-notes", "release_notes",
                  "releasenotes", "releases", "whatsnew", "whats-new", "news"},
    "runbook": {"runbook", "runbooks", "postmortem", "postmortems", "post-mortems", "incidents", "incident",
                "oncall", "on-call"},
    "design": {"rfc", "rfcs", "adr", "adrs", "decisions", "decision-records", "design", "designs", "design-docs",
               "design_docs", "proposal", "proposals", "keps", "enhancements", "architecture-decisions",
               "architecture-decision-records"},
    "blog": {"blog", "blogs", "posts", "_posts"},
    "tutorial": {"tutorial", "tutorials", "how-to", "howto", "how-tos", "how_to", "tasks", "getting-started",
                 "getting_started", "get-started", "quickstart", "quick-start", "walkthrough", "walkthroughs",
                 "cookbook", "recipes", "guide", "guides", "user-guide", "learn"},
    "reference": {"reference", "references", "api", "apis", "api-reference", "api-docs", "man",
                  *(f"man{k}" for k in range(1, 10)), "manpages", "man-pages", "cli", "commands", "configuration",
                  "options", "settings"},
    "explanation": {"concepts", "concept", "explanation", "explanations", "background", "architecture",
                    "internals", "overview", "theory", "how-it-works", "under-the-hood"},
}
STEMS = {
    "changelog": ("changelog", "changes", "history", "news", "release-notes", "release_notes", "releasenotes",
                  "releases", "whatsnew", "whats-new"),
    "runbook": ("runbook", "postmortem", "post-mortem", "post_mortem", "incident", "oncall", "on-call"),
    "design": ("adr-", "adr_", "rfc-", "rfc_", "kep-", "design-doc", "design_doc"),
    "blog": (),
    "tutorial": ("tutorial", "how-to", "howto", "how_to", "getting-started", "getting_started", "gettingstarted",
                 "get-started", "quickstart", "quick-start", "quick_start", "walkthrough", "cookbook", "install",
                 "guide"),
    "reference": ("reference", "api", "cli-reference", "commands", "configuration", "options", "settings",
                  "glossary"),
    "explanation": ("concept", "explanation", "background", "architecture", "internals", "overview",
                    "how-it-works", "under-the-hood", "theory"),
}
KIND_ORDER = ("changelog", "runbook", "design", "blog", "tutorial", "reference", "explanation")
DESIGN_NUM = re.compile(r"^(adr|rfc|kep)\d")
MAN_STEM = re.compile(r"\.[1-9]$")

DOC_EXT = (".md", ".markdown", ".mdx", ".rst")
DOC_SKIP_DIRS = {"node_modules", "vendor", "third_party", "dist", "build", ".github"}
DOC_SKIP_NAMES = ("readme", "license", "contributing", "code_of_conduct", "security", "authors")
CONTRAST_SKIP = ("readme", "contributing", "license", "code_of_conduct")

FILES = {**dict.fromkeys(DOC_STRATA, 2), **dict.fromkeys(CODE_STRATA, 3), "standards": 1, "contrast": 40}
NAMED_FILES = 30
MAX_BYTES, MAX_SRC_BYTES, CHANGELOG_BYTES = 1_000_000, 200_000, 100_000
MIN_WORDS = 100
MIN_SRC_WORDS = 40

# --- quotas and caps ---

QUOTA = {"default": 12, "opt-in": 4, "near-default": 4, "near-opt-in": 2, "decoy": 16}
REPO_CAP, DECOY_REPO_CAP = 2, 1
NAMED_CAP, NAMED_DIR_CAP, NAMED_DECOYS = 4, 2, 4
RANKED_DOCS, RANKED_MIN_SENTENCES = 20, 5

RATER_SEEDS = {f"rater{k}": 7000 + k for k in range(1, 13)}
BLIND_SEEDS = {f"blind{k}": 8000 + k for k in range(1, 4)}
PRIMED_ITEMS = ("finding", "near", "decoy")

KIND_LINE = ('Each item also has "kind", the kind of document the sentence comes from (for example "tutorial or '
             'how-to guide", "changelog or release notes", "design document, RFC, proposal or architecture '
             'decision record" or "doc comment in Go source"); judge it as an editor of that kind of document '
             'would.')
BLIND_SOURCE_OLD = "(its documentation, the comments in its source code, a commit message or a pull request description)"
BLIND_SOURCE_NEW = "(its documentation, the comments in its source code, its standards text or its policies)"


# --- pure helpers (tested in tests/test_kinds_precision.py) ---

def _name(path: str) -> str:
    return PurePosixPath(path).name.lower()


def _stem(path: str) -> str:
    name = _name(path)
    return name.rsplit(".", 1)[0] if "." in name else name


def doc_file(path: str) -> bool:
    """A documentation file: Markdown or reStructuredText, outside skipped directories, not README and the like."""
    p = path.lower()
    if not p.endswith(DOC_EXT):
        return False
    if any(part in DOC_SKIP_DIRS for part in p.split("/")[:-1]):
        return False
    return not _name(path).startswith(DOC_SKIP_NAMES)


def kind_of_path(path: str) -> str | None:
    """The registered kind rule: directory components outermost first, then the file's stem."""
    parts = path.lower().split("/")
    for part in parts[:-1]:
        for kind in KIND_ORDER:
            if part in DIRS[kind]:
                return kind
    stem = _stem(path)
    for kind in KIND_ORDER:
        if STEMS[kind] and stem.startswith(STEMS[kind]):
            return kind
        if kind == "design" and DESIGN_NUM.match(stem):
            return kind
        if kind == "tutorial" and stem.endswith(("-guide", "_guide")):
            return kind
        if kind == "reference" and MAN_STEM.search(stem):
            return kind
    return None


def code_file(path: str) -> bool:
    p = path.lower()
    parts = p.split("/")
    if any(x in bp.SKIP_DIRS or x in bp.SRC_SKIP_DIRS for x in parts[:-1]):
        return False
    name = parts[-1]
    if name.endswith((".min.js", "_pb2.py", ".pb.go")) or ".generated." in name or "_generated." in name:
        return False
    return p.endswith(SRC_EXT)


def eligible_paths(paths: list[str], source: str, repo: str = "", search_paths: list[str] | None = None
                   ) -> dict[str, list[str]]:
    """Eligible tree paths per stratum, for one repository and the part of the population it came from.

    source: "walk", "named", "standards", "contrast" or "codesearch".
    """
    out: dict[str, list[str]] = {}

    def add(stratum, path):
        out.setdefault(stratum, []).append(path)

    if source == "walk":
        for p in paths:
            if doc_file(p):
                k = kind_of_path(p)
                if k:
                    add(k, p)
            elif code_file(p):
                add("code-doc", p)
                add("code-ordinary", p)
    elif source == "named":
        prefix, fixed = named_rule(repo)
        for p in paths:
            if not p.startswith(prefix) or not doc_file(p):
                continue
            k = fixed or kind_of_path(p[len(prefix):])
            if k:
                add(k, p)
    elif source == "standards":
        for p in paths:
            if p.lower().endswith(".md") and _name(p).startswith("draft-") and \
                    not any(x in DOC_SKIP_DIRS for x in p.lower().split("/")[:-1]):
                add("standards", p)
    elif source == "contrast":
        for p in paths:
            if p.lower().endswith(".md") and not p.lower().startswith(".github/") \
                    and not _name(p).startswith(CONTRAST_SKIP):
                add("contrast", p)
    elif source == "codesearch":
        tree = set(paths)
        for p in sorted(set(search_paths or [])):
            if p in tree and doc_file(p) and kind_of_path(p) == "runbook":
                add("runbook", p)
    else:
        raise ValueError(source)
    return out


def named_rule(repo: str) -> tuple[str, str | None]:
    return {k.lower(): v for k, v in NAMED.items()}[repo.lower()]


def files_per(stratum: str, source: str) -> int:
    if source == "named":
        return NAMED_FILES
    return FILES[stratum]


def truncate_changelog(data: bytes, limit: int = CHANGELOG_BYTES) -> tuple[bytes, bool]:
    """The first limit bytes, cut back to the end of a line."""
    if len(data) <= limit:
        return data, False
    cut = data.rfind(b"\n", 0, limit)
    return data[:cut + 1] if cut >= 0 else data[:limit], True


def normalize(sentence: str) -> str:
    """Lower case, every run of characters that are not letters or digits one space, stripped."""
    return re.sub(r"[^0-9a-z]+", " ", sentence.lower()).strip()


def dedupe_norm(items: list[dict]) -> list[dict]:
    """Drop an item whose rule and normalized sentence equal an earlier one's, in key order."""
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["key"]):
        k = (it["rule"], normalize(it["sentence"]))
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def dedupe_against_norm(items: list[dict], others: list[dict]) -> list[dict]:
    seen = {(o["rule"], normalize(o["sentence"])) for o in others}
    return [it for it in items if (it["rule"], normalize(it["sentence"])) not in seen]


# --- comment classes ---

GO_DECL = re.compile(r"^(func|type|var|const|package)\b|^[A-Z]")
RUBY_DECL = re.compile(r"^(def|class|module|attr_reader|attr_writer|attr_accessor)\b")
C_BLOCK = re.compile(r"/\*\*?(.*?)\*/", re.S)     # the pattern readcost reads block comments with
ANY_BLOCK = re.compile(r"/\*.*?\*/", re.S)


class CommentClass:
    """Classify a source offset as in a doc comment or an ordinary one (registered rule, "Code strata")."""

    def __init__(self, text: str, path: str):
        self.text, self.ext = text, PurePosixPath(path).suffix.lower()
        self.lines = text.splitlines(keepends=True)
        self.starts, pos = [], 0
        for line in self.lines:
            self.starts.append(pos)
            pos += len(line)
        self.blocks = []
        if self.ext in C_FAMILY:
            self.blocks = [(m.start(), m.end(), m.group(0)) for m in C_BLOCK.finditer(text)]
        elif self.ext == ".rs":
            self.blocks = [(m.start(), m.end(), m.group(0)) for m in ANY_BLOCK.finditer(text)]
        self.doc_lines: set[int] = set()
        if self.ext in (".py", ".pyi"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                tree = None
            for node in ast.walk(tree) if tree else ():
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", [])
                    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        self.doc_lines |= set(range(body[0].lineno - 1, (body[0].end_lineno or body[0].lineno)))

    def _line(self, k: int) -> str:
        return self.lines[k].strip() if 0 <= k < len(self.lines) else ""

    def _run_end(self, k: int, prefix: str) -> int:
        """Index of the last line of the run of comment lines that holds line k."""
        while k + 1 < len(self.lines) and self._line(k + 1).startswith(prefix):
            k += 1
        return k

    def __call__(self, offset: int) -> str:
        for a, b, body in self.blocks:
            if a <= offset < b:
                return "doc" if (body.startswith(("/**", "/*!")) and not body.startswith("/**/")) else "ordinary"
        k = max(0, bisect_right(self.starts, offset) - 1)
        s = self._line(k)
        ext = self.ext
        if ext in (".py", ".pyi"):
            return "ordinary" if s.startswith("#") and k not in self.doc_lines else "doc"
        if ext == ".rs":
            return "doc" if s.startswith(("///", "//!")) else "ordinary"
        if ext in C_FAMILY:
            if s.startswith("///"):
                return "doc"
            if ext == ".go" and s.startswith("//"):
                nxt = self._line(self._run_end(k, "//") + 1)
                return "doc" if nxt and GO_DECL.match(nxt) else "ordinary"
            return "ordinary"
        if ext == ".rb" and s.startswith("#"):
            nxt = self._line(self._run_end(k, "#") + 1)
            return "doc" if nxt and RUBY_DECL.match(nxt) else "ordinary"
        return "ordinary"


def code_kind(stratum: str, path: str) -> str:
    ext = PurePosixPath(path).suffix.lower()
    lang = LANG_NAME[ext]
    if stratum == "code-doc":
        return "Python docstring" if lang == "Python" else f"doc comment in {lang} source"
    return f"ordinary comment in {lang} source (not a doc comment)"


def kind_label(stratum: str, path: str) -> str:
    return code_kind(stratum, path) if stratum in CODE_STRATA else KIND[stratum]


# --- sentence features for the ranked items ---

def arc_words(sent) -> int:
    """Longest dependency arc: alphabetic tokens from a dependent to its head, counting the head."""
    best = 0
    for t in sent:
        h = t.head
        if h.i == t.i or not (sent.start <= h.i < sent.end):
            continue
        lo, hi = min(t.i, h.i), max(t.i, h.i)
        n = sum(1 for x in sent.doc[lo:hi + 1] if x.is_alpha and x.i != t.i)
        best = max(best, n)
    return best


def zscores(xs: list[float]) -> list[float]:
    if len(xs) < 2:
        return [0.0] * len(xs)
    mu, sd = statistics.fmean(xs), statistics.pstdev(xs)
    return [0.0 if sd == 0 else (x - mu) / sd for x in xs]


def ranked_picks(sents: list[dict], nfind: list[int], rng: random.Random) -> dict[str, int]:
    """Indexes of the longest, composite-top and random sentence (sents in document order)."""
    words = [s["words"] for s in sents]
    comp = [a + b + c + f for a, b, c, f in zip(zscores(words), zscores([s["arc"] for s in sents]),
                                              zscores([s["depth"] for s in sents]), nfind)]
    longest = max(range(len(sents)), key=lambda i: (words[i], -i))
    top = max(range(len(sents)), key=lambda i: (comp[i], -i))
    return {"longest": longest, "composite": top, "random": rng.randrange(len(sents))}


# --- capped draws ---

def cap_keys(it: dict, decoy: bool = False) -> list[tuple[str, int]]:
    """(counter key, limit) pairs an item counts against."""
    repo, src = it["repo"], it.get("source", "walk")
    if src == "named":
        d = str(PurePosixPath(it["path"]).parent)
        if decoy:
            return [(f"src:{repo}", NAMED_DECOYS), (f"file:{repo}:{it['path']}", 1)]
        return [(f"src:{repo}", NAMED_CAP), (f"dir:{repo}:{d}", NAMED_DIR_CAP)]
    if src == "contrast":
        return [(f"file:{repo}:{it['path']}", DECOY_REPO_CAP if decoy else REPO_CAP)]
    return [(f"repo:{repo}", DECOY_REPO_CAP if decoy else REPO_CAP)]


def capped_draw(items: list[dict], quota: int, seed: str, seen_keys: set, seen_norm: set,
                accept=None) -> list[dict]:
    """Shuffle (from key order) with seed; take in order under the caps, rejecting keys and (rule, sentence) seen."""
    pool = sorted(items, key=lambda x: x["key"])
    random.Random(seed).shuffle(pool)
    count: Counter = Counter()
    out = []
    for it in pool:
        if len(out) >= quota:
            break
        norm = (it["rule"], normalize(it["sentence"]))
        if it["key"] in seen_keys or norm in seen_norm:
            continue
        caps = cap_keys(it)
        if any(count[k] >= lim for k, lim in caps):
            continue
        if accept is not None and not accept(it):
            continue
        for k, _ in caps:
            count[k] += 1
        seen_keys.add(it["key"])
        seen_norm.add(norm)
        out.append(it)
    return out


def quota_for(rule: str, near: bool) -> int:
    if near:
        return QUOTA["near-default" if rule in DEFAULT_RULES else "near-opt-in"]
    return QUOTA["default" if rule in DEFAULT_RULES else "opt-in"]


def doc_key(c: dict) -> str:
    return hp.finding_key(c["repo"], c["commit"], c["path"], "document")


def draw_stratum(stratum: str, kept: list[dict], tokens_for, seen_keys: set, seen_norm: set,
                 seen_sent: set) -> tuple[list[dict], dict]:
    """Findings, near misses, random decoys and ranked sentences of one stratum.

    seen_keys, seen_norm (rule, normalized sentence) and seen_sent (normalized
    sentence) are shared across strata, so no item is drawn twice.
    """
    counts: dict = {}

    def base(c):
        return {"repo": c["repo"], "commit": c["commit"], "path": c["path"], "blob": c["blob"],
                "stratum": stratum, "source": c.get("source", "walk"), "doc": doc_key(c)}

    allf = [f | base(c) for c in kept for f in c["findings"]]
    alln = [f | base(c) for c in kept for f in c["near"]]
    deduped = dedupe_norm(allf)
    near = dedupe_norm(dedupe_against_norm(alln, allf))
    counts["findings"] = dict(Counter(f["rule"] for f in allf))
    counts["deduped"] = dict(Counter(f["rule"] for f in deduped))
    counts["near"] = dict(Counter(f["rule"] for f in alln))
    counts["near_deduped"] = dict(Counter(f["rule"] for f in near))
    out: list[dict] = []
    sampled, sampled_near = {}, {}
    for rule in RULES:
        got = capped_draw([f for f in deduped if f["rule"] == rule], quota_for(rule, False),
                          f"{SEED}:{stratum}:{rule}", seen_keys, seen_norm)
        sampled[rule] = len(got)
        out += [f | {"item": "finding"} for f in got]
        if rule in LOOSE:
            got = capped_draw([f for f in near if f["rule"] == rule], quota_for(rule, True),
                              f"{SEED}:{stratum}:near-{rule}", seen_keys, seen_norm)
            sampled_near[rule] = len(got)
            out += [f | {"item": "near"} for f in got]
    counts["sampled"], counts["sampled_near"] = sampled, sampled_near
    seen_sent |= {normalize(it["sentence"]) for it in out}
    # random decoys
    sents = []
    for c in kept:
        for s in c["sentences"]:
            sents.append(s | base(c) | {"rule": "", "rec": c, "key": hp.finding_key(
                c["repo"], c["commit"], c["path"], "sentence", s["start"], s["end"])})
    pool = dedupe_norm(sents)
    counts["decoy_pool"] = len(pool)
    names = hp.rule_names(QUOTA["decoy"], f"{SEED}:{stratum}:decoy-rules")
    order = sorted(pool, key=lambda x: x["key"])
    random.Random(f"{SEED}:{stratum}:decoy-random").shuffle(order)
    count: Counter = Counter()
    decoys = []
    rejected = 0
    for s in order:
        if len(decoys) >= QUOTA["decoy"]:
            break
        caps = cap_keys(s, decoy=True)
        if any(count[k] >= lim for k, lim in caps):
            continue
        if normalize(s["sentence"]) in seen_sent:
            rejected += 1
            continue
        toks = tokens_for(s["rec"], s["start"], s["end"])
        if not toks:
            continue
        span = hp.decoy_span([(t[0], t[1], t[2]) for t in toks], random.Random(f"{SEED}:span:{s['key']}"))
        if span is None:
            continue
        run = toks[span[0]:span[1] + 1]
        if run[0][3] is None or run[-1][4] is None:
            continue
        start, end = run[0][3], run[-1][4]
        key = hp.finding_key(s["repo"], s["commit"], s["path"], "decoy-random", start, end)
        if key in seen_keys:
            continue
        for k, _ in caps:
            count[k] += 1
        rule = names[len(decoys)]
        seen_keys.add(key)
        seen_sent.add(normalize(s["sentence"]))
        decoys.append({k: s[k] for k in ("repo", "commit", "path", "blob", "stratum", "source", "doc")} | {
            "rule": rule, "message": hp.decoy_message(rule, [t[0] for t in run]), "excerpt": None,
            "sentence": s["sentence"], "start": start, "end": end, "sentence_start": s["start"],
            "sentence_end": s["end"], "item": "decoy", "key": key})
    counts["decoys"], counts["decoys_rejected_as_seen"] = len(decoys), rejected
    out += decoys
    ranked, counts["ranked_docs"] = draw_ranked(stratum, kept, out, seen_keys, base)
    counts["ranked"] = len(ranked)
    return out + ranked, counts


def draw_ranked(stratum: str, kept: list[dict], items: list[dict], seen_keys: set, base) -> tuple[list[dict], int]:
    """Part A: longest, composite-top and random sentence of up to RANKED_DOCS documents that gave an item."""
    first: dict[str, str] = {}
    for it in items:
        first[it["doc"]] = min(first.get(it["doc"], it["key"]), it["key"])
    by_doc = {doc_key(c): c for c in kept}
    docs = sorted(first, key=lambda d: first[d])
    random.Random(f"{SEED}:{stratum}:ranked-docs").shuffle(docs)
    repos: set = set()
    out, ndocs = [], 0
    for d in docs:
        if ndocs >= RANKED_DOCS:
            break
        c = by_doc[d]
        if stratum != "contrast" and c["repo"] in repos:
            continue
        sents = sorted(c["all_sentences"], key=lambda s: s["start"])
        if len(sents) < RANKED_MIN_SENTENCES:
            continue
        default = [f for f in c["findings"] if f["rule"] in DEFAULT_RULES]
        nfind = [sum(1 for f in default if s["start"] <= f["start"] < s["end"]) for s in sents]
        picks = ranked_picks(sents, nfind, random.Random(f"{SEED}:ranked:{d}"))
        by_idx: dict[int, list[str]] = {}
        for name, idx in picks.items():
            by_idx.setdefault(idx, []).append(name)
        made = []
        for idx, names in sorted(by_idx.items()):
            s = sents[idx]
            key = hp.finding_key(c["repo"], c["commit"], c["path"], "ranked", s["start"], s["end"])
            if key in seen_keys:
                continue
            made.append(base(c) | {"rule": "", "message": "", "excerpt": s["sentence"], "sentence": s["sentence"],
                                   "start": s["start"], "end": s["end"], "sentence_start": s["start"],
                                   "sentence_end": s["end"], "item": "ranked", "ranks": sorted(names),
                                   "key": key})
        for m in made:
            seen_keys.add(m["key"])
        repos.add(c["repo"])
        ndocs += 1
        out += made
    return out, ndocs


def build_sample(checked: list[dict], sources: dict[tuple, str], tokens_for) -> tuple[list[dict], dict]:
    counts: dict = {}
    sample: list[dict] = []
    seen_keys: set = set()
    seen_norm: set = set()
    seen_sent: set = set()
    for stratum in STRATA:
        kept = [c for c in checked if c["stratum"] == stratum and not c.get("drop")]
        items, counts[stratum] = draw_stratum(stratum, kept, tokens_for, seen_keys, seen_norm, seen_sent)
        sample += items
    keys = [it["key"] for it in sample]
    assert len(keys) == len(set(keys)), "an item was drawn twice"
    ids = hp.assign_ids(keys, seed=f"{SEED}:ids")
    for it in sample:
        src = sources[(it["repo"], it["path"])]
        it["i"] = ids[it["key"]]
        it["kind"] = kind_label(it["stratum"], it["path"])
        if it["excerpt"] is None:  # a decoy shows the source's own words
            it["excerpt"] = src[it["start"]:it["end"]]
        it["before"], it["after"] = hp.context(src, it["sentence_start"], it["sentence_end"])
        it.setdefault("ranks", [])
    return sorted(sample, key=lambda x: x["key"]), counts


def primed_items(sample: list[dict]) -> list[dict]:
    return [bp.rater_item(x) for x in sample if x["item"] in PRIMED_ITEMS]


def blind_items(sample: list[dict]) -> list[dict]:
    return [bp.blind_item(x) for x in sample]


def rubric_primed(base: str) -> str:
    """Round 2's RUBRIC.txt with the kind line saying what "kind" now means."""
    assert bp.KIND_LINE in base
    return base.replace(bp.KIND_LINE, KIND_LINE)


def rubric_blind(base: str) -> str:
    assert bp.KIND_LINE in base and BLIND_SOURCE_OLD in base
    return base.replace(bp.KIND_LINE, KIND_LINE).replace(BLIND_SOURCE_OLD, BLIND_SOURCE_NEW)


# --- search ---

def _gap(gap: float = hp.SEARCH_GAP) -> None:
    wait = gap - (time.time() - hp._last_search)
    if wait > 0:
        time.sleep(wait)
    hp._last_search = time.time()


def search_split(fmt: str, lo: int | None, hi: int | None, log: list) -> list[dict]:
    """Every repository of a query, splitting its star range while the count is over the search limit."""
    q = fmt.format(lo=lo, hi=hi) if lo is not None else fmt
    items, page = [], 1
    while True:
        _gap()
        res = json.loads(hp.gh(["-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "sort=stars",
                                "-f", "order=desc", "-f", "per_page=100", "-f", f"page={page}"]))
        log.append({"q": q, "page": page, "total_count": res["total_count"],
                    "incomplete": res.get("incomplete_results"), "at": datetime.now(UTC).isoformat()})
        if page == 1 and res["total_count"] > bp.SEARCH_LIMIT and lo is not None and lo < hi:
            return [x for a, b in bp.split_range(lo, hi) for x in search_split(fmt, a, b, log)]
        items += res["items"]
        if len(res["items"]) < 100 or len(items) >= min(res["total_count"], bp.SEARCH_LIMIT):
            return items
        page += 1


CAND_FIELDS = ("repo", "population", "language", "stars", "created_at", "default_branch", "fork", "archived",
               "license")


def cand_row(it: dict, population: str) -> dict:
    return {"repo": it["full_name"], "population": population, "language": it.get("language") or "",
            "stars": it["stargazers_count"], "created_at": it["created_at"],
            "default_branch": it["default_branch"], "fork": it["fork"], "archived": it["archived"],
            "license": ((it.get("license") or {}).get("spdx_id")) or ""}


def write_tsv(path: Path, rows: list[dict], fields=CAND_FIELDS) -> None:
    lines = ["\t".join(fields)]
    for r in sorted(rows, key=lambda r: (r.get("population", ""), r["repo"].lower(), r.get("path", ""))):
        lines.append("\t".join(str(r[k]).lower() if isinstance(r[k], bool) else str(r[k]) for k in fields))
    path.write_text("\n".join(lines) + "\n")


def read_tsv(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    head = lines[0].split("\t")
    out = []
    for line in lines[1:]:
        r = dict(zip(head, line.split("\t")))
        if "stars" in r:
            r["stars"] = int(r["stars"])
        for k in ("fork", "archived"):
            if k in r:
                r[k] = r[k] == "true"
        out.append(r)
    return out


def code_search(q: str, log: list) -> list[dict]:
    out = []
    for page in range(1, CODE_PAGES + 1):
        _gap(CODE_SEARCH_GAP)
        try:
            res = json.loads(hp.gh(["-X", "GET", "search/code", "-f", f"q={q}", "-f", "per_page=100",
                                    "-f", f"page={page}"], tries=3))
        except (RuntimeError, FileNotFoundError) as exc:
            log.append({"q": q, "page": page, "error": str(exc)[:200], "at": datetime.now(UTC).isoformat()})
            break
        log.append({"q": q, "page": page, "total_count": res["total_count"],
                    "incomplete": res.get("incomplete_results"), "at": datetime.now(UTC).isoformat()})
        out += [{"repo": it["repository"]["full_name"], "path": it["path"], "query": q} for it in res["items"]]
        if len(res["items"]) < 100:
            break
    return out


def cmd_search(args) -> None:
    log: list = []
    out = ROOT / "eval/kinds"
    out.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    for pop, fmt in (("a", POP_A), ("b", POP_B)):
        got = search_split(fmt, *STARS[pop], log)
        for it in got:
            seen.setdefault(it["full_name"], cand_row(it, pop))
        print(f"population {pop}: {len(got)}", flush=True)
    write_tsv(out / "candidates.tsv", list(seen.values()))
    drafts = {it["full_name"]: cand_row(it, "standards") for it in search_split(DRAFTS_Q, None, None, log)}
    write_tsv(out / "drafts.tsv", list(drafts.values()))
    named = {}
    for repo in [*NAMED, CONTRAST]:
        _gap()
        res = json.loads(hp.gh(["-X", "GET", "search/repositories", "-f", f"q=repo:{repo}"]))
        log.append({"q": f"repo:{repo}", "total_count": res["total_count"], "at": datetime.now(UTC).isoformat()})
        for it in res["items"]:
            named[it["full_name"]] = cand_row(it, "contrast" if repo == CONTRAST else "named")
    write_tsv(out / "named.tsv", list(named.values()))
    hits = []
    for q in CODE_QUERIES:
        got = code_search(q, log)
        hits += got
        print(f"{q}: {len(got)}", flush=True)
    uniq = {(h["repo"], h["path"]): h for h in hits}
    write_tsv(out / "codesearch.tsv", list(uniq.values()), fields=("repo", "path", "query"))
    (out / "search-log.json").write_text(json.dumps(log, indent=1) + "\n")
    print(len(seen), "candidates,", len(drafts), "drafts,", len(named), "named,", len(uniq), "code search hits")


# --- fetch ---

def excluded_repos() -> set[str]:
    names: set[str] = set()
    files = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", FROZEN, "scripts", "eval", "docs"],
                           check=True, capture_output=True, text=True).stdout.split()
    for f in files:
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{FROZEN}:{f}"], check=True, capture_output=True)
        names |= hp.repo_names(blob.stdout.decode("utf-8", "replace"))
    edit = subprocess.run(["git", "-C", str(ROOT), "show", "exp/edit-arms:eval/edit-arms/candidates.jsonl"],
                          check=True, capture_output=True, text=True).stdout
    names |= {json.loads(x)["repo"].lower() for x in edit.splitlines() if x.strip()}
    return names


def walk(cands: list[dict], excluded: set[str], skip: set[str]) -> tuple[list[dict], Counter]:
    """The registered walk: population a, then b, each shuffled; owner cap across both."""
    owners: Counter = Counter()
    picked, drops = [], Counter()
    for pop in ("a", "b"):
        pool = sorted((c for c in cands if c["population"] == pop), key=lambda c: c["repo"].lower())
        random.Random(f"{SEED}:walk:{pop}").shuffle(pool)
        n = 0
        for c in pool:
            if n >= WALK_N[pop]:
                break
            owner = c["repo"].split("/")[0].lower()
            why = ("named source" if c["repo"].lower() in skip else None) or hp.excluded(c["repo"], excluded) \
                or ("fork" if c["fork"] else None) or ("archived" if c["archived"] else None) \
                or ("owner cap" if owners[owner] >= OWNER_CAP else None)
            if why:
                drops[f"{pop}: {why}"] += 1
                continue
            owners[owner] += 1
            picked.append(c | {"source": "walk"})
            n += 1
    return picked, drops


def walk_drafts(cands: list[dict], excluded: set[str]) -> tuple[list[dict], Counter]:
    owners: Counter = Counter()
    pool = sorted(cands, key=lambda c: c["repo"].lower())
    random.Random(f"{SEED}:walk:standards").shuffle(pool)
    picked, drops = [], Counter()
    for c in pool:
        if len(picked) >= DRAFTS_N:
            break
        owner = c["repo"].split("/")[0].lower()
        why = hp.excluded(c["repo"], excluded) or ("fork" if c["fork"] else None) \
            or ("archived" if c["archived"] else None) \
            or ("owner cap" if owners[owner] >= DRAFTS_OWNER_CAP else None)
        if why:
            drops[f"standards: {why}"] += 1
            continue
        owners[owner] += 1
        picked.append(c | {"source": "standards"})
    return picked, drops


def jobs(excluded: set[str]) -> tuple[list[dict], dict]:
    cands = read_tsv(ROOT / "eval/kinds/candidates.tsv")
    named = read_tsv(ROOT / "eval/kinds/named.tsv")
    skip = {r.lower() for r in [*NAMED, CONTRAST]}
    picked, drops = walk(cands, excluded, skip)
    dpicked, ddrops = walk_drafts(read_tsv(ROOT / "eval/kinds/drafts.tsv"), excluded)
    out = picked + dpicked
    for r in named:
        why = hp.excluded(r["repo"], excluded) or ("no licence" if not r["license"] or r["license"] == "NOASSERTION"
                                                   else None) or ("archived" if r["archived"] else None)
        if why:
            drops[f"{r['population']}: {why}"] += 1
            continue
        out.append(r | {"source": "contrast" if r["population"] == "contrast" else "named"})
    # code search: kept candidates (drop rules 1 and 2), runbook paths only
    by_repo = {c["repo"]: c for c in cands if not hp.excluded(c["repo"], excluded) and not c["fork"]
               and not c["archived"] and c["repo"].lower() not in skip}
    walked = {c["repo"] for c in picked}
    hits: dict[str, list[str]] = {}
    for h in read_tsv(ROOT / "eval/kinds/codesearch.tsv"):
        if h["repo"] in by_repo and h["repo"] not in walked and doc_file(h["path"]) \
                and kind_of_path(h["path"]) == "runbook":
            hits.setdefault(h["repo"], []).append(h["path"])
    for repo, paths in sorted(hits.items()):
        out.append(by_repo[repo] | {"source": "codesearch", "search_paths": sorted(set(paths))})
    return out, {"walk": dict(drops | ddrops), "picked": Counter(j["source"] for j in out)}


def _store(ref: Path, repo: str, path: str, data: bytes) -> str:
    local = ref / "files" / repo / path
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(data)
    return str(local.relative_to(ref))


def fetch_repo(ref: Path, job: dict) -> dict:
    repo, branch, source = job["repo"], job["default_branch"], job["source"]
    work = ref / "git" / repo.replace("/", "__")
    shutil.rmtree(work, ignore_errors=True)
    work.parent.mkdir(parents=True, exist_ok=True)
    try:
        hp.git(["clone", "--quiet", "--bare", "--filter=blob:none", "--depth", "1", "--single-branch", "--branch",
                branch, f"https://github.com/{repo}.git", str(work)], timeout=600)
        st: dict = {"commit": hp.git(["rev-parse", "HEAD"], cwd=work).strip()}
        tree = {}
        for line in hp.git(["ls-tree", "-r", "-z", "HEAD"], cwd=work, timeout=600).split("\0"):
            if not line:
                continue
            meta, path = line.split("\t", 1)
            mode, kind, sha = meta.split()
            if kind == "blob" and not mode.startswith("12"):
                tree[path] = sha
        elig = eligible_paths(list(tree), source, repo, job.get("search_paths"))
        chosen = []
        for stratum, paths in sorted(elig.items()):
            for p in bp.choose(paths, files_per(stratum, source), f"{SEED}:{stratum}:{repo}"):
                chosen.append((stratum, p))
        st["eligible"] = {k: len(v) for k, v in elig.items()}
        oids = sorted({tree[p] for _, p in chosen})
        for k in range(0, len(oids), 200):
            hp.git(["-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags",
                    "--no-write-fetch-head", "--filter=blob:none", *oids[k:k + 200]], cwd=work, timeout=600)
        files = []
        for stratum, p in chosen:
            data = hp.git(["cat-file", "blob", tree[p]], cwd=work, binary=True)
            rec = {"stratum": stratum, "path": p, "blob": tree[p], "bytes": len(data)}
            if stratum == "changelog":
                data, cut = truncate_changelog(data)
                rec["truncated"] = cut
            limit = MAX_SRC_BYTES if stratum in CODE_STRATA else MAX_BYTES
            if len(data) <= limit:
                rec["local"] = _store(ref, repo, p, data)
            files.append(rec)
        st["files"] = files
        return st
    finally:
        shutil.rmtree(work, ignore_errors=True)


def cmd_fetch(args) -> None:
    todo_all, meta = jobs(excluded_repos())
    state_path = args.ref / "fetch-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    state["_jobs"] = meta | {"picked": dict(meta["picked"])}
    todo = [j for j in todo_all if j["repo"] not in state]

    def one(j):
        try:
            st = fetch_repo(args.ref, j)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            st = {"drop": "fetch error", "error": str(exc)[:300]}
        state[j["repo"]] = st | {"source": j["source"], "population": j.get("population", ""),
                                 "stars": j["stars"], "license": j.get("license", "")}
        return j

    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        for n, _ in enumerate(ex.map(one, todo), 1):
            if n % 25 == 0:
                state_path.write_text(json.dumps(state))
                print(f"{n}/{len(todo)} repositories in {time.time() - t0:.0f}s", flush=True)
    state_path.write_text(json.dumps(state))
    print(Counter(v.get("drop", "ok") for k, v in state.items() if not k.startswith("_")))


# --- readcost ---

def frozen_check() -> None:
    diff = subprocess.run(["git", "-C", str(ROOT), "diff", "--stat", FROZEN, "--", "src", "uv.lock"],
                          capture_output=True, text=True, check=True).stdout
    if diff.strip():
        sys.exit(f"src/ or uv.lock differ from {FROZEN}; the pre-registration froze them:\n{diff}")


def analyzer(comments: str = "doc"):
    an = bp.analyzer()
    an.cfg.comments = comments
    return an


def check_text(an, text: str, rec: dict) -> dict:
    """Default run, the looser runs, the decoy sentences and every eligible sentence with its features."""
    from readcost.extract import extract
    from readcost.features import Context, show
    from readcost.metrics import embedding_depth

    stratum, repo, commit, path = rec["stratum"], rec["repo"], rec["commit"], rec["path"]
    code = stratum in CODE_STRATA
    want = "doc" if stratum == "code-doc" else "ordinary"
    cls = CommentClass(text, path) if code else None

    def keep(offset):
        return not code or (offset is not None and cls(offset) == want)

    nlp = an.nlp
    cache = bp.ParseCache(nlp)
    an._nlp = cache
    try:
        res = an.check_text(text, None, path, lines=bp.ALL_LINES)
        out = rec | {"words": res.words}
        if any("not English" in n for n in res.notes):
            return out | {"drop": "not English"}
        floor = MIN_SRC_WORDS if code else MIN_WORDS
        if res.words < floor:
            return out | {"drop": f"under {floor} words"}
        if path.lower().endswith((".md", ".markdown", ".mdx")) and hp.fenced_share(text) > 0.5:
            return out | {"drop": "mostly code"}
        findings = [f for f in bp._findings(res, repo, commit, path) if keep(f["sentence_start"])]
        taken = [(f.sentence_start, f.sentence_end) for f in res.findings if f.sentence_start is not None]
        near = []
        for rule in LOOSE:
            with bp.loosened(rule):
                lres = an.check_text(text, None, path, lines=bp.ALL_LINES)
            taken += [(f.sentence_start, f.sentence_end) for f in lres.findings if f.sentence_start is not None]
            lf = [f for f in bp._findings(lres, repo, commit, path, (rule,)) if keep(f["sentence_start"])]
            for f in lf:
                f["key"] = hp.finding_key(repo, commit, path, f"near-{rule}", f["start"], f["end"])
            near += bp.near_misses(findings, lf, rule)
        sentences, alls = [], []
        ctx = Context(an.cfg, an.profile, an.allow, set())
        for seg in extract(text, path, None, comments=an.cfg.comments):
            doc = cache(seg.text)
            ctx.codes = seg.codes
            for sent in doc.sents:
                words = [t for t in sent if t.is_alpha]
                if len(words) < 4 or not any(t.pos_ in ("VERB", "AUX") for t in sent):
                    continue
                whole = seg.span(sent.start_char, sent.end_char)
                if not whole or not keep(whole[0]):
                    continue
                s = {"start": whole[0], "end": whole[1], "words": len(words),
                     "sentence": show(ctx, doc, sent.start, sent.end - 1)}
                alls.append(s | {"arc": arc_words(sent), "depth": embedding_depth(sent)})
                if not any(a < whole[1] and whole[0] < b for a, b in taken):
                    sentences.append(s)
        # one sentence can come twice (a Rust "///" line read again as "//"); keep the first
        uniq = {}
        for s in alls:
            uniq.setdefault((s["start"], s["end"]), s)
        return out | {"findings": findings, "near": near, "sentences": sentences, "all_sentences": list(uniq.values())}
    finally:
        an._nlp = nlp


def sentence_tokens(an, text: str, path: str, start: int, end: int) -> list | None:
    from readcost.extract import extract
    for seg in extract(text, path, None, comments=an.cfg.comments):
        doc = an.nlp(seg.text)
        for sent in doc.sents:
            if seg.span(sent.start_char, sent.end_char) == (start, end):
                return [[t.text, t.pos_, t.is_alpha, *(seg.span(t.idx, t.idx + len(t.text)) or (None, None))]
                        for t in sent]
    return None


_AN: dict = {}


def _worker(job):
    from readcost.engine import read_source
    rec, local = job
    comments = "all" if rec["stratum"] == "code-ordinary" else "doc"
    if comments not in _AN:
        _AN[comments] = analyzer(comments)
    text, _ = read_source(local)
    try:
        return check_text(_AN[comments], text, rec)
    except Exception as exc:  # noqa: BLE001 -- one bad file must not stop the run; recorded as a drop
        return rec | {"drop": "check error", "error": repr(exc)[:300]}


def texts(ref: Path) -> list[tuple[dict, str]]:
    state = json.loads((ref / "fetch-state.json").read_text())
    rows = []
    for repo, st in sorted(state.items(), key=lambda kv: kv[0].lower()):
        if repo.startswith("_") or st.get("drop"):
            continue
        for f in st["files"]:
            rec = {"stratum": f["stratum"], "repo": repo, "commit": st["commit"], "path": f["path"],
                   "blob": f["blob"], "source": st["source"]}
            if not f.get("local"):
                rows.append((rec | {"drop": "too large"}, ""))
                continue
            rows.append((rec, str(ref / f["local"])))
    seen: set = set()
    out = []
    for rec, local in sorted(rows, key=lambda x: (x[0]["stratum"], x[0]["repo"].lower(), x[0]["path"])):
        if local:
            digest = hashlib.sha256(Path(local).read_bytes()).hexdigest()
            rec["sha256"] = digest
            if (rec["stratum"], digest) in seen:
                rec["drop"] = "duplicate text"
            seen.add((rec["stratum"], digest))
        out.append((rec, local))
    return out


def cmd_check(args) -> None:
    frozen_check()
    import readcost
    jobs_ = texts(args.ref)
    rows = [rec for rec, _ in jobs_ if rec.get("drop")]
    todo = [(rec, local) for rec, local in jobs_ if not rec.get("drop")]
    t0 = time.time()
    with ProcessPoolExecutor(args.workers) as ex:
        for n, row in enumerate(ex.map(_worker, todo, chunksize=4), 1):
            rows.append(row)
            if n % 200 == 0:
                print(f"{n}/{len(todo)} texts in {time.time() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["stratum"], r["repo"].lower(), r["path"]))
    meta = {"readcost": readcost.__version__,
            "features_sha256": hashlib.sha256((ROOT / "src/readcost/features.py").read_bytes()).hexdigest()}
    (args.ref / "check-meta.json").write_text(json.dumps(meta))
    (args.ref / "checked.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(Counter((r["stratum"], r.get("drop", "kept")) for r in rows))


POINTER_FIELDS = ("i", "key", "stratum", "kind", "item", "rule", "ranks", "source", "doc", "repo", "commit", "path", "blob",
                  "start", "end", "sentence_start", "sentence_end")


def cmd_sample(args) -> None:
    from readcost.engine import read_source
    checked = [json.loads(x) for x in (args.ref / "checked.jsonl").read_text().splitlines()]
    locals_ = {(rec["repo"], rec["path"]): local for rec, local in texts(args.ref) if local}
    sources = {(c["repo"], c["path"]): read_source(locals_[(c["repo"], c["path"])])[0]
               for c in checked if not c.get("drop")}
    ans = {"doc": analyzer("doc"), "all": analyzer("all")}

    def tokens_for(rec, start, end):
        an = ans["all" if rec["stratum"] == "code-ordinary" else "doc"]
        return sentence_tokens(an, sources[(rec["repo"], rec["path"])], rec["path"], start, end)

    sample, counts = build_sample(checked, sources, tokens_for)
    (args.ref / "sample.jsonl").write_text("".join(json.dumps(x) + "\n" for x in sample))
    out = ROOT / "eval/kinds/sample.jsonl"
    out.write_text("".join(json.dumps({k: x[k] for k in POINTER_FIELDS}) + "\n" for x in sample))
    state = json.loads((args.ref / "fetch-state.json").read_text())
    counts["_texts"] = {f"{s}: {d}": n for (s, d), n in
                        sorted(Counter((c["stratum"], c.get("drop", "kept")) for c in checked).items())}
    counts["_texts_by_source"] = {f"{s}: {src}": n for (s, src), n in sorted(Counter(
        (c["stratum"], c["source"]) for c in checked if not c.get("drop")).items())}
    counts["_jobs"] = state.get("_jobs", {})
    counts["_repos"] = dict(Counter(f"{v['source']}: {v.get('drop', 'ok')}" for k, v in state.items()
                                    if not k.startswith("_")))
    counts["_items"] = {f"{s}: {k}": n for (s, k), n in sorted(Counter((x["stratum"], x["item"]) for x in sample).items())}
    (ROOT / "eval/kinds/counts.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(json.dumps(counts["_items"], indent=1), len(sample), "items")


def cmd_batches(args) -> None:
    sample = [json.loads(x) for x in (args.ref / "sample.jsonl").read_text().splitlines()]
    args.batches.mkdir(parents=True, exist_ok=True)
    base = Path(args.rubrics)
    (args.batches / "RUBRIC.txt").write_text(rubric_primed((base / "RUBRIC.txt").read_text()))
    (args.batches / "RUBRIC_BLIND.txt").write_text(rubric_blind((base / "RUBRIC_BLIND.txt").read_text()))
    for seeds, items in ((RATER_SEEDS, primed_items(sample)), (BLIND_SEEDS, blind_items(sample))):
        for rater, seed in seeds.items():
            d = args.batches / rater
            d.mkdir(exist_ok=True)
            for old in d.glob("batch-*.json"):
                old.unlink()
            for k, b in enumerate(hp.batches(items, seed), 1):
                (d / f"batch-{k:02d}.json").write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n")
    (args.batches / "labels").mkdir(exist_ok=True)
    print(len(sample), "items;", len(primed_items(sample)), "primed;",
          {r: len(list((args.batches / r).glob("batch-*.json"))) for r in [*RATER_SEEDS, *BLIND_SEEDS]})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["search", "fetch", "check", "sample", "batches"])
    ap.add_argument("--ref", type=Path, default=ROOT / "ref/kinds")
    ap.add_argument("--batches", type=Path, default=Path("/home/claude/kinds-batches"))
    ap.add_argument("--rubrics", default="/home/claude/breadth-batches",
                    help="folder with round 2's RUBRIC.txt and RUBRIC_BLIND.txt")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    args.ref.mkdir(parents=True, exist_ok=True)
    {"search": cmd_search, "fetch": cmd_fetch, "check": cmd_check, "sample": cmd_sample,
     "batches": cmd_batches}[args.step](args)


if __name__ == "__main__":
    main()
