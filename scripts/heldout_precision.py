"""Draw the held-out precision sample of docs/prereg/heldout-precision.md.

    uv run python scripts/heldout_precision.py search    # eval/heldout/candidates.jsonl (needs gh)
    uv run python scripts/heldout_precision.py fetch     # ref/heldout/files/, ref/heldout/files.jsonl (needs gh)
    uv run python scripts/heldout_precision.py check     # ref/heldout/checked.jsonl
    uv run python scripts/heldout_precision.py sample    # ref/heldout/sample.jsonl, eval/heldout/sample.jsonl
    uv run python scripts/heldout_precision.py batches   # rater batches and RUBRIC.txt under --batches

Each step reads the output of the one before. `search` and `fetch` use the
`gh` CLI; the rest run offline. The fetched text and everything quoting it
stay under ref/heldout/, outside the repository (it belongs to the
repositories' authors). The repository gets pointers only: the candidate
list and, per sampled item, repository, commit, path, blob SHA, rule and
offsets.

`check` stops unless src/ and uv.lock equal commit a57e19e, the rules the
pre-registration froze.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FROZEN = "a57e19e"
SEED = "20261119"
UA = "readcost-eval (https://github.com/arclabs561/readcost)"

FIRST_DAY, LAST_DAY = date(2026, 11, 2), date(2026, 11, 17)
STAR_FLOOR = 50
SEARCH_LIMIT = 1000
SPLIT = ("50..99", "100..499", ">=500")
SEARCH_GAP = 2.1

DEFAULT_RULES = ("stacked-nouns", "long-dependency", "inanimate-subject", "reduced-object-relative",
                 "hyphen-compound", "inline-list")
OPT_IN_RULES = ("participial-clause", "nominalization", "center-embedding", "undefined-acronym")
RULES = DEFAULT_RULES + OPT_IN_RULES
QUOTA = {"S1": {"default": 40, "opt-in": 20}, "S2": {"default": 20, "opt-in": 10}}
DECOY_QUOTA = {"S1": {"random": 40, "long": 40}, "S2": {"random": 20, "long": 20}}
PER_REPO_CAP = 2         # findings per repository, rule and stratum
DECOY_REPO_CAP = 1       # decoys per repository, kind and stratum
MIN_WORDS = 300
MAX_BYTES = 1_000_000
CONTEXT_CHARS = 240
BATCH_SIZE = 40
RATER_SEEDS = {"rater1": 1, "rater2": 2, "rater3": 3}

DOC_EXT = (".md", ".markdown", ".mdx")
DOC_PREFIX = ("docs/", "doc/", "design/", "rfcs/", "adr/")
DOC_INFIX = ("/adr/", "/design/")
DOC_SKIP_NAMES = ("readme", "changelog", "license", "contributing", "code_of_conduct", "security")
DOCS_PER_REPO = 2

CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}

# Two rules that RUBRIC does not define, verbatim from scripts/eval_optin_rules.py PROMPT.
EXTRA_DEFINITIONS = """- nominalization: an action turned into a noun with a light verb ("performs validation of" for "validates").
- participial-clause: a present participle clause tacked onto a sentence ("..., highlighting what changed")."""

REPLY_FORMAT = """Reply format

Each batch file is a JSON list of findings. Each finding has "i" (its id), "rule", "message", "excerpt"
(the flagged words), "sentence", and "before" and "after" (up to 240 characters of the source on each
side of the sentence, for context only; judge the finding in "sentence").

Reply with one JSON object for the batch, and nothing else:

{"labels": [{"i": 123456, "label": "c", "present": true, "cause": "short reason"}, ...]}

- one entry per finding in the batch, with its "i" unchanged;
- "label" is "c", "d" or "w";
- "present" is true or false;
- "cause" is a string under 8 words (it may be empty).

