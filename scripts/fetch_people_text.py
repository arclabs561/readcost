"""Fetch project community text: issues, pull requests, review threads, wikis and forums.

    PYTHONPATH=src python3 scripts/fetch_people_text.py /Volumes/Rebuildable/readcost-ref/broad/people
    PYTHONPATH=src python3 scripts/eval_people_ai.py /Volumes/Rebuildable/readcost-ref/broad

Four parts, each selectable with ``--parts``:

- ``respected``: for each GitHub handle in ``RESPECTED`` (people with a lens
  in the agent configuration), the issues and pull requests they opened
  (``search/issues`` with ``author:HANDLE``), their review comments on pull
  requests they reviewed (``reviewed-by:HANDLE``, then ``pulls/N/comments``)
  and their comments on threads they joined (``commenter:HANDLE``, then
  ``issues/N/comments``), up to ``--per-person`` texts, at most two comments
  from one thread. Category ``people-issue``, ``people-review`` or
  ``people-comment``; source and author ``respected:HANDLE``.
- ``community``: a baseline of ordinary community text. For each of eight
  languages, ``--repos`` random repositories with 200 to 5,000 stars pushed
  since 2025-06 (a random results page, as in scripts/fetch_github_readmes.py);
  from each, up to five issue or pull request bodies, three issue comments and
  two review comments by people who are not bots and not in ``RESPECTED``.
  Same categories; source ``community/LANGUAGE``, author ``community``.
- ``wikis``: ``git clone --depth 1`` of the public wiki of each repository in
  ``WIKIS`` (projects run by the people above); up to ``--wiki-pages``
  Markdown pages with 150 or more words of prose. Category ``people-wiki``,
  source ``wiki/OWNER-REPO``, author ``project-wiki:HANDLE``.
- ``forums``: Discourse JSON from users.rust-lang.org, internals.rust-lang.org
  and discuss.python.org. From ``/latest.json`` (pages 0 to 4), a random
  ``--topics`` topics per forum, from each ``/t/ID.json`` the first post and up
  to three replies; and, per handle in ``FORUM_PEOPLE``, up to 15 of their
  topics and replies from ``/user_actions.json``. robots.txt is read and
  obeyed. Category ``people-forum``; source ``community/HOST`` or
  ``respected:HANDLE``.

Text is cleaned with ``community_prose``: fenced and indented code, quoted
lines (``>``), HTML comments (pull request templates), task-list and table
lines are removed. Bodies need 40 words after cleaning and comments 25. Bot
accounts (GitHub ``type`` Bot, a ``[bot]`` suffix, or ``BOTS``) are skipped.

None of this text carries a reuse licence (GitHub's terms of service, the
forums' terms): it is kept under the output directory for aggregate analysis
only, and each item's ``license`` says so. Every request carries the project's
User-Agent; GitHub searches are 2.1 s apart and forum requests 1.5 s apart.
Writes ``manifest.json`` in the schema of scripts/fetch_eval_corpus.py and
rebuilds ``../ALL-people-ai.jsonl``.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
NO_LICENCE = "none: each author's text under the host's terms; local aggregate analysis only"

# lens name -> GitHub handle, checked with `gh api users/HANDLE` on 2026-10-27.
RESPECTED = {
    "burntsushi": "BurntSushi", "dtolnay": "dtolnay", "matklad": "matklad", "b0rk": "jvns",
    "danluu": "danluu", "karpathy": "karpathy", "gregg": "brendangregg", "lizrice": "lizrice",
    "pike": "robpike", "rsc": "rsc", "simonw": "simonw", "shepmaster": "shepmaster",
    "withoutboats": "withoutboats", "willcrichton": "willcrichton", "fey": "rusty1s",
    "jeremy-howard": "jph00", "demoura": "leodemoura", "olah": "colah", "beauchemin": "mistercrunch",
    "breunig": "dbreunig", "qntm": "qntm", "hamilton": "williamleif", "tao": "teorth",
    "dowling": "jimdowling",
}
# repository -> handle whose project it is
WIKIS = {
    "BurntSushi/ripgrep": "BurntSushi", "rust-lang/regex": "BurntSushi", "BurntSushi/jiff": "BurntSushi",
    "dtolnay/syn": "dtolnay", "serde-rs/serde": "dtolnay", "rust-lang/rust-analyzer": "matklad",
    "tigerbeetle/tigerbeetle": "matklad", "karpathy/nanoGPT": "karpathy", "karpathy/llm.c": "karpathy",
    "brendangregg/FlameGraph": "brendangregg", "brendangregg/perf-tools": "brendangregg",
    "simonw/datasette": "simonw", "simonw/llm": "simonw", "golang/go": "rsc",
    "pyg-team/pytorch_geometric": "rusty1s", "fastai/fastai": "jph00", "leanprover/lean4": "leodemoura",
    "Z3Prover/z3": "leodemoura", "apache/superset": "mistercrunch", "apache/airflow": "mistercrunch",
    "shepmaster/snafu": "shepmaster", "logicalclocks/hopsworks": "jimdowling",
}
FORUMS = ("users.rust-lang.org", "internals.rust-lang.org", "discuss.python.org")
FORUM_PEOPLE = {"users.rust-lang.org": ("matklad", "dtolnay", "BurntSushi", "shepmaster", "withoutboats"),
                "internals.rust-lang.org": ("matklad", "dtolnay", "BurntSushi", "withoutboats"),
                "discuss.python.org": ("simonw", "jph00")}
LANGS = ("Rust", "Go", "Python", "JavaScript", "TypeScript", "Java", "C++", "Ruby")
BOTS = {"dependabot", "renovate", "github-actions", "codecov", "netlify", "vercel", "rust-highfive",
        "rustbot", "bors", "rust-timer", "rfcbot", "coveralls", "sonarcloud", "changeset-bot",
        "pre-commit-ci", "mergify", "allcontributors", "stale", "copilot", "devin-ai-integration",
        "google-labs-jules", "codspeed-hq", "cla-bot", "k8s-ci-robot", "googlebot", "triagebot",
        "rust-log-analyzer", "rust-cloud-vms", "workflows-tigerbeetle", "claude", "coderabbitai",
        "chatgpt-codex-connector", "gemini-code-assist", "sourcery-ai", "cursor"}
MIN_BODY, MIN_COMMENT = 40, 25
SEARCH_GAP, FORUM_GAP = 2.1, 1.5
_last: dict[str, float] = {}


def _pace(key: str, gap: float) -> None:
    wait = _last.get(key, 0.0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[key] = time.monotonic()


def gh(args: list[str]) -> object:
    """``gh api`` with the project's User-Agent; JSON out. Retries once after a minute on an error."""
    for attempt in range(2):
        try:
            out = subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}", "-H", "Accept: application/vnd.github+json",
                                  *args], check=True, capture_output=True, text=True, timeout=120).stdout
            return json.loads(out)
        except subprocess.CalledProcessError as e:
            if attempt or "404" in e.stderr or "422" in e.stderr:
                raise
            print(f"gh failed; retrying in 65 s ({e.stderr.strip()[:120]})", file=sys.stderr)
            time.sleep(65)
    raise AssertionError("unreachable")


