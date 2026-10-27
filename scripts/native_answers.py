"""Model answers written from scratch versus human answers to the same questions.

    python3 -I scripts/native_answers.py fetch REF/hc3
    EVAL_OPENROUTER_API_KEY=... python3 -I scripts/native_answers.py ask REF/hc3
    python3 scripts/native_answers.py score REF/hc3

Questions come from HC3 (Hello-SimpleAI/HC3, CC BY-SA 4.0): wiki_csai, whose
human answers are Wikipedia passages on computer science and AI, and open_qa.
Each has a human answer and a ChatGPT answer from late 2022. ``ask`` sends
each sampled question, unchanged, to current models through OpenRouter, one
call at a time, at each model's default settings, and stores the plain-text
answer, as a user of a chat product would see it. ``score`` runs readcost on
every answer and compares each source with the human answer to the same
question. Data stays under REF, outside the repository.
"""

import json
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/Hello-SimpleAI/HC3/resolve/refs%2Fconvert%2Fparquet"
CONFIGS = ("wiki_csai", "open_qa")
PER_CONFIG = 30
MODELS = [
    "google/gemini-4-argon",
    "deepseek/deepseek-v4.1-flash",
    "x-ai/grok-4.7",
    "moonshotai/kimi-k3.1-pro",
    "mistralai/mistral-large-4-0",
]
URL = "https://openrouter.ai/api/v1/chat/completions"


def fetch(ref: Path) -> None:
    ref.mkdir(parents=True, exist_ok=True)
    for c in CONFIGS:
        out = ref / f"{c}.parquet"
        if not out.exists():
            urllib.request.urlretrieve(f"{BASE}/{c}/train/0000.parquet", out)
        print(out, out.stat().st_size)


def sample(ref: Path) -> list[dict]:
    """PER_CONFIG questions per config whose human answer has 80 to 400 words, fixed seed."""
    import pyarrow.parquet as pq

    rows = []
    for c in CONFIGS:
        table = pq.read_table(ref / f"{c}.parquet").to_pylist()
        ok = [r for r in table if r["human_answers"] and r["chatgpt_answers"]
              and 80 <= len(r["human_answers"][0].split()) <= 400]
        random.Random(1).shuffle(ok)
        rows += [{"qid": f"{c}/{r['id']}", "question": r["question"], "human": r["human_answers"][0],
                  "chatgpt-2022": r["chatgpt_answers"][0]} for r in ok[:PER_CONFIG]]
    return rows


def ask_text(model: str, question: str) -> tuple[str | None, dict]:
    body = {"model": model, "messages": [{"role": "user", "content": question}], "usage": {"include": True}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {os.environ['EVAL_OPENROUTER_API_KEY']}", "Content-Type": "application/json"})
    meta: dict = {"requested": model}
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read())
            meta["served"] = data.get("model")
            meta["cost"] = (data.get("usage") or {}).get("cost")
            return data["choices"][0]["message"]["content"], meta
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as exc:
            meta["error"] = str(exc)[:300]
            if attempt == 0:
                time.sleep(10)
    return None, meta


def ask(ref: Path) -> None:
    out = ref / "answers.jsonl"
    done = {(a["qid"], a["source"]) for a in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    with out.open("a") as fh:
        for row in sample(ref):
            for src in ("human", "chatgpt-2022"):
                if (row["qid"], src) not in done:
                    fh.write(json.dumps({"qid": row["qid"], "source": src, "text": row[src]}) + "\n")
            for model in MODELS:
                if (row["qid"], model) in done:
                    continue
                text, meta = ask_text(model, row["question"])
                fh.write(json.dumps({"qid": row["qid"], "source": model, "text": text, "meta": meta}) + "\n")
                fh.flush()
    print(out)


def score(ref: Path) -> None:
    from scipy.stats import wilcoxon

    from readcost import Analyzer, Config

    analyzer = Analyzer(Config())
    answers = [a for a in map(json.loads, (ref / "answers.jsonl").read_text().splitlines()) if a["text"]]
    m: dict[str, dict[str, dict]] = {}
    for a in answers:
        r = analyzer.check_text(a["text"], "markdown")
        if r.words < 40 or r.reading_ms_per_word is None:
            continue
        m.setdefault(a["source"], {})[a["qid"]] = {
            "words": r.words, "cost_index": r.cost_index, "ms_per_word": r.reading_ms_per_word,
            "seconds": r.reading_seconds, "findings_per_1k": 1000 * len(r.findings) / r.words,
            "not_pass": r.verdict != "pass"}
    human = m.get("human", {})
    keys = ("words", "cost_index", "findings_per_1k", "ms_per_word", "seconds")
    print(f"{len(human)} questions with a human answer of 40+ words\n")
    print("| Source | Answers | " + " | ".join(f"{k} median (above human)" for k in keys) + " | Not passing |")
    print("| --- | --- | " + " | ".join("---" for _ in keys) + " | --- |")
    for src in ["human", "chatgpt-2022", *MODELS]:
        rows = m.get(src, {})
        if not rows:
            continue
        cells = []
        for k in keys:
            med = statistics.median(v[k] for v in rows.values())
            if src == "human":
                cells.append(f"{med:.3g}")
                continue
            pairs = [(rows[q][k], human[q][k]) for q in rows if q in human]
            above = sum(a > b for a, b in pairs) / len(pairs)
            diffs = [a - b for a, b in pairs if a != b]
            p = wilcoxon(diffs).pvalue if len(diffs) > 5 else float("nan")
            cells.append(f"{med:.3g} ({above:.0%}, p {p:.2g})")
        share = sum(v["not_pass"] for v in rows.values()) / len(rows)
        print(f"| {src} | {len(rows)} | " + " | ".join(cells) + f" | {share:.0%} |")


if __name__ == "__main__":
    {"fetch": fetch, "ask": ask, "score": score}[sys.argv[1]](Path(sys.argv[2]))