The labels of one rater, all batches together, are collected into one file: a JSON list of
{"id": <i>, "label": "c" | "d" | "w", "construction_present": true | false}
(an optional "cause" may stay). scripts/heldout_report.py also reads the reply objects above as they
are, one per batch, and accepts "i" for "id" and "present" for "construction_present"."""


# --- pure helpers (tested in tests/test_heldout_precision.py) ---

def day_queries(first: date = FIRST_DAY, last: date = LAST_DAY, floor: int = STAR_FLOOR) -> list[str]:
    out, d = [], first
    while d <= last:
        out.append(f"created:{d.isoformat()} stars:>={floor} fork:false archived:false")
        d += timedelta(days=1)
    return out


def split_query(q: str) -> list[str]:
    """The same day's query split by star ranges, for a day over the search limit."""
    return [re.sub(r"stars:\S+", f"stars:{s}", q) for s in SPLIT]


REPO_URL = re.compile(r"github\.com/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9._-]+)")
REPO_STR = re.compile(r"""["'`(\s]([A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+)["'`)\s]""")


def repo_names(text: str) -> set[str]:
    """owner/repo strings in text: GitHub URLs and quoted owner/repo pairs, lowercased."""
    out = {f"{o}/{r}".lower().removesuffix(".git") for o, r in REPO_URL.findall(text)}
    out |= {m.lower() for m in REPO_STR.findall(text)}
    return out


def excluded_repos() -> set[str]:
    """Repositories named anywhere under scripts/, eval/ or docs/ at the frozen commit."""
    files = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", FROZEN, "scripts", "eval", "docs"],
                           check=True, capture_output=True, text=True).stdout.split()
    names: set[str] = set()
    for f in files:
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{FROZEN}:{f}"], check=True, capture_output=True)
        names |= repo_names(blob.stdout.decode("utf-8", "replace"))
    return names


def excluded(repo: str, names: set[str]) -> str | None:
    if repo.split("/")[0].lower() == "arclabs561":
        return "owner arclabs561"
    if repo.lower() in names:
        return "in a development corpus"
    return None


def fenced_share(text: str) -> float:
    """Share of non-blank lines inside fenced code blocks (``` or ~~~), fences included."""
    inside, fence, code, total = False, "", 0, 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        total += 1
        m = re.match(r"(`{3,}|~{3,})", s)
        if inside:
            code += 1
            if m and s.startswith(fence) and s.strip(fence[0]) == "":
                inside = False
        elif m:
            inside, fence = True, m.group(1)
            code += 1
    return code / total if total else 0.0


def is_doc_path(path: str) -> bool:
    p = path.lower()
    name = p.rsplit("/", 1)[-1]
    if not p.endswith(DOC_EXT) or name.startswith(DOC_SKIP_NAMES):
        return False
    if any(x in p for x in ("node_modules/", "vendor/")):
        return False
    return p.startswith(DOC_PREFIX) or any(x in "/" + p for x in DOC_INFIX)


def pick_docs(repo: str, paths: list[str], k: int = DOCS_PER_REPO) -> list[str]:
    cands = sorted(p for p in paths if is_doc_path(p))
    if len(cands) <= k:
        return cands
    return sorted(random.Random(f"{SEED}:{repo}").sample(cands, k))


def finding_key(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def dedupe(items: list[dict], field: str = "sentence") -> list[dict]:
    """Drop an item whose rule and sentence equal an earlier one's, in key order."""
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["key"]):
        k = (it["rule"], it[field])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def draw(items: list[dict], quota: int, cap: int, seed: str) -> list[dict]:
    """Shuffle (from key order) with seed; take in order, at most cap per repository."""
    pool = sorted(items, key=lambda x: x["key"])
    random.Random(seed).shuffle(pool)
    per_repo: Counter = Counter()
    out = []
    for it in pool:
        if len(out) >= quota:
            break
        if per_repo[it["repo"]] >= cap:
            continue
        per_repo[it["repo"]] += 1
        out.append(it)
    return out


def rule_names(n: int, seed: str) -> list[str]:
    names = [RULES[i % len(RULES)] for i in range(n)]
    random.Random(seed).shuffle(names)
    return names