def search_issues(q: str, per_page: int = 50, page: int = 1, sort: str | None = None) -> list[dict]:
    _pace("search", SEARCH_GAP)
    args = ["-X", "GET", "search/issues", "-f", f"q={q}", "-f", f"per_page={per_page}", "-f", f"page={page}"]
    if sort:
        args += ["-f", f"sort={sort}"]
    try:
        return gh(args)["items"]
    except subprocess.CalledProcessError as e:
        print(f"search {q!r} failed: {e.stderr.strip()[:120]}", file=sys.stderr)
        return []


def is_bot(user: dict | None) -> bool:
    if not user:
        return True
    login = (user.get("login") or "").lower()
    return user.get("type") == "Bot" or login.endswith("[bot]") or login.removesuffix("[bot]") in BOTS


def community_prose(md: str) -> str:
    """Markdown with the parts a reader skips or did not write removed: code, quotes, templates, tables."""
    md = md.replace("\r\n", "\n")
    md = re.sub(r"(?s)<!--.*?-->", "", md)
    md = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", md)
    md = re.sub(r"(?ms)^\s*(```|~~~).*", "", md)                       # unclosed fence runs to the end
    md = re.sub(r"(?is)<(pre|code|table|details|summary)\b.*?</\1>", "", md)
    keep: list[str] = []
    for line in md.split("\n"):
        s = line.strip()
        if (s.startswith((">", "|")) or line.startswith(("    ", "\t"))
                or re.match(r"^([-*+]\s+)?\[[ xX]\]", s) or re.fullmatch(r"(<[^>]+>\s*)+", s)
                or re.fullmatch(r"\S*https?://\S+", s)):
            continue
        keep.append(line.rstrip())
    text = "\n".join(keep)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))


