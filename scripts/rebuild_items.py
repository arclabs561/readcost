"""Rebuild the items raters labelled in the three held-out precision rounds.

    python scripts/rebuild_items.py --round all              # ref/rebuild/items/round{1,2,3}.jsonl.gz
    python scripts/rebuild_items.py --round 2 --verify DIR   # and compare with DIR/round2.jsonl.gz

The committed pointers (eval/heldout/sample.jsonl for round 1,
eval/breadth/sample.jsonl for round 2, eval/kinds/sample.jsonl for round 3)
hold, per item, a repository, a commit, a path, a blob hash and offsets.
This script fetches each source at its pinned commit, checks its hash, runs
readcost at the commit the round's plan froze, and writes each item as the
raters saw it: rule, message, excerpt, sentence and the context on each
side.

Needs git, uv and network access to GitHub (the sources, readcost and the
spaCy model) and to the Python package index (readcost's dependencies, as
each frozen uv.lock pins them). Nothing from this checkout is installed:
each round's readcost is a checkout of that commit under ref/rebuild/,
synced with `uv sync --locked`, and the extraction runs in it.

How each kind of source is fetched, as the draws fetched it:

- files: a blobless clone of the pinned commit (`git fetch --depth 1
  --filter=blob:none`), the path checked against the blob hash, then the
  blob itself; its Git SHA-1 is checked again on the bytes.
- commit messages (round 2, `commit/SHA`): the commit, read with `git log`'s
  `%B`, trailing newlines cut to one.
- pull request bodies (round 2, `pr/NUMBER`): GitHub's issue search
  (`repo:R is:pr`, created 1 to 19 November 2026), CRLF turned into LF,
  checked against the SHA-256 in the pointer. GITHUB_TOKEN, when set, raises
  the search's rate limit; without it the script waits 6.5 s between calls.
  The REST endpoint for the one issue is tried when search does not find it.

A source that cannot be fetched, or whose bytes no longer hash to the
pointer's value (a deleted repository, a force-pushed history, an edited
pull request), makes its items unrecoverable: they go to
round{N}.missing.jsonl with the reason, and nothing takes their place.

Fetched text stays under ref/rebuild/ (it belongs to the repositories'
authors); so do the outputs.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import breadth_precision as bp
import heldout_precision as hp
import kinds_precision as kp

READCOST_URL = "https://github.com/arclabs561/readcost.git"
PYTHON = "3.13"  # the draws ran on CPython 3.13
ROUNDS = {
    1: {"sample": "eval/heldout/sample.jsonl", "readcost": "a57e19e0541fb8b17611738507a107a5e3558080"},
    2: {"sample": "eval/breadth/sample.jsonl", "readcost": "fa4a42ccc83d4135cca04bc74c7879cbefccb261"},
    3: {"sample": "eval/kinds/sample.jsonl", "readcost": "663e0cc16d86f5fdf0e019eb27d147708e51538b"},
}
FIELDS = ("i", "kind", "rule", "message", "primed_excerpt", "blind_excerpt", "sentence", "before", "after",
          "in_primed", "in_blind")
PR_WINDOW = "created:2026-11-01..2026-11-19"
PR_PAGES = 10
UA = "readcost-rebuild (https://github.com/arclabs561/readcost)"


# --- pure helpers (tested in tests/test_rebuild_items.py) ---

def git_blob_sha1(data: bytes) -> str:
    """The object id Git gives a blob with these bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def body_sha256(body: str) -> str:
    """The hash round 2 stored for a pull request body: CRLF as LF, UTF-8."""
    return hashlib.sha256(body.replace("\r\n", "\n").encode()).hexdigest()


def why_not_fetched(err: str) -> str:
    """A short reason from git's error: GitHub asks for credentials when a repository is gone or private."""
    if "could not read Username" in err or "Repository not found" in err:
        return "repository gone (deleted or private)"
    if "not our ref" in err or "unadvertised object" in err:
        return "commit no longer on GitHub (history rewritten)"
    return err.strip()[:200]


def read_pointers(path: Path) -> list[dict]:
    """The pointer rows, one per item id: a repeated id keeps its first row."""
    out, seen = [], set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["i"] in seen:
            continue
        seen.add(row["i"])
        out.append(row)
    return out


