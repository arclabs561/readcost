"""Does readcost's feedback make an agent's edit easier to read? Three arms, judged blind.

    uv run python scripts/eval_edit_arms.py candidates eval/edit-arms          # search GitHub (gh login)
    uv run python scripts/eval_edit_arms.py draw eval/edit-arms                # pointers to 60 paragraphs
    uv run python scripts/eval_edit_arms.py verify                             # readcost is still a57e19e
    uv run python scripts/eval_edit_arms.py fetch eval/edit-arms ref/edit-arms # text, cut at the pointers
    EVAL_OPENROUTER_API_KEY=... uv run python scripts/eval_edit_arms.py run ref/edit-arms
    uv run python scripts/eval_edit_arms.py report ref/edit-arms --json report.json

The plan, prompts, models and decision rules are fixed in
docs/prereg/edit-arms.md; this script implements them. Arm A is the
original paragraph, arm B one edit given readcost's `-o agent` feedback,
arm C one edit given the same instruction without it. Judges from other
model families say which of two versions is easier to read (each pair in
both orders) and list facts each edit lost, added or changed.

Only pointers (repository, commit, path, offsets, SHA-256) are committed,
under eval/edit-arms/. The text is fetched at run time and stays under
ref/, with the cache of model replies. The model client is
`rater_ensemble.ask`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

PINNED = "a57e19e"
SEED = "20261119:edit-arms"
DAYS = [f"2026-11-{d:02d}" for d in range(2, 18)]
QUERY = "created:{day} stars:10..49 fork:false archived:false"
N_PARAGRAPHS = 60
MIN_WORDS, MAX_WORDS, MIN_FINDINGS = 120, 260, 2
MAX_BYTES = 1_000_000
BUDGET_FACTOR = 1.2

EDITORS = ["anthropic/claude-opus-5.5", "google/gemini-4-argon", "mistralai/mistral-large-4-0"]
JUDGES = ["moonshotai/kimi-k3.1-pro", "deepseek/deepseek-v4.1-flash", "x-ai/grok-4.7"]
PAIRS = [("B", "C"), ("B", "A"), ("C", "A")]
COST_CAP = 60.0
CALL_CAP = 5200
NO_COST = 0.05     # a reply that reports no cost counts as this much
RESERVE = 0.10     # held back per call in flight, so the cap is not crossed
SMALLEST = 0.55
BOOT = 10_000

SYSTEM = ("You edit technical documentation. You will get one paragraph from the README or the "
          "documentation of a software project. Return the whole revised paragraph. Keep its "
          "Markdown, such as links and inline code.")
INSTRUCTION = ("Revise this paragraph to make it easier to read. Keep every fact.\n"
               "The revision must be at most {budget} words.")
ARM_C = INSTRUCTION + "\n\nParagraph:\n{text}"
ARM_B = INSTRUCTION + "\n\nA prose checker reported this about the paragraph:\n{feedback}\n\nParagraph:\n{text}"
PAIRWISE = """Here are two versions of one paragraph from the documentation of a software project. The intended reader is a developer who is new to the project and reads its documentation to learn what it does and how to use it.

Which version is easier for that reader to read and understand? Judge only how easy each is to read. Assume both say the same thing; a separate check compares their content. Answer "tie" only if neither is easier to read.

Version 1:
{first}

Version 2:
{second}

Give your reason in one or two sentences, then your answer: "1", "2" or "tie"."""
PAIRWISE_SCHEMA = {"type": "object", "properties": {
    "reason": {"type": "string"}, "easier": {"type": "string", "enum": ["1", "2", "tie"]}},
    "required": ["reason", "easier"], "additionalProperties": False}
TEXT_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
               "additionalProperties": False}

DOC_PREFIXES = ("docs/", "doc/", "design/", "rfcs/", "adr/")
DOC_SKIP = ("readme", "changelog", "license", "contributing", "code_of_conduct", "security")
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
BAD_START = re.compile(r" {0,3}([#>|\-*+<!\[=]|\d+[.)])")


# ---- paragraphs ------------------------------------------------------------

def blocks(text: str) -> list[tuple[int, int]]:
    """Offsets of runs of non-blank lines, outside fenced code and HTML comments.

    A fence line, or a line in or touching an HTML comment, ends a run as a
    blank line does. The end offset leaves out the last line's line break.
    """
    out: list[tuple[int, int]] = []
    start = end = None
    fence = None
    comment = False
    pos = 0

    def close():
        nonlocal start
        if start is not None:
            out.append((start, end))
        start = None

    for line in text.splitlines(keepends=True):
        here, pos = pos, pos + len(line)
        body = line.rstrip("\r\n")
        m = FENCE.match(body)
        if fence:
            if m and m.group(1)[0] == fence and body.strip() == body.strip()[0] * len(body.strip()):
                fence = None
            close()
            continue
        if m:
            fence = m.group(1)[0]
            close()
            continue
        if comment or "<!--" in body:
            if comment:
                comment = "-->" not in body
            else:
                comment = "-->" not in body.split("<!--", 1)[1]
            close()
            continue
        if not body.strip():
            close()
            continue
        if start is None:
            start = here
        end = here + len(body)
    close()
    return out


def shape_ok(para: str) -> bool:
    """The prereg's rules 1 to 3: not a heading, list, quote, table or code; 120 to 260 words."""
    lines = para.splitlines()
    if not lines or BAD_START.match(lines[0]):
        return False
    if any(ln.startswith(("    ", "\t")) or ln.lstrip(" ").startswith("|") for ln in lines):
        return False
    return MIN_WORDS <= len(para.split()) <= MAX_WORDS