def html_to_text(s: str) -> str:
    """Discourse ``cooked`` HTML to plain paragraphs, without code, quotes, onebox previews or images."""
    s = re.sub(r"(?is)<(pre|code|aside|blockquote|table|script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?is)<img\b[^>]*>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|li|h\d|div)>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n", s)]
    return "\n\n".join(p for p in paras if p) + "\n"


class Store:
    """Writes each text under ``out`` and collects manifest entries and failures."""

    def __init__(self, out: Path, redo: set[str]):
        self.out = out
        self.now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        old = json.loads((out / "manifest.json").read_text()) if (out / "manifest.json").exists() else {}
        self.entries = [e for e in old.get("entries", []) if e.get("part") not in redo]
        self.failures = [f for f in old.get("failures", []) if f.get("part") not in redo]
        self.seen = {e["id"] for e in self.entries}

    def add(self, part: str, category: str, source: str, key: str, text: str, url: str, via: str,
            fmt: str = "markdown", license: str = NO_LICENCE, author: str = "", **extra) -> bool:
        item_id = f"{category}/{source}/{key}"
        if item_id in self.seen:
            return False
        self.seen.add(item_id)
        ext = {"markdown": "md", "text": "txt"}[fmt]
        rel = f"{category}/{re.sub(r'[^A-Za-z0-9_.-]+', '_', source)}/{re.sub(r'[^A-Za-z0-9_.-]+', '_', key)}.{ext}"
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(text)
        self.entries.append({"id": item_id, "category": category, "source": source, "author": author,
                             "url": url, "path": rel, "format": fmt, "license": license,
                             "fetched_at": self.now, "via": via, "part": part, **extra,
                             "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})
        return True

    def fail(self, part: str, item: str, reason: str) -> None:
        self.failures.append({"part": part, "item": item, "reason": reason})

    def save(self, description: str, **meta) -> None:
        (self.out / "manifest.json").write_text(json.dumps(
            {"description": description, "generated_at": self.now, **meta,
             "entries": self.entries, "failures": self.failures}, indent=1) + "\n")
        rebuild_all(self.out.parent)


def rebuild_all(root: Path) -> None:
    """``ALL-people-ai.jsonl``: one line per item of ``people/`` and ``ai/``, path relative to ``root``."""
    lines = []
    for sub in ("people", "ai"):
        mf = root / sub / "manifest.json"
        if mf.exists():
            for e in json.loads(mf.read_text())["entries"]:
                lines.append(json.dumps({**e, "path": f"{sub}/{e['path']}", "corpus": sub}))
    tmp = root / f"ALL-people-ai.jsonl.{os.getpid()}.tmp"
    tmp.write_text("".join(x + "\n" for x in lines))
    os.chmod(tmp, 0o600)
    tmp.replace(root / "ALL-people-ai.jsonl")


# ------------------------------------------------------------------ GitHub

def repo_of(url: str) -> str:
    """``owner/repo`` from an API or HTML issue URL."""
    m = re.search(r"(?:repos/|github\.com/)([^/]+/[^/]+)/(?:issues|pulls?)/", url)
    return m.group(1) if m else ""


def body_item(store: Store, part: str, source: str, author: str, it: dict, other_language) -> bool:
    text = community_prose(it.get("body") or "")
    kind = "pr" if it.get("pull_request") or "/pull/" in it.get("html_url", "") else "issue"
    key = f"{repo_of(it['html_url']).replace('/', '-')}-{it['number']}"
    if words(text) < MIN_BODY:
        store.fail(part, it["html_url"], f"under {MIN_BODY} words")
        return False
    if other_language(text):
        store.fail(part, it["html_url"], "not English")
        return False
    return store.add(part, "people-issue", source, key, text, it["html_url"], f"gh api search/issues ({kind})",
                     author=author, kind=kind, repo=repo_of(it["html_url"]))


def comment_item(store: Store, part: str, category: str, source: str, author: str, c: dict, via: str,
                 other_language) -> bool:
    text = community_prose(c.get("body") or "")
    if words(text) < MIN_COMMENT or other_language(text):
        return False
    return store.add(part, category, source, str(c["id"]), text, c["html_url"], via, author=author,
                     repo=repo_of(c["html_url"]))


def fetch_respected(store: Store, per_person: int, rng: random.Random, other_language) -> None:
    for handle in RESPECTED.values():
        source = author = f"respected:{handle}"
        n_body = n_rev = n_com = 0
        budget = {"body": per_person // 2, "review": per_person // 4, "comment": per_person - per_person // 2 - per_person // 4}
        items = search_issues(f"author:{handle}", 100)
        rng.shuffle(items)
        for it in items:
            if n_body >= budget["body"]:
                break
            n_body += body_item(store, "respected", source, author, it, other_language)
        for it in search_issues(f"reviewed-by:{handle} is:pr", 30):
            if n_rev >= budget["review"]:
                break
            repo = repo_of(it["html_url"])
            try:
                comments = gh([f"repos/{repo}/pulls/{it['number']}/comments?per_page=100"])
            except subprocess.CalledProcessError:
                continue
            took = 0
            for c in comments:
                if (c.get("user") or {}).get("login", "").lower() != handle.lower() or took == 2:
                    continue
                if comment_item(store, "respected", "people-review", source, author, c, "gh api pulls/N/comments",
                                other_language):
                    took += 1
                    n_rev += 1
        budget["comment"] += budget["review"] - n_rev                    # make up for few review comments
        for it in search_issues(f"commenter:{handle} -author:{handle}", 50):
            if n_com >= budget["comment"]:
                break
            repo = repo_of(it["html_url"])
            try:
                comments = gh([f"repos/{repo}/issues/{it['number']}/comments?per_page=100"])
            except subprocess.CalledProcessError:
                continue
            took = 0
            for c in comments:
                if (c.get("user") or {}).get("login", "").lower() != handle.lower() or took == 2:
                    continue
                if comment_item(store, "respected", "people-comment", source, author, c, "gh api issues/N/comments",
                                other_language):
                    took += 1
                    n_com += 1
        print(f"{handle}: {n_body} bodies, {n_rev} review comments, {n_com} comments", file=sys.stderr)


def fetch_community(store: Store, repos_per_lang: int, rng: random.Random, other_language) -> None:
    respected = {h.lower() for h in RESPECTED.values()}
    for lang in LANGS:
        _pace("search", SEARCH_GAP)
        q = f"language:{lang} stars:200..5000 pushed:>2025-06-01 fork:false archived:false"
        total = gh(["-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "per_page=1"])["total_count"]
        _pace("search", SEARCH_GAP)
        page = rng.randrange(max(1, min(total, 1000) // 30)) + 1
        repos = gh(["-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "per_page=30",
                    "-f", f"page={page}"])["items"]
        rng.shuffle(repos)
        source, author = f"community/{lang.lower().replace('+', 'p')}", "community"
        used = 0
        for r in repos:
            if used >= repos_per_lang:
                break
            name = r["full_name"]
            got = 0
            try:
                issues = gh([f"repos/{name}/issues?state=all&sort=updated&per_page=50"])
                comments = gh([f"repos/{name}/issues/comments?sort=created&direction=desc&per_page=100"])
                reviews = gh([f"repos/{name}/pulls/comments?sort=created&direction=desc&per_page=100"])
            except subprocess.CalledProcessError:
                store.fail("community", name, "API error")
                continue
            n = 0
            for it in issues:
                if n == 5:
                    break
                if is_bot(it.get("user")) or it["user"]["login"].lower() in respected:
                    continue
                n += body_item(store, "community", source, author, it, other_language)
            got += n
            for cs, cat, cap, via in ((comments, "people-comment", 3, "gh api issues/comments"),
                                      (reviews, "people-review", 2, "gh api pulls/comments")):
                n = 0
                for c in cs:
                    if n == cap:
                        break
                    if is_bot(c.get("user")) or c["user"]["login"].lower() in respected:
                        continue
                    n += comment_item(store, "community", cat, source, author, c, via, other_language)
                got += n
            if got:
                used += 1
            else:
                store.fail("community", name, "no usable text")
        print(f"{source}: {used} repositories", file=sys.stderr)


def wiki_pages(repo_dir: Path) -> list[Path]:
    return sorted(p for p in repo_dir.rglob("*") if p.suffix.lower() in (".md", ".markdown") and ".git" not in p.parts)


def fetch_wikis(store: Store, cache: Path, per_wiki: int, rng: random.Random, other_language, prose_text) -> None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    for repo, handle in WIKIS.items():
        dest = cache / repo.replace("/", "__")
        url = f"https://github.com/{repo}.wiki.git"
        if not dest.exists():
            r = subprocess.run(["git", "-c", f"http.userAgent={UA}", "clone", "--quiet", "--depth", "1", url, str(dest)],
                               check=False, capture_output=True, text=True, env=env, timeout=600)
            if r.returncode:
                store.fail("wikis", repo, "no public wiki")
                continue
        sha = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        pages = wiki_pages(dest)
        rng.shuffle(pages)
        kept = 0
        for p in pages:
            if kept == per_wiki:
                break
            raw = p.read_text(encoding="utf-8", errors="replace")
            text = community_prose(raw)
            if words(prose_text(text)) < 150 or other_language(text):
                continue
            name = p.relative_to(dest).with_suffix("").as_posix()
            kept += store.add("wikis", "people-wiki", f"wiki/{repo.replace('/', '-')}", name, text,
                              f"https://github.com/{repo}/wiki/{urllib.parse.quote(p.stem)}",
                              f"git clone --depth 1 {url} @{sha}", author=f"project-wiki:{handle}", repo=repo)
        print(f"wiki {repo}: {kept} of {len(pages)} pages", file=sys.stderr)
        if not kept:
            store.fail("wikis", repo, "no page with 150 words of prose")


# ------------------------------------------------------------------ Discourse

_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


def forum_get(host: str, path: str) -> dict | None:
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        req = urllib.request.Request(f"https://{host}/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            rp.parse(r.read().decode().splitlines())
        _robots[host] = rp
    url = f"https://{host}{path}"
    if not _robots[host].can_fetch(UA, url):
        print(f"robots.txt disallows {url}", file=sys.stderr)
        return None
    for attempt in range(3):
        _pace(host, FORUM_GAP)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After") or 30))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
    return None


def forum_posts(topic: dict) -> list[dict]:
    """The first post and replies of a ``/t/ID.json`` response, as {id, username, number, text}."""
    out = []
    for p in topic.get("post_stream", {}).get("posts", []):
        if p.get("user_id", 0) < 0 or p.get("action_code") or p.get("hidden"):
            continue                                                       # system user, moderator actions
        out.append({"id": p["id"], "username": p.get("username", ""), "number": p.get("post_number", 0),
                    "text": html_to_text(p.get("cooked") or "")})
    return out


def fetch_forums(store: Store, topics: int, rng: random.Random, other_language) -> None:
    respected = {h.lower() for hs in FORUM_PEOPLE.values() for h in hs}
    for host in FORUMS:
        ids = []
        for page in range(5):
            lat = forum_get(host, f"/latest.json?page={page}") or {}
            ids += [t["id"] for t in lat.get("topic_list", {}).get("topics", [])
                    if not t.get("pinned") and t.get("posts_count", 0) >= 2]
        rng.shuffle(ids)
        kept = 0
        for tid in ids[:topics]:
            t = forum_get(host, f"/t/{tid}.json")
            if not t:
                store.fail("forums", f"{host}/t/{tid}", "unreadable")
                continue
            replies = 0
            for p in forum_posts(t):
                if p["username"].lower() in respected or (p["number"] > 1 and replies == 3):
                    continue
                n = words(p["text"])
                if n < (MIN_BODY if p["number"] == 1 else MIN_COMMENT) or other_language(p["text"]):
                    continue
                if store.add("forums", "people-forum", f"community/{host}", f"{tid}-{p['number']}", p["text"],
                             f"https://{host}/t/{tid}/{p['number']}", f"GET https://{host}/t/{tid}.json",
                             fmt="text", author="community", post="topic" if p["number"] == 1 else "reply"):
                    kept += 1
                    replies += p["number"] > 1
        print(f"{host}: {kept} community posts", file=sys.stderr)
        for handle in FORUM_PEOPLE[host]:
            acts = []
            for flt in (4, 5):
                r = forum_get(host, f"/user_actions.json?username={urllib.parse.quote(handle)}&filter={flt}&offset=0")
                acts += (r or {}).get("user_actions", [])
            rng.shuffle(acts)
            kept = 0
            for a in acts:
                if kept == 15:
                    break
                t = forum_get(host, f"/posts/{a['post_id']}.json") if a.get("post_id") else None
                if not t or (t.get("username") or "").lower() != handle.lower():
                    continue
                text = html_to_text(t.get("cooked") or "")
                if words(text) < MIN_COMMENT or other_language(text):
                    continue
                kept += store.add("forums", "people-forum", f"respected:{handle}", f"{host}-{t['id']}", text,
                                  f"https://{host}/t/{t['topic_id']}/{t['post_number']}",
                                  f"GET https://{host}/posts/{t['id']}.json", fmt="text",
                                  author=f"respected:{handle}", host=host,
                                  post="topic" if t.get("post_number") == 1 else "reply")
            print(f"{host} {handle}: {kept} posts", file=sys.stderr)


def main() -> int:
    from readcost.lang import other_language

    sys.path.insert(0, str(Path(__file__).parent))
    from fetch_github_readmes import prose_text

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--parts", default="respected,community,wikis,forums")
    ap.add_argument("--per-person", type=int, default=32)
    ap.add_argument("--repos", type=int, default=4)
    ap.add_argument("--wiki-pages", type=int, default=12)
    ap.add_argument("--topics", type=int, default=25)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    parts = set(args.parts.split(","))
    store = Store(out, parts)
    rng = random.Random(args.seed)
    try:
        if "respected" in parts:
            fetch_respected(store, args.per_person, rng, other_language)
        if "community" in parts:
            fetch_community(store, args.repos, rng, other_language)
        if "wikis" in parts:
            cache = out / "raw" / "wikis"
            cache.mkdir(parents=True, exist_ok=True, mode=0o700)
            fetch_wikis(store, cache, args.wiki_pages, rng, other_language, prose_text)
        if "forums" in parts:
            fetch_forums(store, args.topics, rng, other_language)
    finally:
        store.save("Project community text by respected authors and a community baseline; "
                   "see scripts/fetch_people_text.py", seed=args.seed)
    print(len(store.entries), "texts;", len(store.failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