def decoy_span(tokens: list[tuple[str, str, bool]], rng: random.Random) -> tuple[int, int] | None:
    """Indexes (first, last) of a random run of 2 to 4 alphabetic tokens whose ends are content words.

    tokens: (text, pos, is_alpha) for each token of the sentence.
    """
    length = rng.choice((2, 3, 4))
    while length >= 2:
        runs = []
        for i in range(len(tokens) - length + 1):
            run = tokens[i:i + length]
            if all(t[2] for t in run) and run[0][1] in CONTENT_POS and run[-1][1] in CONTENT_POS:
                runs.append(i)
        if runs:
            i = rng.choice(runs)
            return i, i + length - 1
        length -= 1
    return None


def decoy_message(rule: str, words: list[str]) -> str:
    """The rule's own message template, filled from the decoy span's words."""
    a, b, ex, n = words[0], words[-1], " ".join(words), len(words)
    return {
        "stacked-nouns": f"{n} nouns stacked: '{ex}'",
        "hyphen-compound": f"coined compound modifier: '{ex}'",
        "inline-list": "4 items listed in one sentence",
        "long-dependency": f"'{a}' and '{b}' are {n - 1} words apart",
        "inanimate-subject": f"'{a} ... {b}': a person's verb with a non-person subject",
        "reduced-object-relative": f"'{ex}': object relative without 'that'",
        "nominalization": f"'{a} {b} of': the verb '{b}' would do",
        "participial-clause": f"', {a} ...' leaves its link to '{b}' unstated",
        "center-embedding": f"clause '{ex}' is nested 2 deep inside clauses that continue after it",
        "undefined-acronym": f"'{a}' is used without being spelled out",
    }[rule]


def context(source: str, start: int, end: int, width: int = CONTEXT_CHARS) -> tuple[str, str]:
    """Up to width characters before start and after end, cut at whitespace, spaces collapsed."""
    before = source[max(0, start - width):start]
    after = source[end:end + width]
    if start > width:  # cut inside the text: drop the partial first word
        parts = before.split(None, 1)
        before = parts[1] if len(parts) == 2 and not before[0].isspace() else before
    if end + width < len(source):  # and the partial last word
        parts = after.rsplit(None, 1)
        after = parts[0] if len(parts) == 2 and not after[-1].isspace() else after
    return " ".join(before.split()), " ".join(after.split())


def assign_ids(keys: list[str], seed: str = f"{SEED}:ids") -> dict[str, int]:
    ids = random.Random(seed).sample(range(100000, 1000000), len(keys))
    return dict(zip(sorted(keys), ids))


def batches(items: list[dict], seed: int, size: int = BATCH_SIZE) -> list[list[dict]]:
    """Items shuffled with seed, cut into batches of about size."""
    order = sorted(items, key=lambda x: x["i"])
    random.Random(seed).shuffle(order)
    n = max(1, round(len(order) / size))
    return [order[k * len(order) // n:(k + 1) * len(order) // n] for k in range(n)]


def rater_item(it: dict) -> dict:
    """The fields a rater sees: second_rater.py's, with context."""
    return {"i": it["i"], "rule": it["rule"], "message": it["message"], "excerpt": it["excerpt"],
            "sentence": it["sentence"], "before": it["before"], "after": it["after"]}


def rubric_text() -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    from second_rater import RUBRIC
    return ("Rubric (RUBRIC from scripts/second_rater.py, verbatim)\n\n" + RUBRIC
            + "\n\nTwo rules the list above does not define:\n" + EXTRA_DEFINITIONS
            + "\n\n" + REPLY_FORMAT + "\n")


# --- GitHub ---

_last_search = 0.0


def gh(args: list[str], tries: int = 4) -> str:
    for attempt in range(tries):
        p = subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}", *args], capture_output=True, text=True,
                           timeout=180, check=False)
        if p.returncode == 0:
            return p.stdout
        if "404" in p.stderr or "Not Found" in p.stderr:
            raise FileNotFoundError(p.stderr.strip()[:200])
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"gh api {' '.join(args)}: {p.stderr.strip()[:300]}")