def source_kind(row: dict) -> str:
    """"commit", "pr" or "blob": how the item's text is fetched."""
    p = row["path"]
    if row.get("stratum") == "commit" and p.startswith("commit/"):
        return "commit"
    if row.get("stratum") == "pr" and p.startswith("pr/"):
        return "pr"
    return "blob"


def local_path(row: dict) -> str:
    """Where the fetched text is stored, relative to ref/rebuild/files/."""
    kind, repo, p = source_kind(row), row["repo"], row["path"]
    if kind == "commit":
        return f"{repo}/commits/{p.split('/', 1)[1]}.gitmessage"
    if kind == "pr":
        return f"{repo}/prs/{p.split('/', 1)[1]}.md"
    return f"{repo}/blobs/{row['blob']}"


def item_type(rnd: int, row: dict) -> str:
    """finding, near, decoy or ranked."""
    if rnd == 1:
        return "decoy" if row["decoy"] else "finding"
    return row["item"]


def tasks_for(rnd: int, rows: list[dict]) -> list[dict]:
    """One task per text readcost checks: stratum, repository, commit and path, with its items."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r.get("stratum", ""), r["repo"], r["commit"], r["path"])].append(r)
    return [{"round": rnd, "stratum": s, "repo": repo, "commit": c, "path": p, "blob": items[0]["blob"],
             "local": local_path(items[0]), "items": items}
            for (s, repo, c, p), items in sorted(groups.items())]


def decoy_words(tokens: list, start: int, end: int) -> list[str] | None:
    """Words of the run of tokens from the one that starts at start to the one that ends at end."""
    a = next((k for k, t in enumerate(tokens) if t[3] == start), None)
    b = next((k for k, t in enumerate(tokens) if t[4] == end), None)
    if a is None or b is None or b < a:
        return None
    return [t[0] for t in tokens[a:b + 1]]


def item_row(rnd: int, ptr: dict, got: dict) -> dict:
    """The item in the schema of the label store, from its pointer and the regenerated fields."""
    typ = item_type(rnd, ptr)
    primed = rnd < 3 or typ in kp.PRIMED_ITEMS
    return {"i": ptr["i"], "kind": ptr.get("kind") if rnd > 1 else None,
            "rule": got["rule"] if primed else None, "message": got["message"] if primed else None,
            "primed_excerpt": got["excerpt"] if primed else None, "blind_excerpt": got["excerpt"],
            "sentence": got["sentence"], "before": got["before"], "after": got["after"],
            "in_primed": primed, "in_blind": True}


def compare(ours: list[dict], theirs: list[dict], fields=FIELDS) -> dict:
    """Field-by-field comparison by item id: counts, and the differing ids per field."""
    a, b = {x["i"]: x for x in ours}, {x["i"]: x for x in theirs}
    diff: dict[str, list] = defaultdict(list)
    exact = 0
    for i in sorted(set(a) & set(b)):
        bad = [f for f in fields if a[i].get(f) != b[i].get(f)]
        for f in bad:
            diff[f].append(i)
        exact += not bad
    return {"reference": len(b), "rebuilt": len(a), "exact": exact,
            "missing": sorted(set(b) - set(a)), "extra": sorted(set(a) - set(b)),
            "fields": {f: v for f, v in sorted(diff.items())}}


def write_gz(path: Path, rows: list[dict]) -> None:
    """JSON lines, gzip with no timestamp, so the same rows give the same bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(data)


def read_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt") as fh:
        return [json.loads(x) for x in fh if x.strip()]


# --- fetching ---

def git(args: list[str], cwd: Path | None = None, binary: bool = False, timeout: int = 600):
    return hp.git(args, cwd=cwd, binary=binary, timeout=timeout)


def _repo_dir(ref: Path, repo: str) -> Path:
    d = ref / "git" / (repo.replace("/", "__") + ".git")
    if not (d / "HEAD").exists():
        d.mkdir(parents=True, exist_ok=True)
        git(["init", "-q", "--bare"], cwd=d)
        git(["remote", "add", "origin", f"https://github.com/{repo}.git"], cwd=d)
    return d


