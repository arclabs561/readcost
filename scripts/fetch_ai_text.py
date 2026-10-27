"""Fetch AI-written text with matched human text: agent pull requests and machine-text detection sets.

    PYTHONPATH=src python3 scripts/fetch_ai_text.py /Volumes/Rebuildable/readcost-ref/broad/ai
    PYTHONPATH=src python3 scripts/eval_people_ai.py /Volumes/Rebuildable/readcost-ref/broad

Needs pyarrow (and fsspec with aiohttp for RAID). Five parts, each selectable
with ``--parts``:

- ``aidev``: AIDev v3 (hao-li/AIDev at tag v3, CC BY 4.0 for the
  compilation), ``pull_request`` (agent pull requests in repositories with
  more than 100 stars) and ``human_pull_request`` (people's pull requests in
  the same repositories). For each agent, up to ``--aidev`` agent pull
  requests, each paired with a human pull request from the same repository
  that no other pair uses. Text is title and body after ``community_prose``;
  both sides need 40 words. Category ``agent-pr``; source ``aidev/AGENT`` or
  ``aidev/human``; ``pair_id``, ``role`` (``agent`` or ``human``).
- ``live``: current agent pull requests from GitHub search
  (``is:pr author:app/copilot-swe-agent``, ``app/devin-ai-integration``,
  ``app/google-labs-jules``, and body markers for Claude Code and Codex),
  created in the last 60 days, four random results pages of the first ten; each paired with
  the most recent pull request in the same repository by a person, with no
  agent marker in its body. Category ``agent-pr-live``.
- ``raid``: RAID (liamdugan/raid, MIT), read by HTTP range requests from the
  Hub's Parquet conversion of the train split. Per domain (abstracts, books,
  news, recipes, reddit, reviews, wiki), ``--raid`` human texts and every
  generation that names one of them as ``source_id`` with no attack, greedy
  decoding and no repetition penalty. Category ``mgt-raid``; ``pair_id`` the
  human text's id; source ``raid/MODEL``.
- ``mage``: MAGE (yaful/MAGE, Apache-2.0), ``test.csv``. Per generator, up
  to ``--mage`` machine texts, each paired with a human text of the same
  domain (``src`` prefix) drawn without replacement. Category ``mgt-mage``.
- ``m4``: M4 (mbzuai-nlp/M4 on GitHub; no licence stated, so local aggregate
  analysis only), the English files, whose records hold a human and a machine
  text on the same prompt. The first 3 MB of each file is read (a prefix, not
  a random sample) and ``--m4`` records with 50 words on both sides drawn
  from it. Category ``mgt-m4``.

Machine and human texts from detection sets need 50 words. Every request
carries the project's User-Agent; Hub and GitHub raw downloads are a second
apart. Writes ``manifest.json`` in the schema of scripts/fetch_eval_corpus.py
and rebuilds ``../ALL-people-ai.jsonl``. The text stays under the output
directory, outside the repository.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

_spec = importlib.util.spec_from_file_location("fetch_people_text", Path(__file__).with_name("fetch_people_text.py"))
people = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(people)

UA = people.UA
HF = "https://huggingface.co/datasets"
AIDEV_LICENCE = "CC-BY-4.0 compilation (hao-li/AIDev v3); text each author's under GitHub's terms; local aggregate analysis only"
RAID_LICENCE = "MIT (liamdugan/raid card); human side from third-party sources; local aggregate analysis only"
MAGE_LICENCE = "Apache-2.0 (yaful/MAGE card); human side from third-party sources; local aggregate analysis only"
M4_LICENCE = "none stated (mbzuai-nlp/M4 has no licence); local aggregate analysis only"
RAID_DOMAINS = ("abstracts", "books", "news", "recipes", "reddit", "reviews", "wiki")
M4_FILES = ("arxiv_chatGPT", "arxiv_cohere", "arxiv_davinci", "arxiv_dolly", "arxiv_flant5", "arxiv_bloomz",
            "peerread_chatgpt", "peerread_cohere", "peerread_davinci", "peerread_dolly", "peerread_llama",
            "peerread_bloomz", "reddit_chatGPT", "reddit_cohere", "reddit_davinci", "reddit_dolly",
            "reddit_flant5", "reddit_bloomz", "wikihow_chatGPT", "wikihow_cohere", "wikihow_davinci",
            "wikihow_dolly2", "wikihow_bloomz", "wikipedia_chatgpt", "wikipedia_cohere", "wikipedia_davinci",
            "wikipedia_dolly", "wikipedia_bloomz")
# agent -> GitHub search qualifier for its pull requests
LIVE = {"copilot": "author:app/copilot-swe-agent", "devin": "author:app/devin-ai-integration",
        "jules": "author:app/google-labs-jules", "claude-code": '"Generated with Claude Code" in:body',
        "codex": '"chatgpt.com/codex/tasks" in:body'}
AGENT_MARKERS = re.compile(r"(?i)generated with \[?claude code|chatgpt\.com/codex|devin\.ai|copilot-swe-agent|"
                           r"jules\.google|cursor\.com/(agents|background)|co-authored-by: (claude|copilot|cursor)")
MIN_PR, MIN_MGT = 40, 50
_last = 0.0


def download(url: str, dest: Path, byte_range: str | None = None) -> Path:
    """Fetch ``url`` to ``dest`` once (kept for reruns), a second after the previous download."""
    global _last
    if dest.exists():
        return dest
    wait = _last + 1.0 - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    headers = {"User-Agent": UA} | ({"Range": f"bytes={byte_range}"} if byte_range else {})
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=600) as r:
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(r.read())
        tmp.replace(dest)
    return dest


def pr_text(title: str | None, body: str | None) -> str:
    """A pull request's title as a heading over its cleaned body."""
    body = people.community_prose(body or "")
    return f"# {(title or '').strip()}\n\n{body}" if body else ""