def search_all(q: str, log: list) -> list[dict]:
    global _last_search
    items, page = [], 1
    while True:
        wait = SEARCH_GAP - (time.time() - _last_search)
        if wait > 0:
            time.sleep(wait)
        _last_search = time.time()
        res = json.loads(gh(["-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "sort=stars",
                             "-f", "order=desc", "-f", "per_page=100", "-f", f"page={page}"]))
        log.append({"q": q, "page": page, "total_count": res["total_count"],
                    "incomplete": res.get("incomplete_results"), "at": datetime.now(UTC).isoformat()})
        items += res["items"]
        if page == 1 and res["total_count"] > SEARCH_LIMIT:
            return [{"__split__": True}]
        if len(res["items"]) < 100 or len(items) >= min(res["total_count"], SEARCH_LIMIT):
            return items
        page += 1


def cmd_search(args) -> None:
    log: list = []
    seen: dict[str, dict] = {}
    for q in day_queries():
        got = search_all(q, log)
        queries = [q]
        if got and got[0].get("__split__"):
            got, queries = [], split_query(q)
            for sq in queries:
                got += search_all(sq, log)
        for it in got:
            seen.setdefault(it["full_name"], {
                "repo": it["full_name"], "stars": it["stargazers_count"], "created_at": it["created_at"],
                "fork": it["fork"], "archived": it["archived"], "default_branch": it["default_branch"],
                "query": queries[0] if len(queries) == 1 else q + " (split)"})
        print(f"{q}: {len(got)}", flush=True)
    out = ROOT / "eval/heldout/candidates.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(v) + "\n" for v in sorted(seen.values(), key=lambda v: v["repo"].lower())))
    (args.ref / "search-log.json").parent.mkdir(parents=True, exist_ok=True)
    (args.ref / "search-log.json").write_text(json.dumps(log, indent=1))
    print(len(seen), "candidates ->", out)


GQL = """query { %s }"""
GQL_REPO = """r%d: repository(owner: %s, name: %s) { isFork isArchived defaultBranchRef { name target { oid } } }"""


def head_commits(repos: list[str]) -> dict[str, dict]:
    out = {}
    for k in range(0, len(repos), 50):
        chunk = repos[k:k + 50]
        parts = [GQL_REPO % (i, json.dumps(r.split("/")[0]), json.dumps(r.split("/")[1])) for i, r in enumerate(chunk)]
        p = subprocess.run(["gh", "api", "graphql", "-f", "query=" + GQL % " ".join(parts)],
                           capture_output=True, text=True, timeout=180, check=False)
        data = json.loads(p.stdout or "{}").get("data") or {}
        for i, r in enumerate(chunk):
            node = data.get(f"r{i}")
            if node:
                ref = node.get("defaultBranchRef") or {}
                out[r] = {"fork": node["isFork"], "archived": node["isArchived"],
                          "commit": (ref.get("target") or {}).get("oid")}
    return out


def _store(ref: Path, repo: str, path: str, data: bytes) -> str:
    local = ref / "files" / repo / path
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(data)
    return str(local.relative_to(ref))


def fetch_readme(ref: Path, repo: str, commit: str) -> dict:
    try:
        meta = json.loads(gh([f"repos/{repo}/readme?ref={commit}"]))
    except FileNotFoundError:
        return {"drop": "no README"}
    if meta.get("size", 0) > MAX_BYTES or meta.get("encoding") != "base64":
        return {"drop": "README over 1 MB"}
    data = base64.b64decode(meta["content"])
    return {"path": meta["path"], "blob": meta["sha"], "bytes": len(data), "local": _store(ref, repo, meta["path"], data)}