def _fetch_commits(d: Path, shas: list[str]) -> dict[str, str]:
    """Fetch each commit with its trees (no blobs); the error per commit that could not be fetched."""
    errors = {}
    have = lambda s: subprocess.run(["git", "cat-file", "-e", f"{s}^{{commit}}"], cwd=d,
                                    capture_output=True, check=False).returncode == 0
    todo = [s for s in shas if not have(s)]
    if not todo:
        return errors
    try:
        git(["fetch", "-q", "--no-tags", "--no-write-fetch-head", "--filter=blob:none", "--depth", "1", "origin",
             *todo], cwd=d)
    except (RuntimeError, subprocess.TimeoutExpired):
        for s in todo:  # one bad SHA fails the batch: try each alone
            try:
                git(["fetch", "-q", "--no-tags", "--no-write-fetch-head", "--filter=blob:none", "--depth", "1",
                     "origin", s], cwd=d)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                errors[s] = why_not_fetched(str(exc))
    return errors


def fetch_repo(ref: Path, repo: str, rows: list[dict]) -> dict[int, str]:
    """Store every blob and commit message these items need; the reason per item id that failed."""
    files = ref / "files"
    bad: dict[int, str] = {}
    need = [r for r in rows if source_kind(r) in ("blob", "commit") and not (files / local_path(r)).exists()]
    if not need:
        return bad
    try:
        d = _repo_dir(ref, repo)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return {r["i"]: f"git init: {exc}" for r in need}
    shas = sorted({r["commit"] if source_kind(r) == "blob" else r["blob"] for r in need})
    errors = _fetch_commits(d, shas)
    blobs = {}
    for r in need:
        kind = source_kind(r)
        sha = r["commit"] if kind == "blob" else r["blob"]
        if sha in errors:
            bad[r["i"]] = f"{errors[sha]}: commit {sha}"
            continue
        if kind == "commit":
            out = git(["log", "-1", "--format=%H%x00%an%x00%ae%x00%aI%x00%B%x1e", sha], cwd=d)
            msg = bp.parse_log(out)[0]["message"]
            dest = files / local_path(r)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(msg.encode())
            continue
        try:
            oid = git(["rev-parse", f"{r['commit']}:{r['path']}"], cwd=d).strip()
        except RuntimeError as exc:
            bad[r["i"]] = f"path not in commit: {exc}"
            continue
        if oid != r["blob"]:
            bad[r["i"]] = f"path at commit is blob {oid}, pointer says {r['blob']}"
            continue
        blobs.setdefault(r["blob"], []).append(r)
    oids = sorted(blobs)
    for k in range(0, len(oids), 200):
        try:
            git(["-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags",
                 "--no-write-fetch-head", "--filter=blob:none", *oids[k:k + 200]], cwd=d)
        except (RuntimeError, subprocess.TimeoutExpired):
            pass  # cat-file below fetches what is still missing one by one, and records failures
    for oid, rs in blobs.items():
        try:
            data = git(["cat-file", "blob", oid], cwd=d, binary=True)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            bad |= {r["i"]: f"blob not fetched: {exc}" for r in rs}
            continue
        if git_blob_sha1(data) != oid:
            bad |= {r["i"]: "blob bytes do not hash to the pointer" for r in rs}
            continue
        dest = files / local_path(rs[0])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return bad