def complete_lines(blob: bytes) -> list[str]:
    """The whole lines of a byte prefix: the last, possibly cut, line is dropped."""
    lines = blob.decode("utf-8", errors="replace").split("\n")
    return [x for x in lines[:-1] if x.strip()]


def m4_texts(rec: dict) -> tuple[str, str] | None:
    """(human, machine) of an M4 record; list fields keep their first element.

    Most files use ``human_text`` and ``machine_text``. The BLOOMZ files keep
    the human side in ``abstract``, ``text`` or ``human_reviews`` and the
    generation in ``machine_abstract``, ``machine_answer`` or
    ``bloom_reviews``; their ``machine_text`` holds the prompt.
    """
    def one(*keys):
        for k in keys:
            v = rec.get(k)
            if isinstance(v, list):
                v = v[0] if v else ""
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    h = one("human_text", "abstract", "text", "human_reviews")
    m = one("machine_abstract", "machine_answer", "bloom_reviews", "machine_text")
    return (h, m) if h and m else None


def mage_src(src: str) -> tuple[str, str]:
    """(domain, generator) of a MAGE ``src``; generator ``human`` for human text."""
    if src.endswith("_human"):
        return src[: -len("_human")], "human"
    m = re.match(r"(.+?)_machine_(?:[a-z]+_)*?(?:continuation|topical|specified)_(.+)$", src)
    if m:
        return m.group(1), m.group(2)
    dom, _, gen = src.partition("_machine_")
    return dom, gen or "unknown"


def para_text(s: str) -> str:
    s = s.replace("\r\n", "\n").strip()
    return re.sub(r"\n{3,}", "\n\n", s) + "\n"


# ------------------------------------------------------------------ parts