def fetch_docs(ref: Path, repo: str, commit: str) -> list[dict]:
    try:
        tree = json.loads(gh([f"repos/{repo}/git/trees/{commit}?recursive=1"]))
    except FileNotFoundError:
        return []
    blobs = {t["path"]: t for t in tree.get("tree", []) if t["type"] == "blob"}
    out = []
    for path in pick_docs(repo, list(blobs)):
        t = blobs[path]
        if t.get("size", 0) > MAX_BYTES:
            out.append({"path": path, "blob": t["sha"], "drop": "over 1 MB"})
            continue
        data = base64.b64decode(json.loads(gh([f"repos/{repo}/git/blobs/{t['sha']}"]))["content"])
        out.append({"path": path, "blob": t["sha"], "bytes": len(data), "local": _store(ref, repo, path, data)})
    return out


def cmd_fetch(args) -> None:
    cands = [json.loads(x) for x in (ROOT / "eval/heldout/candidates.jsonl").read_text().splitlines()]
    names = excluded_repos()
    state_path = args.ref / "fetch-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    todo = []
    for c in cands:
        r = c["repo"]
        if r in state:
            continue
        why = excluded(r, names) or ("fork" if c["fork"] else None) or ("archived" if c["archived"] else None)
        if why:
            state[r] = {"drop": why}
        else:
            todo.append(r)
    heads = head_commits([r for r in todo if r not in state])
    for r in todo:
        h = heads.get(r)
        if not h or not h["commit"]:
            state[r] = {"drop": "no default branch"}
        elif h["fork"] or h["archived"]:
            state[r] = {"drop": "fork" if h["fork"] else "archived"}
        else:
            state[r] = {"commit": h["commit"], "pending": True}

    def one(r):
        st = state[r]
        st.update(fetch_readme(args.ref, r, st["commit"]))
        st.pop("pending", None)
        return r

    pending = [r for r, st in state.items() if st.get("pending")]
    with ThreadPoolExecutor(args.workers) as ex:
        for n, _ in enumerate(ex.map(one, pending), 1):
            if n % 200 == 0:
                state_path.write_text(json.dumps(state))
                print(f"{n}/{len(pending)} READMEs", flush=True)
    state_path.write_text(json.dumps(state))
    print("READMEs done", Counter(st.get("drop", "kept") for st in state.values()))


def cmd_fetch_docs(args) -> None:
    """S2: docs files from the repositories whose README passed every filter (after `check`)."""
    state = json.loads((args.ref / "fetch-state.json").read_text())
    kept = [json.loads(x) for x in (args.ref / "checked.jsonl").read_text().splitlines()]
    repos = sorted({k["repo"] for k in kept if k["stratum"] == "S1" and not k.get("drop")})

    def one(r):
        if "docs" not in state[r]:
            state[r]["docs"] = fetch_docs(args.ref, r, state[r]["commit"])
        return r

    with ThreadPoolExecutor(args.workers) as ex:
        for n, _ in enumerate(ex.map(one, repos), 1):
            if n % 200 == 0:
                (args.ref / "fetch-state.json").write_text(json.dumps(state))
                print(f"{n}/{len(repos)} repos' docs", flush=True)
    (args.ref / "fetch-state.json").write_text(json.dumps(state))
    print(sum(len(state[r]["docs"]) for r in repos), "docs files")


# --- readcost ---

def frozen_check() -> None:
    diff = subprocess.run(["git", "-C", str(ROOT), "diff", "--stat", FROZEN, "--", "src", "uv.lock"],
                          capture_output=True, text=True, check=True).stdout
    if diff.strip():
        sys.exit(f"src/ or uv.lock differ from {FROZEN}; the pre-registration froze them:\n{diff}")


def analyzer():
    from readcost.config import Config
    from readcost.engine import Analyzer
    cfg = Config()
    cfg.rules = {r: "info" for r in OPT_IN_RULES}
    return Analyzer(config=cfg)