class Search:
    """GitHub's REST search, spaced to stay under its rate limit."""

    def __init__(self, token: str | None = None):
        self.token = token
        self.gap = 2.1 if token else 6.5
        self.last = 0.0

    def get(self, url: str, spaced: bool = True) -> dict:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": UA}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(4):
            if spaced:
                wait = self.gap - (time.time() - self.last)
                if wait > 0:
                    time.sleep(wait)
                self.last = time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 410, 422, 451):
                    raise FileNotFoundError(f"HTTP {exc.code}") from exc
                if exc.code in (403, 429) and attempt < 3:
                    time.sleep(30 * (attempt + 1))
                    continue
                raise RuntimeError(f"HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < 3:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise RuntimeError(str(exc)) from exc
        raise RuntimeError("retries exhausted")


def fetch_prs(ref: Path, repo: str, rows: list[dict], search: Search) -> dict[int, str]:
    """Store the pull request bodies these items need; the reason per item id that failed."""
    files = ref / "files"
    need = {int(r["path"].split("/", 1)[1]): r for r in rows if not (files / local_path(r)).exists()}
    if not need:
        return {}
    bodies: dict[int, str] = {}
    q = f"repo:{repo} is:pr {PR_WINDOW}"
    try:
        for page in range(1, PR_PAGES + 1):
            res = search.get("https://api.github.com/search/issues?" + urllib.parse.urlencode(
                {"q": q, "sort": "created", "order": "desc", "per_page": 100, "page": page}))
            for it in res["items"]:
                if it["number"] in need:
                    bodies[it["number"]] = it.get("body") or ""
            if len(res["items"]) < 100 or set(need) <= set(bodies):
                break
    except (RuntimeError, FileNotFoundError):
        pass
    for num in sorted(set(need) - set(bodies)):  # not found by search: the issue itself
        try:
            it = search.get(f"https://api.github.com/repos/{repo}/issues/{num}", spaced=False)
            bodies[num] = it.get("body") or ""
        except (RuntimeError, FileNotFoundError):
            pass
    bad = {}
    for num, r in need.items():
        if num not in bodies:
            bad[r["i"]] = "pull request not found"
            continue
        body = bodies[num].replace("\r\n", "\n")
        if body_sha256(body) != r["blob"]:
            bad[r["i"]] = "pull request body changed since the draw"
            continue
        dest = files / local_path(r)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body.encode())
    return bad


def fetch_round(ref: Path, rows: list[dict], workers: int, search: Search) -> dict[int, str]:
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_repo[r["repo"]].append(r)
    bad: dict[int, str] = {}
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        for n, got in enumerate(ex.map(lambda kv: fetch_repo(ref, *kv), sorted(by_repo.items())), 1):
            bad |= got
            if n % 50 == 0:
                print(f"  fetched {n}/{len(by_repo)} repositories in {time.time() - t0:.0f}s", flush=True)
    for repo, rs in sorted(by_repo.items()):
        prs = [r for r in rs if source_kind(r) == "pr"]
        if prs:
            bad |= fetch_prs(ref, repo, prs, search)
    return bad


# --- readcost at the frozen commit ---

def ensure_readcost(ref: Path, commit: str) -> Path:
    """A checkout of readcost at commit, synced from its uv.lock, with the spaCy model in place."""
    d = ref / "readcost" / commit[:12]
    if (d / ".rebuild-ready").exists():
        return d
    d.mkdir(parents=True, exist_ok=True)
    if not (d / ".git").exists():
        git(["init", "-q"], cwd=d)
        git(["remote", "add", "origin", READCOST_URL], cwd=d)
    git(["fetch", "-q", "--depth", "1", "origin", commit], cwd=d)
    git(["checkout", "-q", "--force", commit], cwd=d)
    env = os.environ | {"UV_PROJECT_ENVIRONMENT": str(d / ".venv")}
    subprocess.run(["uv", "sync", "--locked", "--no-dev", "--python", PYTHON, "--project", str(d)],
                   check=True, env=env)
    subprocess.run(["uv", "run", "--no-sync", "--project", str(d), "readcost", "setup"], check=True, env=env)
    (d / ".rebuild-ready").write_text(commit + "\n")
    return d


# --- extraction (runs inside the frozen readcost) ---

_AN: dict = {}


def _analyzer(rnd: int, stratum: str):
    key = (rnd, "all" if rnd == 3 and stratum == "code-ordinary" else "doc")
    if key not in _AN:
        _AN[key] = hp.analyzer() if rnd == 1 else bp.analyzer() if rnd == 2 else kp.analyzer(key[1])
    return _AN[key]