def eligible(text: str, path: str, analyzer) -> list[dict]:
    """Eligible paragraphs of one decoded file, with offsets, SHA-256, words and findings."""
    from readcost.lang import other_language
    out = []
    for start, end in blocks(text):
        para = text[start:end]
        if not shape_ok(para) or other_language(para):
            continue
        n = len(analyzer.check_text(para, "markdown", path).findings)
        if n >= MIN_FINDINGS:
            out.append({"path": path, "start": start, "end": end, "sha256": sha(para),
                        "words": len(para.split()), "findings": n})
    return out


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def doc_paths(paths: list[str], repo: str) -> list[str]:
    """Up to two documentation files, drawn with the repository's seed from the sorted matches."""
    keep = []
    for p in sorted(paths):
        low = p.lower()
        name = low.rsplit("/", 1)[-1]
        if not low.endswith((".md", ".markdown", ".mdx")) or name.startswith(DOC_SKIP):
            continue
        if low.startswith(DOC_PREFIXES) or "/adr/" in low or "/design/" in low:
            keep.append(p)
    rng = random.Random(f"{SEED}:{repo}")
    return rng.sample(keep, min(2, len(keep)))


def exclusion_patterns(rev: str = PINNED) -> str:
    """Text of every file under scripts/, eval/ and docs/ at ``rev``, lowercased."""
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", rev, "scripts", "eval", "docs"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    parts = []
    for n in names:
        r = subprocess.run(["git", "show", f"{rev}:{n}"], cwd=ROOT, capture_output=True, check=False)
        parts.append(r.stdout.decode("utf-8", "replace"))
    return "\n".join(parts).lower()


def named_in(repo: str, text: str) -> bool:
    return re.search(r"(?<![\w.-])" + re.escape(repo.lower()) + r"(?![\w-])", text) is not None


def heldout_text() -> str:
    parts = []
    for ref in ("origin/main", "origin/exp/heldout-precision"):
        r = subprocess.run(["git", "show", f"{ref}:eval/heldout/candidates.jsonl"], cwd=ROOT,
                           capture_output=True, check=False)
        if r.returncode == 0:
            parts.append(r.stdout.decode("utf-8", "replace"))
    return "\n".join(parts).lower()


def drop_reason(item: dict, corpus_text: str, held_text: str) -> str | None:
    repo = item["full_name"]
    if repo.split("/")[0].lower() == "arclabs561" or named_in(repo, corpus_text):
        return "named in an evaluation corpus"
    if named_in(repo, held_text):
        return "in the held-out precision candidates"
    if item.get("fork") or item.get("archived"):
        return "fork or archived"
    return None


def walk(repos: list[dict], files_for, analyzer, n: int = N_PARAGRAPHS) -> tuple[list[dict], list[dict]]:
    """Shuffle the kept repositories and take one eligible paragraph from each until there are n.

    ``files_for(repo)`` returns (commit, [(path, text)]) or a reason string.
    """
    order = sorted(r["full_name"] for r in repos)
    random.Random(SEED).shuffle(order)
    picked, log, seen = [], [], set()
    for repo in order:
        if len(picked) >= n:
            break
        got = files_for(repo)
        if isinstance(got, str):
            log.append({"repo": repo, "outcome": got})
            continue
        commit, files = got
        cands = []
        for path, text in files:
            cands += [c for c in eligible(text, path, analyzer) if c["sha256"] not in seen]
        cands.sort(key=lambda c: (c["path"], c["start"]))
        if not cands:
            log.append({"repo": repo, "outcome": "no eligible paragraph"})
            continue
        c = random.Random(f"{SEED}:{repo}:pick").choice(cands)
        seen.add(c["sha256"])
        picked.append({"id": c["sha256"][:12], "repo": repo, "commit": commit, **c})
        log.append({"repo": repo, "outcome": "drawn", "eligible": len(cands)})
    return picked, log


# ---- GitHub ----------------------------------------------------------------

def raw_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path)}"