class _CachingNLP:
    """Wraps the spaCy pipeline so the decoy pass reuses the parses of the check."""

    def __init__(self, nlp):
        self.nlp, self.docs = nlp, {}

    def pipe(self, texts):
        for doc in self.nlp.pipe(texts):
            self.docs[doc.text] = doc
            yield doc

    def __call__(self, text):
        if text not in self.docs:
            self.docs[text] = self.nlp(text)
        return self.docs[text]


def check_one(an, local: Path, repo: str, commit: str, path: str, blob: str, stratum: str) -> dict:
    from readcost.engine import read_source
    from readcost.extract import extract
    from readcost.features import Context, show

    text, _ = read_source(str(local))
    rec = {"repo": repo, "commit": commit, "path": path, "blob": blob, "stratum": stratum}
    share = fenced_share(text)
    nlp = an.nlp
    cache = _CachingNLP(nlp)
    an._nlp = cache
    try:
        res = an.check_text(text, None, path)
    finally:
        an._nlp = nlp
    rec.update(words=res.words, fenced_share=round(share, 3))
    if any("not English" in n for n in res.notes):
        return rec | {"drop": "not English"}
    if res.words < MIN_WORDS:
        return rec | {"drop": f"under {MIN_WORDS} words"}
    if share > 0.5:
        return rec | {"drop": "mostly code"}
    findings = []
    for f in res.findings:
        if f.feature not in RULES or f.start is None:
            continue
        findings.append({"rule": f.feature, "message": f.message, "excerpt": f.excerpt, "sentence": f.sentence,
                         "start": f.start, "end": f.end, "sentence_start": f.sentence_start,
                         "sentence_end": f.sentence_end,
                         "key": finding_key(repo, commit, path, f.feature, f.start, f.end)})
    taken = [(f.sentence_start, f.sentence_end) for f in res.findings if f.sentence_start is not None]
    taken += [(f.start, f.end) for f in res.findings if f.start is not None]
    sentences = []
    segments = extract(text, path, None, comments=an.cfg.comments)
    ctx = Context(an.cfg, an.profile, an.allow, set())
    for seg in segments:
        doc = cache(seg.text)
        ctx.codes = seg.codes
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) < 4 or not any(t.pos_ in ("VERB", "AUX") for t in sent):
                continue
            whole = seg.span(sent.start_char, sent.end_char)
            if not whole or any(a < whole[1] and whole[0] < b for a, b in taken):
                continue
            toks = [[t.text, t.pos_, t.is_alpha, *(seg.span(t.idx, t.idx + len(t.text)) or (None, None))]
                    for t in sent]
            sentences.append({"start": whole[0], "end": whole[1], "words": len(words),
                              "sentence": show(ctx, doc, sent.start, sent.end - 1), "tokens": toks})
    return rec | {"findings": findings, "sentences": sentences}


def cmd_check(args) -> None:
    frozen_check()
    import readcost
    state = json.loads((args.ref / "fetch-state.json").read_text())
    stratum = args.stratum
    files = []
    for r, st in sorted(state.items(), key=lambda kv: kv[0].lower()):
        if stratum == "S1" and st.get("local"):
            files.append((r, st["commit"], st["path"], st["blob"], st["local"]))
        if stratum == "S2":
            for d in st.get("docs", []):
                if d.get("local"):
                    files.append((r, st["commit"], d["path"], d["blob"], d["local"]))
    out_path = args.ref / "checked.jsonl"
    old = [json.loads(x) for x in out_path.read_text().splitlines()] if out_path.exists() else []
    old = [o for o in old if o["stratum"] != stratum]
    an = analyzer()
    seen_blobs: set[str] = set()
    rows = []
    t0 = time.time()
    for n, (r, commit, path, blob, local) in enumerate(files, 1):
        if blob in seen_blobs:
            rows.append({"repo": r, "commit": commit, "path": path, "blob": blob, "stratum": stratum,
                         "drop": "duplicate file"})
            continue
        row = check_one(an, args.ref / local, r, commit, path, blob, stratum)
        if not row.get("drop"):
            seen_blobs.add(blob)
        rows.append(row)
        if n % 100 == 0:
            print(f"{stratum}: {n}/{len(files)} in {time.time() - t0:.0f}s", flush=True)
    meta = {"readcost": readcost.__version__,
            "features_sha256": hashlib.sha256((ROOT / "src/readcost/features.py").read_bytes()).hexdigest()}
    (args.ref / f"check-meta-{stratum}.json").write_text(json.dumps(meta))
    out_path.write_text("".join(json.dumps(x) + "\n" for x in old + rows))
    print(stratum, Counter(x.get("drop", "kept") for x in rows))