def fetch_aidev(store, raw: Path, per_agent: int, rng: random.Random, other_language) -> None:
    import pyarrow.parquet as pq

    tables = {}
    for name in ("pull_request", "human_pull_request", "repository"):
        tables[name] = pq.read_table(download(f"{HF}/hao-li/AIDev/resolve/v3/{name}.parquet",
                                              raw / "aidev" / f"{name}.parquet")).to_pylist()
    lang = {r["url"]: r["language"] for r in tables["repository"]}
    human_by_repo: dict[str, list[dict]] = defaultdict(list)
    for h in tables["human_pull_request"]:
        human_by_repo[h["repo_url"]].append(h)
    for v in human_by_repo.values():
        rng.shuffle(v)
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for p in tables["pull_request"]:
        if p["repo_url"] in human_by_repo:
            by_agent[p["agent"]].append(p)
    used: set[int] = set()
    for agent, prs in sorted(by_agent.items()):
        rng.shuffle(prs)
        kept = 0
        for p in prs:
            if kept == per_agent:
                break
            a = pr_text(p["title"], p["body"])
            if people.words(a) < MIN_PR or other_language(a):
                continue
            human = None
            for h in human_by_repo[p["repo_url"]]:
                t = pr_text(h["title"], h["body"])
                if h["id"] not in used and people.words(t) >= MIN_PR and not AGENT_MARKERS.search(h["body"] or "") \
                        and not other_language(t):
                    human = (h, t)
                    break
            if not human:
                continue
            h, t = human
            used.add(h["id"])
            pair = f"aidev-{p['id']}"
            repo = p["repo_url"].removeprefix("https://api.github.com/repos/")
            common = {"license": AIDEV_LICENCE, "pair_id": pair, "agent": agent, "repo": repo,
                      "language": lang.get(p["repo_url"]) or ""}
            store.add("aidev", "agent-pr", f"aidev/{agent}", str(p["id"]), a, p["html_url"],
                      "hao-li/AIDev@v3 pull_request.parquet", author=f"agent:{agent}", role="agent", **common)
            store.add("aidev", "agent-pr", "aidev/human", str(h["id"]), t, h["html_url"],
                      "hao-li/AIDev@v3 human_pull_request.parquet", author="community", role="human", **common)
            kept += 1
        print(f"aidev {agent}: {kept} pairs of {len(prs)}", file=sys.stderr)


def fetch_live(store, per_agent: int, rng: random.Random, other_language) -> None:
    since = (datetime.now(UTC) - timedelta(days=60)).date().isoformat()
    for agent, qual in LIVE.items():
        q = f"is:pr is:public {qual} created:>{since}"
        items = [it for page in rng.sample(range(1, 11), 4) for it in people.search_issues(q, 50, page=page)]
        rng.shuffle(items)
        kept, repos = 0, set()
        for it in items:
            if kept == per_agent:
                break
            repo = people.repo_of(it["html_url"])
            if repo in repos:
                continue
            a = pr_text(it["title"], it.get("body"))
            if people.words(a) < MIN_PR or other_language(a):
                continue
            try:
                pulls = people.gh([f"repos/{repo}/pulls?state=all&sort=created&direction=desc&per_page=50"])
            except subprocess.CalledProcessError:
                continue
            human = None
            for h in pulls:
                t = pr_text(h["title"], h.get("body"))
                if (not people.is_bot(h.get("user")) and not AGENT_MARKERS.search(h.get("body") or "")
                        and h["number"] != it["number"] and people.words(t) >= MIN_PR and not other_language(t)):
                    human = (h, t)
                    break
            if not human:
                store.fail("live", it["html_url"], "no human pull request in the repository")
                continue
            h, t = human
            repos.add(repo)
            pair = f"live-{repo.replace('/', '-')}-{it['number']}"
            common = {"pair_id": pair, "agent": agent, "repo": repo}
            store.add("live", "agent-pr-live", f"live/{agent}", f"{repo.replace('/', '-')}-{it['number']}", a,
                      it["html_url"], f"gh api search/issues q={q!r}", author=f"agent:{agent}", role="agent", **common)
            store.add("live", "agent-pr-live", "live/human", f"{repo.replace('/', '-')}-{h['number']}", t,
                      h["html_url"], f"gh api repos/{repo}/pulls", author="community", role="human", **common)
            kept += 1
        print(f"live {agent}: {kept} pairs of {len(items)} found", file=sys.stderr)


