"""Blind labels for the per-rule benchmark from the model rater ensemble.

    EVAL_OPENROUTER_API_KEY=... python3 -I scripts/label_rulebench.py label BENCH OUT_DIR
    python3 scripts/label_rulebench.py summary BENCH OUT_DIR

BENCH is the rulebench.jsonl that scripts/fetch_rulebench.py writes (with
sentences). Each strict rater of scripts/rater_ensemble.py sees, for every
item, only the rule's definition and the sentence, never the expected label
or readcost's output, and answers whether the rule should flag the sentence
and whether doing so would help a writer. Items go in batches of 30, one
call at a time. ``summary`` compares the raters' majority with each item's
stored label, split by who made that label.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rater_ensemble  # noqa: E402  (ask(), MODELS)

STRICT = [m for m in rater_ensemble.MODELS
          if m not in ("meta-llama/llama-4-maverick", "minimax/minimax-m3")]

PROMPT = """You are helping build a test set for a prose linter. For each item you get one rule and one
sentence from technical writing. Decide whether the rule should flag that sentence: "yes" if the construction
the rule describes is really in the sentence and an experienced technical editor would want it pointed out
because it costs readers time; "no" if the construction is absent (for example a misreading of the grammar),
or present but harmless (a fixed phrase, a term of art, a name, an ordinary verb). Judge each item on its own.
Give a reason of at most 10 words.

Rules:
- stacked-nouns: three or more nouns in a row used as one noun phrase ("source segment rebuilds").
- long-dependency: a subject far from its verb, or a verb far from its object.
- inanimate-subject: a thing as subject of a verb that normally needs a person ("the file decides").
- reduced-object-relative: an object relative clause without "that" ("the format the reader expects").
- hyphen-compound: an ad hoc hyphenated noun-noun compound used as a modifier ("storage-shrink use case").
- inline-list: four or more coordinated items, or slash-joined items, inside one sentence.

Return JSON matching the schema: one entry per item, with its "i" unchanged."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["labels"],
          "properties": {"labels": {"type": "array", "items": {
              "type": "object", "additionalProperties": False, "required": ["i", "flag", "reason"],
              "properties": {"i": {"type": "integer"}, "flag": {"type": "string", "enum": ["yes", "no"]},
                             "reason": {"type": "string"}}}}}}


def label(bench: Path, out: Path) -> None:
    items = [json.loads(x) for x in bench.read_text().splitlines()]
    out.mkdir(parents=True, exist_ok=True)
    payload = [{"i": i, "rule": it["rule"], "sentence": it["text"]} for i, it in enumerate(items)]
    for model in STRICT:
        dest = out / f"labels-{model.replace('/', '__')}.json"
        done = json.loads(dest.read_text()) if dest.exists() else {}
        for start in range(0, len(payload), 30):
            batch = [x for x in payload[start:start + 30] if str(x["i"]) not in done]
            if not batch:
                continue
            t = time.time()
            data, meta = rater_ensemble.ask(model, PROMPT + "\n\nItems:\n" + json.dumps(batch, indent=1), SCHEMA)
            print(model, start, "ok" if data else f"FAILED {meta.get('error')}", meta.get("cost"),
                  f"{time.time() - t:.0f}s", flush=True)
            for lab in (data or {}).get("labels", []):
                if lab.get("flag") in ("yes", "no"):
                    done[str(lab["i"])] = {"flag": lab["flag"], "reason": lab.get("reason", "")}
            dest.write_text(json.dumps(done, indent=1))


def summary(bench: Path, out: Path) -> None:
    items = [json.loads(x) for x in bench.read_text().splitlines()]
    labels = {p.stem.removeprefix("labels-"): json.loads(p.read_text()) for p in out.glob("labels-*.json")}
    if not labels:
        sys.exit(f"no labels in {out}; run the label step first")
    rows: dict[str, dict[str, int]] = {}
    for i, it in enumerate(items):
        votes = [labels[m][str(i)]["flag"] for m in labels if str(i) in labels[m]]
        r = rows.setdefault(it["labelled_by"], {"agree": 0, "disagree": 0, "tie": 0, "missing": 0})
        if len(votes) < len(labels):
            r["missing"] += 1
            continue
        yes = votes.count("yes")
        if 2 * yes == len(votes):
            r["tie"] += 1
            continue
        r["agree" if ("fire" if 2 * yes > len(votes) else "no-fire") == it["expected"] else "disagree"] += 1
    print(f"{len(labels)} raters")
    for who, r in sorted(rows.items()):
        print(f"stored label by {who}: " + ", ".join(f"{k} {v}" for k, v in r.items()))


if __name__ == "__main__":
    {"label": label, "summary": summary}[sys.argv[1]](Path(sys.argv[2]), Path(sys.argv[3]))