# --- the draw ---

def build_sample(checked: list[dict], sources: dict[tuple, str]) -> tuple[list[dict], dict]:
    """The pre-registered draw: findings per rule, then decoys. sources: (repo, path) -> text."""
    counts: dict = {"findings": {}, "deduped": {}, "sampled": {}, "decoy_pool": {}, "decoys": {}}
    sample = []
    for stratum in ("S1", "S2"):
        kept = [c for c in checked if c["stratum"] == stratum and not c.get("drop")]
        allf = [f | {"repo": c["repo"], "commit": c["commit"], "path": c["path"], "blob": c["blob"]}
                for c in kept for f in c["findings"]]
        counts["findings"][stratum] = dict(Counter(f["rule"] for f in allf))
        deduped = dedupe(allf)
        counts["deduped"][stratum] = dict(Counter(f["rule"] for f in deduped))
        by_rule = defaultdict(list)
        for f in deduped:
            by_rule[f["rule"]].append(f)
        for rule in RULES:
            quota = QUOTA[stratum]["default" if rule in DEFAULT_RULES else "opt-in"]
            got = draw(by_rule[rule], quota, PER_REPO_CAP, f"{SEED}:{stratum}:{rule}")
            counts["sampled"].setdefault(stratum, {})[rule] = len(got)
            sample += [f | {"stratum": stratum, "decoy": ""} for f in got]
        # decoys
        sents = []
        for c in kept:
            for s in c["sentences"]:
                sents.append(s | {"repo": c["repo"], "commit": c["commit"], "path": c["path"], "blob": c["blob"],
                                  "rule": "", "key": finding_key(c["repo"], c["commit"], c["path"], "sentence",
                                                                 s["start"], s["end"])})
        sents = dedupe(sents)
        pools = {"random": sents, "long": []}
        by_file = defaultdict(list)
        for s in sents:
            by_file[(s["repo"], s["path"])].append(s)
        for _, ss in sorted(by_file.items()):
            pools["long"].append(max(sorted(ss, key=lambda s: s["start"]), key=lambda s: s["words"]))
        counts["decoy_pool"][stratum] = {k: len(v) for k, v in pools.items()}
        names = rule_names(sum(DECOY_QUOTA[stratum].values()), f"{SEED}:{stratum}:decoy-rules")
        used: set[str] = set()
        decoys = []
        for kind in ("random", "long"):
            pool = sorted(pools[kind], key=lambda x: x["key"])
            random.Random(f"{SEED}:{stratum}:decoy-{kind}").shuffle(pool)
            per_repo: Counter = Counter()
            got = 0
            for s in pool:
                if got >= DECOY_QUOTA[stratum][kind]:
                    break
                if per_repo[s["repo"]] >= DECOY_REPO_CAP or s["key"] in used:
                    continue
                span = decoy_span([(t[0], t[1], t[2]) for t in s["tokens"]],
                                  random.Random(f"{SEED}:span:{s['key']}"))
                if span is None:
                    continue
                toks = s["tokens"][span[0]:span[1] + 1]
                if toks[0][3] is None or toks[-1][4] is None:
                    continue
                per_repo[s["repo"]] += 1
                used.add(s["key"])
                got += 1
                rule = names[len(decoys)]
                words = [t[0] for t in toks]
                start, end = toks[0][3], toks[-1][4]
                src = sources[(s["repo"], s["path"])]
                decoys.append({"rule": rule, "message": decoy_message(rule, words), "excerpt": src[start:end],
                               "sentence": s["sentence"], "start": start, "end": end,
                               "sentence_start": s["start"], "sentence_end": s["end"],
                               "repo": s["repo"], "commit": s["commit"], "path": s["path"], "blob": s["blob"],
                               "stratum": stratum, "decoy": kind,
                               "key": finding_key(s["repo"], s["commit"], s["path"], f"decoy-{kind}", start, end)})
        counts["decoys"][stratum] = dict(Counter(d["decoy"] for d in decoys))
        sample += decoys
    ids = assign_ids([it["key"] for it in sample])
    for it in sample:
        it["i"] = ids[it["key"]]
        b, a = context(sources[(it["repo"], it["path"])], it["sentence_start"], it["sentence_end"])
        it["before"], it["after"] = b, a
    return sorted(sample, key=lambda x: x["key"]), counts