def get_raw(repo: str, commit: str, path: str) -> str:
    with urllib.request.urlopen(raw_url(repo, commit, path), timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


README_ORDER = ("readme.md", "readme.markdown", "readme.mdx", "readme.rst", "readme.txt", "readme")


def pick_readme(sizes: dict[str, int]) -> str | None:
    """The README GitHub would show: in the root, then .github/, then docs/, by extension in README_ORDER."""
    for folder in ("", ".github/", "docs/"):
        here = sorted(p for p in sizes if p.lower().startswith(folder) and "/" not in p[len(folder):])
        for name in README_ORDER:
            for p in here:
                if p[len(folder):].lower() == name:
                    return p
    return None


def tree(repo: str) -> tuple[str, dict[str, int]] | None:
    """Head commit of the default branch and {path: size} of its files, from a clone without blobs."""
    import os
    import tempfile
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    with tempfile.TemporaryDirectory() as d:
        g = f"{d}/g"
        r = subprocess.run(["git", "clone", "-q", "--bare", "--depth", "1", "--filter=blob:none",
                            f"https://github.com/{repo}", g], capture_output=True, timeout=180, check=False, env=env)
        if r.returncode != 0:
            return None
        commit = subprocess.run(["git", "-C", g, "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
        out = subprocess.run(["git", "-C", g, "ls-tree", "-r", "-l", "-z", "HEAD"], capture_output=True,
                             text=True, check=True).stdout
    sizes = {}
    for entry in out.split("\0"):
        if not entry:
            continue
        info, path = entry.split("\t", 1)
        _mode, kind, _sha, size = info.split()
        if kind == "blob" and size != "-":
            sizes[path] = int(size)
    return commit, sizes


def github_files(repo: str, get_tree=tree, get=None):
    """(commit, [(path, text)]) for a repository's README and up to two documentation files, or a reason."""
    get = get or get_raw
    got = get_tree(repo)
    if got is None:
        return "repository unavailable"
    commit, sizes = got
    readme = pick_readme(sizes)
    if readme is None:
        return "no README"
    if sizes[readme] > MAX_BYTES:
        return "README over 1 MB"
    files = [(readme, get(repo, commit, readme))]
    for p in doc_paths([x for x in sizes if x != readme], repo):
        if sizes[p] <= MAX_BYTES:
            files.append((p, get(repo, commit, p)))
    return commit, files


def candidates(out: Path) -> None:
    import fetch_github_readmes as fgr
    rows, seen = [], set()
    for day in DAYS:
        page = 1
        while True:
            data = fgr.search(QUERY.format(day=day), page, 100)
            items = data.get("items", [])
            for it in items:
                if it["full_name"] not in seen:
                    seen.add(it["full_name"])
                    rows.append({"repo": it["full_name"], "stars": it["stargazers_count"],
                                 "created_at": it["created_at"], "fork": it["fork"], "archived": it["archived"],
                                 "default_branch": it["default_branch"]})
            print(day, page, len(items), data.get("total_count"), flush=True)
            if len(items) < 100 or page * 100 >= min(1000, data.get("total_count", 0)):
                break
            page += 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sorted(rows, key=lambda r: r["repo"])))
    print(len(rows), "candidates")


def draw(out: Path) -> None:
    from readcost import Analyzer, Config
    rows = [json.loads(x) for x in (out / "candidates.jsonl").read_text().splitlines()]
    corpus_text, held = exclusion_patterns(), heldout_text()
    kept, drops = [], Counter()
    for r in rows:
        why = drop_reason({"full_name": r["repo"], **r}, corpus_text, held)
        if why:
            drops[why] += 1
        else:
            kept.append({"full_name": r["repo"], **r})
    picked, log = walk(kept, github_files, Analyzer(Config()))
    (out / "paragraphs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in picked))
    (out / "walk.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
    print(json.dumps({"candidates": len(rows), "dropped": dict(drops), "kept": len(kept), "walked": len(log),
                      "outcomes": dict(Counter(x["outcome"] for x in log)), "drawn": len(picked)}, indent=1))


def fetch(pointers: Path, ref: Path, get=get_raw) -> list[dict]:
    """Cut each paragraph out of its file at its commit; leave out those whose SHA-256 differs."""
    out, missing = [], []
    cache: dict = {}
    for p in map(json.loads, (pointers / "paragraphs.jsonl").read_text().splitlines()):
        key = (p["repo"], p["commit"], p["path"])
        try:
            if key not in cache:
                cache[key] = get(*key)
            text = cache[key][p["start"]:p["end"]]
        except OSError as exc:
            missing.append({"id": p["id"], "why": str(exc)[:200]})
            continue
        if sha(text) != p["sha256"]:
            missing.append({"id": p["id"], "why": "SHA-256 differs"})
            continue
        out.append({**p, "text": text})
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "texts.jsonl").write_text("".join(json.dumps(p) + "\n" for p in out))
    (ref / "missing.json").write_text(json.dumps(missing, indent=1))
    print(len(out), "paragraphs fetched,", len(missing), "missing")
    return out


def verify() -> int:
    r = subprocess.run(["git", "diff", "--quiet", PINNED, "--", "src", "uv.lock"], cwd=ROOT, check=False)
    if r.returncode != 0:
        print(f"src/ or uv.lock differs from {PINNED}; the pre-registration needs an amendment", file=sys.stderr)
        return 1
    print(f"src/ and uv.lock match {PINNED}")
    return 0


# ---- prompts ---------------------------------------------------------------

def budget(text: str) -> int:
    return math.ceil(BUDGET_FACTOR * len(text.split()))


def feedback(analyzer, text: str) -> str:
    from readcost import report
    return report.agent([analyzer.check_text(text, "markdown", "p.md")], feedback_link=False)


def edit_prompt(arm: str, text: str, fb: str = "") -> str:
    if arm == "B":
        return ARM_B.format(budget=budget(text), feedback=fb, text=text)
    return ARM_C.format(budget=budget(text), text=text)


def pair_prompt(first: str, second: str) -> str:
    return PAIRWISE.format(first=first, second=second)


def fact_prompt(original: str, edit: str) -> str:
    import eval_agent_loop
    return eval_agent_loop.JUDGE_PROMPT.format(a=original, b=edit)


def fact_schema() -> dict:
    import eval_agent_loop
    return eval_agent_loop.JUDGE_SCHEMA


def judge_calls(units: list[tuple[str, str]], pairs, judges, shuffle_seed: str) -> list[dict]:
    """Every (unit, pair, judge, order), shuffled. Order 0 shows X first; order 1 shows Y first."""
    calls = [{"id": pid, "editor": ed, "pair": f"{x}{y}", "judge": j, "order": o}
             for pid, ed in units for x, y in pairs for j in judges for o in (0, 1)]
    random.Random(shuffle_seed).shuffle(calls)
    return calls


def shown(call: dict) -> tuple[str, str]:
    """The arms shown as Version 1 and Version 2."""
    x, y = call["pair"]
    return (x, y) if call["order"] == 0 else (y, x)


def parse_easier(data: dict | None) -> str | None:
    """'1', '2' or 'tie' from a judge reply, or None."""
    if not data:
        return None
    v = str(data.get("easier", "")).strip().lower().strip('"\'.')
    if v in ("1", "2", "tie"):
        return v
    m = re.fullmatch(r"(?:version\s*)?([12])", v)
    if m:
        return m.group(1)
    return "tie" if v.startswith("tie") or v in ("neither", "equal", "same") else None


def chosen_arm(call: dict, easier: str | None) -> str | None:
    if easier is None:
        return None
    if easier == "tie":
        return "tie"
    return shown(call)[int(easier) - 1]


# ---- model calls, cache and caps --------------------------------------------

class CapReached(Exception):
    pass


class Client:
    """`rater_ensemble.ask` behind a cache of replies and the cost and call caps.

    The cache is a JSON-lines file of {key, model, data, meta}. Every line
    counts toward the caps, so the caps hold across runs that share it. A
    key whose lines all failed is asked again.
    """

    def __init__(self, path: Path, ask=None, cost_cap: float = COST_CAP, call_cap: int = CALL_CAP):
        if ask is None:
            import rater_ensemble
            ask = rater_ensemble.ask
        self.ask, self.path = ask, path
        self.cost_cap, self.call_cap = cost_cap, call_cap
        self.lock = threading.Lock()
        self.ok: dict[str, dict] = {}
        self.spent, self.calls, self.cached_hits, self.new_calls, self.reserved = 0.0, 0, 0, 0, 0.0
        self.served: dict[str, Counter] = defaultdict(Counter)
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                self._count(row)

    @staticmethod
    def key(model: str, system: str | None, prompt: str) -> str:
        return sha(json.dumps([model, system, prompt]))

    def _count(self, row: dict) -> None:
        self.calls += 1
        meta = row.get("meta") or {}
        if row.get("data") is not None:
            self.ok[row["key"]] = row
            self.spent += meta["cost"] if isinstance(meta.get("cost"), (int, float)) else NO_COST
            self.served[row["model"]][meta.get("served") or "?"] += 1
        elif isinstance(meta.get("cost"), (int, float)):
            self.spent += meta["cost"]

    def get(self, model: str, system: str | None, prompt: str) -> dict | None:
        """A cached reply, without asking."""
        row = self.ok.get(self.key(model, system, prompt))
        return row["data"] if row else None

    def __call__(self, model: str, system: str | None, prompt: str, schema: dict) -> dict | None:
        k = self.key(model, system, prompt)
        with self.lock:
            if k in self.ok:
                self.cached_hits += 1
                return self.ok[k]["data"]
            if self.calls + 1 > self.call_cap or self.spent + self.reserved + RESERVE > self.cost_cap:
                raise CapReached(f"cap reached: {self.calls} calls, ${self.spent:.2f}")
            self.calls += 1
            self.reserved += RESERVE
        try:
            data, meta = self.ask(model, prompt, schema, system=system)
        finally:
            with self.lock:
                self.reserved -= RESERVE
        row = {"key": k, "model": model, "data": data, "meta": meta}
        with self.lock:
            self.calls -= 1
            self._count(row)
            self.new_calls += 1
            with self.path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
        return data


def _pool(jobs, fn, workers: int) -> bool:
    """Run fn over jobs; False if a cap stopped the phase."""
    stop = threading.Event()

    def one(job):
        if stop.is_set():
            return
        try:
            fn(job)
        except CapReached as exc:
            if not stop.is_set():
                print(exc, flush=True)
            stop.set()
    with ThreadPoolExecutor(max(1, workers)) as ex:
        list(ex.map(one, jobs))
    return not stop.is_set()


def run(ref: Path, client: Client, analyzer, editors=EDITORS, judges=JUDGES, workers: int = 8) -> dict:
    """The five phases in the prereg's order. Returns which phases finished."""
    paras = [json.loads(x) for x in (ref / "texts.jsonl").read_text().splitlines()]
    fb = {p["id"]: feedback(analyzer, p["text"]) for p in paras}
    status = {}

    def edits_phase():
        jobs = [(p, ed, arm) for p in paras for ed in editors for arm in ("B", "C")]

        def one(job):
            p, ed, arm = job
            client(ed, SYSTEM, edit_prompt(arm, p["text"], fb[p["id"]]), TEXT_SCHEMA)
        ok = _pool(jobs, one, workers)
        missing = [j for j in jobs if not edit_of(client, *j, fb)]
        return ok and _pool(missing, one, workers)  # asked once more at the end

    def judging(pairs, tag):
        units = [(p["id"], ed) for p in paras for ed in editors]
        texts = {p["id"]: p["text"] for p in paras}
        calls = judge_calls(units, pairs, judges, f"{SEED}:calls:{tag}")

        def one(c):
            a, b = (arm_texts(client, texts, c["id"], c["editor"], fb)[s] for s in shown(c))
            if a is None or b is None:
                return
            client(c["judge"], None, pair_prompt(a, b), PAIRWISE_SCHEMA)
        ok = _pool(calls, one, workers)
        def shown_ok(c):
            t = arm_texts(client, texts, c["id"], c["editor"], fb)
            return all(t[s] is not None for s in shown(c))
        again = [c for c in calls if shown_ok(c) and verdict(client, texts, c, fb) is None]
        return ok and _pool(again, one, workers)

    def facts_phase():
        texts = {p["id"]: p["text"] for p in paras}
        jobs = [(p["id"], ed, arm, j) for p in paras for ed in editors for arm in ("B", "C") for j in judges]
        random.Random(f"{SEED}:calls:facts").shuffle(jobs)

        def one(job):
            pid, ed, arm, j = job
            e = arm_texts(client, texts, pid, ed, fb)[arm]
            if e is not None:
                client(j, None, fact_prompt(texts[pid], e), fact_schema())
        ok = _pool(jobs, one, workers)
        again = [jb for jb in jobs if arm_texts(client, texts, jb[0], jb[1], fb)[jb[2]] is not None
                 and fact_of(client, texts, *jb, fb) is None]
        return ok and _pool(again, one, workers)

    for name, phase in [("edits", edits_phase), ("BC", lambda: judging([("B", "C")], "BC")),
                        ("facts", facts_phase), ("BA", lambda: judging([("B", "A")], "BA")),
                        ("CA", lambda: judging([("C", "A")], "CA"))]:
        status[name] = bool(phase())
        print(name, "done" if status[name] else "stopped", f"{client.calls} calls, ${client.spent:.2f}", flush=True)
        if not status[name]:
            break
    (ref / "status.json").write_text(json.dumps({"phases": status, "calls": client.calls,
                                                 "spent": round(client.spent, 4)}, indent=1))
    return status


def edit_of(client, p: dict, ed: str, arm: str, fb: dict) -> str | None:
    data = client.get(ed, SYSTEM, edit_prompt(arm, p["text"], fb[p["id"]]))
    text = (data or {}).get("text")
    return text.strip() if isinstance(text, str) and text.strip() else None


def arm_texts(client, texts: dict, pid: str, ed: str, fb: dict) -> dict:
    p = {"id": pid, "text": texts[pid]}
    return {"A": texts[pid], "B": edit_of(client, p, ed, "B", fb), "C": edit_of(client, p, ed, "C", fb)}


def verdict(client, texts: dict, call: dict, fb: dict) -> str | None:
    t = arm_texts(client, texts, call["id"], call["editor"], fb)
    a, b = (t[s] for s in shown(call))
    if a is None or b is None:
        return None
    return chosen_arm(call, parse_easier(client.get(call["judge"], None, pair_prompt(a, b))))


def fact_of(client, texts: dict, pid: str, ed: str, arm: str, judge: str, fb: dict) -> dict | None:
    e = arm_texts(client, texts, pid, ed, fb)[arm]
    if e is None:
        return None
    data = client.get(judge, None, fact_prompt(texts[pid], e))
    if not data or not all(isinstance(data.get(k), list) for k in ("lost", "added", "changed")):
        return None
    return data


# ---- statistics --------------------------------------------------------------

def outcome(first: str | None, second: str | None, x: str, y: str) -> str | None:
    """One judge's outcome for X against Y from its picks in the two orders: win, loss, tie or split."""
    if first is None or second is None:
        return None
    if first == second == x:
        return "win"
    if first == second == y:
        return "loss"
    if {first, second} == {x, y}:
        return "split"
    return "tie"


SCORE = {"win": 1.0, "loss": 0.0, "tie": 0.5, "split": 0.5}


def unit_scores(outcomes: dict) -> dict:
    """{(pid, editor): mean score over judges} from {(pid, editor, judge): outcome}."""
    acc = defaultdict(list)
    for (pid, ed, _j), o in outcomes.items():
        if o is not None:
            acc[(pid, ed)].append(SCORE[o])
    return {k: sum(v) / len(v) for k, v in acc.items()}


def cluster_boot(values: dict, n: int = BOOT, seed: int = 0) -> tuple[float, float, float] | None:
    """Mean of {(pid, ...): value} and a 95% percentile interval, resampling paragraphs."""
    import numpy as np
    if not values:
        return None
    by = defaultdict(list)
    for k, v in values.items():
        by[k[0]].append(v)
    pids = sorted(by)
    sums = np.array([sum(by[p]) for p in pids])
    counts = np.array([len(by[p]) for p in pids])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pids), size=(n, len(pids)))
    means = sums[idx].sum(1) / counts[idx].sum(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(sums.sum() / counts.sum()), float(lo), float(hi)


def label(est: tuple[float, float, float] | None, smallest: float = SMALLEST) -> str:
    if est is None:
        return "not run"
    m, lo, hi = est
    if lo > 0.5 and m >= smallest:
        return "better"
    if hi < smallest:
        return "no meaningful advantage"
    return "inconclusive"


def changes_content(checks: list[dict | None]) -> bool:
    return sum(bool(c and (c["lost"] or c["changed"])) for c in checks) >= 2


def claims(bc, ba, ca, diff_bc, share_b, share_c) -> dict:
    """The four claims of the prereg, from the estimates (mean, lo, hi) or None."""
    def under(e, bound):
        return e is not None and e[2] < bound
    return {
        "readcost feedback beats a generic instruction": label(bc) == "better" and under(diff_bc, 0.10),
        "readcost adds nothing over a generic instruction": label(bc) == "no meaningful advantage",
        "an edit with readcost feedback beats the original": label(ba) == "better" and under(share_b, 0.10),
        "an edit with a generic instruction beats the original": label(ca) == "better" and under(share_c, 0.10),
    }


def collect(ref: Path, client: Client, analyzer, editors=EDITORS, judges=JUDGES) -> dict:
    paras = [json.loads(x) for x in (ref / "texts.jsonl").read_text().splitlines()]
    texts = {p["id"]: p["text"] for p in paras}
    fb = {p["id"]: feedback(analyzer, p["text"]) for p in paras}
    edits = {(p["id"], ed): arm_texts(client, texts, p["id"], ed, fb) for p in paras for ed in editors}
    picks = {}
    for (pid, ed) in edits:
        for x, y in PAIRS:
            for j in judges:
                for o in (0, 1):
                    c = {"id": pid, "editor": ed, "pair": x + y, "judge": j, "order": o}
                    picks[(pid, ed, x + y, j, o)] = verdict(client, texts, c, fb)
    facts = {(pid, ed, arm, j): fact_of(client, texts, pid, ed, arm, j, fb)
             for (pid, ed) in edits for arm in ("B", "C") for j in judges}
    return {"paras": paras, "edits": edits, "picks": picks, "facts": facts}


def analyse(data: dict, analyzer, editors=EDITORS, judges=JUDGES) -> dict:
    edits, picks, facts = data["edits"], data["picks"], data["facts"]
    res: dict = {"pairs": {}, "per_editor": {}, "per_judge": {}}
    outcomes_by_pair = {}
    for x, y in PAIRS:
        oc = {(pid, ed, j): outcome(picks[(pid, ed, x + y, j, 0)], picks[(pid, ed, x + y, j, 1)], x, y)
              for (pid, ed) in edits for j in judges}
        outcomes_by_pair[x + y] = oc
        est = cluster_boot(unit_scores(oc))
        res["pairs"][x + y] = {"estimate": est, "label": label(est),
                               "counts": dict(Counter(o for o in oc.values() if o)),
                               "missing": sum(o is None for o in oc.values())}
        for ed in editors:
            sub = {k: v for k, v in oc.items() if k[1] == ed}
            res["per_editor"].setdefault(ed, {})[x + y] = {"estimate": cluster_boot(unit_scores(sub)),
                                                          "counts": dict(Counter(o for o in sub.values() if o))}
        for j in judges:
            sub = {k: v for k, v in oc.items() if k[2] == j}
            res["per_judge"].setdefault(j, {})[x + y] = {"estimate": cluster_boot(unit_scores(sub)),
                                                        "counts": dict(Counter(o for o in sub.values() if o))}
    # Agreement between judges: same outcome (split counted as tie) on a unit.
    agree = {}
    for a in range(len(judges)):
        for b in range(a + 1, len(judges)):
            same = tot = 0
            for oc in outcomes_by_pair.values():
                for (pid, ed) in edits:
                    oa, ob = oc[(pid, ed, judges[a])], oc[(pid, ed, judges[b])]
                    if oa and ob:
                        tot += 1
                        same += (oa if oa != "split" else "tie") == (ob if ob != "split" else "tie")
            agree[f"{judges[a]} / {judges[b]}"] = round(same / tot, 3) if tot else None
    res["judge_agreement"] = agree
    # Content.
    change = {arm: {} for arm in ("B", "C")}
    counts = {arm: Counter() for arm in ("B", "C")}
    n_checked = Counter()
    for (pid, ed), t in edits.items():
        for arm in ("B", "C"):
            if t[arm] is None:
                continue
            checks = [facts[(pid, ed, arm, j)] for j in judges]
            got = [c for c in checks if c]
            if not got:
                continue
            change[arm][(pid, ed)] = float(changes_content(checks))
            n_checked[arm] += 1
            for c in got:
                for k in ("lost", "added", "changed"):
                    counts[arm][k] += len(c[k]) / len(got)
    res["content"] = {arm: {"share_changing": cluster_boot(change[arm]), "edits_checked": n_checked[arm],
                            **{f"mean_{k}": round(counts[arm][k] / n_checked[arm], 3) if n_checked[arm] else None
                               for k in ("lost", "added", "changed")}} for arm in ("B", "C")}
    both = {k: change["B"][k] - change["C"][k] for k in change["B"] if k in change["C"]}
    res["content"]["B_minus_C"] = cluster_boot(both) if both else None
    # Length and findings.
    import statistics
    length, finds = {}, {}
    for arm in ("A", "B", "C"):
        for ed in editors:
            rows = [(t["A"], t[arm]) for (pid, e), t in edits.items() if e == ed and t[arm] is not None]
            if not rows:
                continue
            ratios = [len(b.split()) / len(a.split()) for a, b in rows]
            over = sum(len(b.split()) > budget(a) for a, b in rows)
            name = "A" if arm == "A" else f"{arm} {ed}"
            length[name] = {"n": len(rows), "median_ratio": round(statistics.median(ratios), 3),
                                     "over_budget": over}
            nf = [len(analyzer.check_text(b, "markdown", "p.md").findings) for _a, b in rows]
            finds[name] = {"median": statistics.median(nf), "mean": round(statistics.mean(nf), 2),
                                    "none": round(sum(f == 0 for f in nf) / len(nf), 3)}
            if arm == "A":
                break  # A is the same for every editor
    res["length"], res["findings"] = length, finds
    res["missing_edits"] = sum(t[a] is None for t in edits.values() for a in ("B", "C"))
    res["claims"] = claims(res["pairs"]["BC"]["estimate"], res["pairs"]["BA"]["estimate"],
                           res["pairs"]["CA"]["estimate"], res["content"]["B_minus_C"],
                           res["content"]["B"]["share_changing"], res["content"]["C"]["share_changing"])
    return res


def fmt(est) -> str:
    if est is None:
        return "not run"
    return f"{est[0]:.3f} [{est[1]:.3f}, {est[2]:.3f}]"


def render(res: dict, status: dict, client: Client) -> str:
    lines = ["## Edit arms: readcost feedback (B) against a generic instruction (C) and the original (A)", "",
             f"Calls {client.calls} (new this run {client.new_calls}, served from cache {client.cached_hits}), "
             f"cost ${client.spent:.2f} of ${COST_CAP:.0f}. Phases: "
             + ", ".join(f"{k} {'done' if v else 'stopped'}" for k, v in status.items()), ""]
    if not status.get("BC", False):
        lines += ["B against C is not complete, so no claim is decided.", ""]
    lines += ["| Pair | Win rate of first [95%] | Label | Win | Tie | Split | Loss | Missing |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for pair, r in res["pairs"].items():
        c = r["counts"]
        lines.append(f"| {pair[0]} against {pair[1]} | {fmt(r['estimate'])} | {r['label']} | {c.get('win', 0)} | "
                     f"{c.get('tie', 0)} | {c.get('split', 0)} | {c.get('loss', 0)} | {r['missing']} |")
    lines += ["", "| Claim | Holds |", "| --- | --- |"]
    lines += [f"| {k} | {'yes' if v and status.get('BC') else 'no'} |" for k, v in res["claims"].items()]
    co = res["content"]
    lines += ["", "Content (an edit changes content when 2 of 3 judges list a lost or changed fact):", "",
              "| Arm | Edits checked | Share changing content [95%] | Lost | Added | Changed |",
              "| --- | --- | --- | --- | --- | --- |"]
    for arm in ("B", "C"):
        lines.append(f"| {arm} | {co[arm]['edits_checked']} | {fmt(co[arm]['share_changing'])} | "
                     f"{co[arm]['mean_lost']} | {co[arm]['mean_added']} | {co[arm]['mean_changed']} |")
    lines += ["", f"B minus C, share changing content: {fmt(co['B_minus_C'])}. Missing edits: {res['missing_edits']}.",
              "", "| Version | n | Words over original, median | Over budget | Findings, median | mean | none |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for k, v in res["length"].items():
        f = res["findings"][k]
        lines.append(f"| {k} | {v['n']} | {v['median_ratio']} | {v['over_budget']} | {f['median']} | {f['mean']} | "
                     f"{f['none']} |")
    lines += ["", ("B was told to address readcost's findings, so fewer findings after B is not evidence "
                   "that B reads better."), "", "Per editor and per judge (decide nothing):", "",
              "| Who | B against C | B against A | C against A |", "| --- | --- | --- | --- |"]
    for kind in ("per_editor", "per_judge"):
        for who, r in res[kind].items():
            lines.append(f"| {who} | " + " | ".join(fmt(r[p]["estimate"]) for p in ("BC", "BA", "CA")) + " |")
    lines += ["", "Judge agreement (same outcome on a unit): "
              + "; ".join(f"{k} {v}" for k, v in res["judge_agreement"].items()), "",
              "Models served: " + "; ".join(f"{m}: {dict(c)}" for m, c in sorted(client.served.items()))]
    return "\n".join(lines) + "\n"


def draw_counts(pointers: Path | None, ref: Path) -> str:
    """One line of counts from the committed draw and the fetch."""
    parts = []
    if pointers and (pointers / "candidates.jsonl").exists():
        parts.append(f"candidates {len((pointers / 'candidates.jsonl').read_text().splitlines())}")
    if pointers and (pointers / "walk.jsonl").exists():
        walked = [json.loads(x)["outcome"] for x in (pointers / "walk.jsonl").read_text().splitlines()]
        parts.append(f"walked {len(walked)} ({', '.join(f'{k}: {v}' for k, v in sorted(Counter(walked).items()))})")
    if (ref / "texts.jsonl").exists():
        parts.append(f"paragraphs fetched {len((ref / 'texts.jsonl').read_text().splitlines())}")
    if (ref / "missing.json").exists():
        parts.append(f"missing at run time {len(json.loads((ref / 'missing.json').read_text()))}")
    return "Draw: " + "; ".join(parts) + ".\n" if parts else ""


def report(ref: Path, json_out: Path | None, client: Client | None = None, analyzer=None,
           pointers: Path | None = None, editors=EDITORS, judges=JUDGES) -> str:
    from readcost import Analyzer, Config
    analyzer = analyzer or Analyzer(Config())
    client = client or Client(ref / "replies.jsonl", ask=lambda *a, **k: (None, {}))
    status = json.loads((ref / "status.json").read_text())["phases"] if (ref / "status.json").exists() else {}
    res = analyse(collect(ref, client, analyzer, editors, judges), analyzer, editors, judges)
    text = render(res, status, client) + "\n" + draw_counts(pointers, ref)
    if json_out:
        json_out.write_text(json.dumps({"status": status, **res}, indent=1, default=str))
    return text


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("candidates").add_argument("out", type=Path)
    sub.add_parser("draw").add_argument("out", type=Path)
    sub.add_parser("verify")
    f = sub.add_parser("fetch"); f.add_argument("pointers", type=Path); f.add_argument("ref", type=Path)
    r = sub.add_parser("run"); r.add_argument("ref", type=Path); r.add_argument("--workers", type=int, default=8)
    p = sub.add_parser("report"); p.add_argument("ref", type=Path); p.add_argument("--json", type=Path)
    p.add_argument("--pointers", type=Path, help="eval/edit-arms, for the draw's counts")
    a = ap.parse_args(argv)
    if a.cmd == "candidates":
        candidates(a.out)
    elif a.cmd == "draw":
        draw(a.out)
    elif a.cmd == "verify":
        return verify()
    elif a.cmd == "fetch":
        fetch(a.pointers, a.ref)
    elif a.cmd == "run":
        from readcost import Analyzer, Config
        run(a.ref, Client(a.ref / "replies.jsonl"), Analyzer(Config()), workers=a.workers)
    else:
        print(report(a.ref, a.json, pointers=a.pointers), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