def fetch_raid(store, per_domain: int, rng: random.Random, other_language) -> None:
    import fsspec
    import pyarrow.parquet as pq

    info = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://datasets-server.huggingface.co/parquet?dataset=liamdugan/raid",
        headers={"User-Agent": UA}), timeout=60).read())
    shards = [f["url"] for f in info["parquet_files"] if f["config"] == "raid" and f["split"] == "train"]
    fs = fsspec.filesystem("http", headers={"User-Agent": UA})
    meta_cols = ["id", "source_id", "model", "domain", "attack", "decoding", "repetition_penalty"]
    done: set[str] = set()
    for url in shards:
        pf = pq.ParquetFile(fs.open(url, block_size=2 ** 20))
        t = pf.read(columns=meta_cols).to_pydict()
        n = len(t["id"])
        domains = set(t["domain"]) & (set(RAID_DOMAINS) - done)
        if not domains:
            continue
        # row index -> row group, to read the generation column only where needed
        starts, acc = [], 0
        for g in range(pf.metadata.num_row_groups):
            starts.append(acc)
            acc += pf.metadata.row_group(g).num_rows
        for dom in sorted(domains):
            humans = [i for i in range(n) if t["domain"][i] == dom and t["model"][i] == "human"]
            gens: dict[str, list[int]] = defaultdict(list)
            for i in range(n):
                if (t["domain"][i] == dom and t["model"][i] != "human" and t["attack"][i] == "none"
                        and t["decoding"][i] == "greedy" and t["repetition_penalty"][i] == "no"):
                    gens[t["source_id"][i]].append(i)
            humans = [i for i in humans if len(gens.get(t["id"][i], [])) >= 3]
            rng.shuffle(humans)
            chosen = humans[:per_domain]
            rows = sorted(chosen + [j for i in chosen for j in gens[t["id"][i]]])
            groups = sorted({max(g for g, s in enumerate(starts) if s <= r) for r in rows})
            text: dict[int, str] = {}
            for g in groups:
                col = pf.read_row_group(g, columns=["generation"]).column(0).to_pylist()
                for r in rows:
                    if starts[g] <= r < starts[g] + len(col):
                        text[r] = col[r - starts[g]]
            kept = 0
            for i in chosen:
                pair = f"raid-{t['id'][i]}"
                h = para_text(text[i])
                if people.words(h) < MIN_MGT:
                    continue
                store.add("raid", "mgt-raid", "raid/human", t["id"][i], h, f"{HF}/liamdugan/raid",
                          f"{url} id={t['id'][i]}", fmt="text", license=RAID_LICENCE, author="human",
                          role="human", pair_id=pair, domain=dom, generator="human")
                for j in gens[t["id"][i]]:
                    m = para_text(text[j])
                    if people.words(m) < MIN_MGT:
                        continue
                    store.add("raid", "mgt-raid", f"raid/{t['model'][j]}", t["id"][j], m, f"{HF}/liamdugan/raid",
                              f"{url} id={t['id'][j]}", fmt="text", license=RAID_LICENCE,
                              author=f"model:{t['model'][j]}", role="machine", pair_id=pair, domain=dom,
                              generator=t["model"][j])
                kept += 1
            print(f"raid {dom}: {kept} human texts with their generations", file=sys.stderr)
            done.add(dom)
    for dom in set(RAID_DOMAINS) - done:
        store.fail("raid", dom, "domain not in the Hub's partial Parquet conversion of train")