POINTER_FIELDS = ("i", "key", "stratum", "decoy", "rule", "repo", "commit", "path", "blob",
                  "start", "end", "sentence_start", "sentence_end")


def cmd_sample(args) -> None:
    checked = [json.loads(x) for x in (args.ref / "checked.jsonl").read_text().splitlines()]
    state = json.loads((args.ref / "fetch-state.json").read_text())
    from readcost.engine import read_source
    sources = {}
    for r, st in state.items():
        if st.get("local"):
            sources[(r, st["path"])] = read_source(str(args.ref / st["local"]))[0]
        for d in st.get("docs", []):
            if d.get("local"):
                sources[(r, d["path"])] = read_source(str(args.ref / d["local"]))[0]
    sample, counts = build_sample(checked, sources)
    (args.ref / "sample.jsonl").write_text("".join(json.dumps(x) + "\n" for x in sample))
    out = ROOT / "eval/heldout/sample.jsonl"
    out.write_text("".join(json.dumps({k: x[k] for k in POINTER_FIELDS}) + "\n" for x in sample))
    files = Counter((c["stratum"], c.get("drop", "kept")) for c in checked)
    counts["files"] = {f"{s}: {d}": n for (s, d), n in sorted(files.items())}
    counts["fetch"] = dict(Counter(st.get("drop", "fetched") for st in state.values()))
    (ROOT / "eval/heldout/counts.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(json.dumps(counts, indent=1))


def cmd_batches(args) -> None:
    sample = [json.loads(x) for x in (args.ref / "sample.jsonl").read_text().splitlines()]
    items = [rater_item(x) for x in sample]
    args.batches.mkdir(parents=True, exist_ok=True)
    (args.batches / "RUBRIC.txt").write_text(rubric_text())
    for rater, seed in RATER_SEEDS.items():
        d = args.batches / rater
        d.mkdir(exist_ok=True)
        for old in d.glob("batch-*.json"):
            old.unlink()
        for k, b in enumerate(batches(items, seed), 1):
            (d / f"batch-{k:02d}.json").write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n")
    (args.batches / "labels").mkdir(exist_ok=True)
    print(len(items), "items;", {r: len(list((args.batches / r).glob("batch-*.json"))) for r in RATER_SEEDS})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["search", "fetch", "check", "docs", "sample", "batches"])
    ap.add_argument("--ref", type=Path, default=ROOT / "ref/heldout")
    ap.add_argument("--batches", type=Path, default=Path("/home/claude/heldout-batches"))
    ap.add_argument("--stratum", choices=["S1", "S2"], default="S1")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)
    args.ref.mkdir(parents=True, exist_ok=True)
    {"search": cmd_search, "fetch": cmd_fetch, "check": cmd_check, "docs": cmd_fetch_docs,
     "sample": cmd_sample, "batches": cmd_batches}[args.step](args)


if __name__ == "__main__":
    main()