def rebuild_task(task: dict) -> list[dict]:
    """Regenerate every item of one text, as the round's draw made it."""
    from readcost.engine import read_source
    from readcost.extract import extract
    from readcost.features import Context, show

    rnd, stratum, path = task["round"], task["stratum"], task["path"]
    local = Path(task["files"]) / task["local"]
    if rnd == 3 and stratum == "changelog":  # round 3 stored changelogs cut at 100 KB
        data, cut = kp.truncate_changelog(local.read_bytes())
        if cut:
            local = local.with_name(local.name + ".cut")
            local.write_bytes(data)
    text, _ = read_source(str(local))
    an = _analyzer(rnd, stratum)
    cpath = bp.check_path(stratum, path) if rnd == 2 else path
    kw = {} if rnd == 1 else {"lines": bp.ALL_LINES}
    items = task["items"]
    types = {it["i"]: item_type(rnd, it) for it in items}
    nlp = an.nlp
    cache = hp._CachingNLP(nlp) if rnd == 1 else bp.ParseCache(nlp)
    an._nlp = cache
    runs: dict[str, list] = {}
    sents: dict[tuple, tuple] = {}
    try:
        runs[""] = an.check_text(text, None, cpath, **kw).findings
        for rule in bp.LOOSE if rnd > 1 else ():
            if any(types[it["i"]] == "near" and it["rule"] == rule for it in items):
                with bp.loosened(rule):
                    runs[rule] = an.check_text(text, None, cpath, **kw).findings
        want = {(it["sentence_start"], it["sentence_end"]) for it in items if types[it["i"]] in ("decoy", "ranked")}
        if want:
            ctx = Context(an.cfg, an.profile, an.allow, set())
            for seg in extract(text, cpath, None, comments=an.cfg.comments):
                doc = cache(seg.text)
                ctx.codes = seg.codes
                for sent in doc.sents:
                    whole = seg.span(sent.start_char, sent.end_char)
                    if whole in want and whole not in sents:
                        toks = [[t.text, t.pos_, t.is_alpha, *(seg.span(t.idx, t.idx + len(t.text)) or (None, None))]
                                for t in sent]
                        sents[whole] = (show(ctx, doc, sent.start, sent.end - 1), toks)
    finally:
        an._nlp = nlp
    out = []
    for it in items:
        typ = types[it["i"]]
        ss, se = it["sentence_start"], it["sentence_end"]
        got: dict = {"i": it["i"]}
        if typ in ("finding", "near"):
            pool = runs[it["rule"] if typ == "near" else ""]
            f = next((f for f in pool if f.feature == it["rule"] and (f.start, f.end, f.sentence_start,
                                                                       f.sentence_end) == (it["start"], it["end"], ss, se)),
                     None)
            if f is None:
                out.append(got | {"error": f"readcost gave no {typ} at these offsets"})
                continue
            got |= {"rule": it["rule"], "message": f.message, "excerpt": f.excerpt, "sentence": f.sentence}
        else:
            if (ss, se) not in sents:
                out.append(got | {"error": "no sentence at these offsets"})
                continue
            sentence, toks = sents[(ss, se)]
            if typ == "ranked":
                got |= {"rule": None, "message": None, "excerpt": sentence, "sentence": sentence}
            else:
                if rnd == 2:  # rounds 2 and 3 took a decoy's tokens from a second parse
                    toks = bp.sentence_tokens(an, text, {"stratum": stratum, "path": path}, ss, se)
                elif rnd == 3:
                    toks = kp.sentence_tokens(an, text, path, ss, se)
                words = decoy_words(toks or [], it["start"], it["end"])
                if words is None:
                    out.append(got | {"error": "decoy span is not a run of tokens"})
                    continue
                got |= {"rule": it["rule"], "message": hp.decoy_message(it["rule"], words),
                        "excerpt": text[it["start"]:it["end"]], "sentence": sentence}
        got["before"], got["after"] = hp.context(text, ss, se)
        out.append(got)
    return out


def _safe_task(task: dict) -> list[dict]:
    try:
        return rebuild_task(task)
    except Exception as exc:  # noqa: BLE001 -- recorded per item, the other texts go on
        return [{"i": it["i"], "error": f"check error: {exc!r}"[:300]} for it in task["items"]]


def cmd_extract(args) -> None:
    tasks = json.loads(Path(args.tasks).read_text())
    rows = []
    t0 = time.time()
    with ProcessPoolExecutor(args.workers) as ex:
        for n, got in enumerate(ex.map(_safe_task, tasks, chunksize=1), 1):
            rows += got
            if n % 50 == 0:
                print(f"  checked {n}/{len(tasks)} texts in {time.time() - t0:.0f}s", flush=True)
    Path(args.results).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


# --- the rounds ---