def fetch_mage(store, raw: Path, per_gen: int, rng: random.Random, other_language) -> None:
    path = download(f"{HF}/yaful/MAGE/resolve/main/test.csv", raw / "mage" / "test.csv")
    csv.field_size_limit(10 ** 8)
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    humans: dict[str, list[int]] = defaultdict(list)
    machines: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        dom, gen = mage_src(r["src"])
        if people.words(r["text"]) < MIN_MGT:
            continue
        (humans[dom] if gen == "human" else machines[gen]).append(i)
    for v in (*humans.values(), *machines.values()):
        rng.shuffle(v)
    for gen, idx in sorted(machines.items()):
        kept = 0
        for i in idx:
            if kept == per_gen:
                break
            dom = mage_src(rows[i]["src"])[0]
            if not humans.get(dom) or other_language(rows[i]["text"]):
                continue
            j = humans[dom].pop()
            pair = f"mage-{i}"
            common = {"license": MAGE_LICENCE, "pair_id": pair, "domain": dom, "fmt": "text"}
            store.add("mage", "mgt-mage", f"mage/{gen}", str(i), para_text(rows[i]["text"]),
                      f"{HF}/yaful/MAGE", f"test.csv row {i} src={rows[i]['src']}", author=f"model:{gen}",
                      role="machine", generator=gen, **common)
            store.add("mage", "mgt-mage", "mage/human", f"{j}-for-{i}", para_text(rows[j]["text"]),
                      f"{HF}/yaful/MAGE", f"test.csv row {j} src={rows[j]['src']}", author="human",
                      role="human", generator="human", **common)
            kept += 1
        print(f"mage {gen}: {kept} pairs", file=sys.stderr)


def fetch_m4(store, raw: Path, per_file: int, rng: random.Random, other_language) -> None:
    for name in M4_FILES:
        url = f"https://raw.githubusercontent.com/mbzuai-nlp/M4/main/data/{name}.jsonl"
        try:
            blob = download(url, raw / "m4" / f"{name}.head.jsonl", "0-3000000").read_bytes()
        except OSError as e:
            store.fail("m4", name, f"download failed: {e}")
            continue
        recs = []
        for line in complete_lines(blob):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            pair = m4_texts(rec)
            if pair and min(people.words(pair[0]), people.words(pair[1])) >= MIN_MGT:
                recs.append((rec, pair))
        rng.shuffle(recs)
        domain = name.split("_")[0]
        kept = 0
        for k, (rec, (h, m)) in enumerate(recs):
            if kept == per_file:
                break
            if other_language(h) or other_language(m):
                continue
            gen = str(rec.get("model") or name.split("_", 1)[1]).lower()
            key = f"{name}-{k}"
            common = {"license": M4_LICENCE, "pair_id": f"m4-{key}", "domain": domain, "fmt": "text"}
            store.add("m4", "mgt-m4", f"m4/{gen}", f"{key}-m", para_text(m), url, f"{url} (first 3 MB)",
                      author=f"model:{gen}", role="machine", generator=gen, **common)
            store.add("m4", "mgt-m4", "m4/human", f"{key}-h", para_text(h), url, f"{url} (first 3 MB)",
                      author="human", role="human", generator="human", **common)
            kept += 1
        print(f"m4 {name}: {kept} pairs of {len(recs)}", file=sys.stderr)


def main() -> int:
    from readcost.lang import other_language

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--parts", default="aidev,raid,mage,m4,live")
    ap.add_argument("--aidev", type=int, default=80)
    ap.add_argument("--live", type=int, default=25)
    ap.add_argument("--raid", type=int, default=15)
    ap.add_argument("--mage", type=int, default=25)
    ap.add_argument("--m4", type=int, default=25)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = out / "raw"
    parts = set(args.parts.split(","))
    store = people.Store(out, parts)
    rng = random.Random(args.seed)
    try:
        if "aidev" in parts:
            fetch_aidev(store, raw, args.aidev, rng, other_language)
        if "mage" in parts:
            fetch_mage(store, raw, args.mage, rng, other_language)
        if "m4" in parts:
            fetch_m4(store, raw, args.m4, rng, other_language)
        if "raid" in parts:
            fetch_raid(store, args.raid, rng, other_language)
        if "live" in parts:
            fetch_live(store, args.live, rng, other_language)
    finally:
        store.save("AI-written text with matched human text; see scripts/fetch_ai_text.py", seed=args.seed)
    print(len(store.entries), "texts;", len(store.failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