def build_round(rnd: int, args) -> dict:
    ref: Path = args.ref
    t0 = time.time()
    ptrs = read_pointers(ROOT / ROUNDS[rnd]["sample"])
    print(f"round {rnd}: {len(ptrs)} items", flush=True)
    bad = fetch_round(ref, ptrs, args.fetch_workers, Search(os.environ.get("GITHUB_TOKEN") or None))
    ok = [r for r in ptrs if r["i"] not in bad]
    env_dir = ensure_readcost(ref, ROUNDS[rnd]["readcost"])
    tasks = tasks_for(rnd, ok)
    for t in tasks:
        t["files"] = str((ref / "files").resolve())
    work = ref / "work"
    work.mkdir(parents=True, exist_ok=True)
    tasks_path, results_path = work / f"tasks-round{rnd}.json", work / f"results-round{rnd}.jsonl"
    tasks_path.write_text(json.dumps(tasks))
    env = os.environ | {"UV_PROJECT_ENVIRONMENT": str(env_dir / ".venv")}
    subprocess.run(["uv", "run", "--no-sync", "--project", str(env_dir), "python", str(Path(__file__).resolve()),
                    "_extract", "--tasks", str(tasks_path), "--results", str(results_path),
                    "--workers", str(args.workers)], check=True, env=env)
    got = {r["i"]: r for r in map(json.loads, results_path.read_text().splitlines())}
    items, missing = [], []
    for p in ptrs:
        if p["i"] in bad:
            missing.append({"i": p["i"], "repo": p["repo"], "path": p["path"], "reason": bad[p["i"]]})
        elif "error" in got[p["i"]]:
            missing.append({"i": p["i"], "repo": p["repo"], "path": p["path"], "reason": got[p["i"]]["error"]})
        else:
            items.append(item_row(rnd, p, got[p["i"]]))
    items.sort(key=lambda x: x["i"])
    write_gz(args.out / f"round{rnd}.jsonl.gz", items)
    (args.out / f"round{rnd}.missing.jsonl").write_text("".join(json.dumps(m) + "\n" for m in missing))
    summary = {"round": rnd, "items": len(ptrs), "rebuilt": len(items), "unrecoverable": len(missing),
               "reasons": dict(Counter(m["reason"].split(":")[0] for m in missing)),
               "seconds": round(time.time() - t0)}
    print(json.dumps(summary), flush=True)
    return summary


def verify_round(rnd: int, args) -> dict:
    ours = read_gz(args.out / f"round{rnd}.jsonl.gz")
    theirs = read_gz(Path(args.verify) / f"round{rnd}.jsonl.gz")
    res = compare(ours, theirs)
    (args.out / f"verify-round{rnd}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(f"round {rnd}: {res['exact']} of {res['reference']} items match exactly; "
          f"{len(res['missing'])} not rebuilt; differing fields "
          + json.dumps({f: len(v) for f, v in res["fields"].items()}), flush=True)
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["_extract"]:  # the inner step, run by build_round inside the frozen readcost
        ap.add_argument("step")
        ap.add_argument("--tasks", required=True)
        ap.add_argument("--results", required=True)
        ap.add_argument("--workers", type=int, default=2)
        cmd_extract(ap.parse_args(argv))
        return
    ap.add_argument("--round", default="all", choices=["1", "2", "3", "all"])
    ap.add_argument("--ref", type=Path, default=ROOT / "ref/rebuild", help="fetched text, clones, readcost checkouts")
    ap.add_argument("--out", type=Path, default=None, help="where round{N}.jsonl.gz go (default REF/items)")
    ap.add_argument("--verify", metavar="DIR", help="compare with DIR/round{N}.jsonl.gz, field by field")
    ap.add_argument("--no-build", action="store_true", help="with --verify: compare the outputs already in --out")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2, help="processes running readcost")
    ap.add_argument("--fetch-workers", type=int, default=6)
    args = ap.parse_args(argv)
    args.ref = args.ref.resolve()
    args.out = (args.out or args.ref / "items").resolve()
    args.ref.mkdir(parents=True, exist_ok=True)
    rounds = [1, 2, 3] if args.round == "all" else [int(args.round)]
    for rnd in rounds:
        if not (args.no_build and args.verify):
            build_round(rnd, args)
        if args.verify:
            verify_round(rnd, args)


if __name__ == "__main__":
    main()
