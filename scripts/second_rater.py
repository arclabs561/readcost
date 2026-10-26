"""Blind second rater for the readcost precision sample, via headless Codex.

    python3 -I scripts/second_rater.py ref/eval ref/eval/analysis/rater2-codex

Reads CORPUS/results/sample.jsonl (the 210 sampled findings) and asks Codex to
label each one with the same rubric the first rater used, without showing the
first rater's labels. Batches run one at a time. Writes OUT_DIR/labels2.json
and the per-batch prompts and answers for audit.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

RUBRIC = """You are labelling findings from a prose linter called readcost. Each finding says that a sentence
contains a construction that may slow readers down. Judge each finding on its own, as an experienced
technical editor would.

Labels:
- "c" (correct): the construction is really there and it is a real reading cost an editor would fix.
- "d" (defensible): the construction is there and an editor might reasonably flag it, but fixing it is optional
  or the author's choice is fine.
- "w" (wrong): the construction is not really there (misparse, wrong definition), or it is there but costs the
  reader nothing (a fixed phrase, a term of art, an idiom, an ordinary verb).

Also give "present": true if the construction the rule names is actually in the sentence (judged by the rule's
definition, apart from whether it costs the reader), else false. Give a short "cause" (under 8 words).

Rules:
- stacked-nouns: three or more nouns in a row used as one noun phrase ("source segment rebuilds").
- long-dependency: related words (subject and verb, verb and object) far apart in the sentence.
- inanimate-subject: a thing as subject of a verb that normally needs a person ("the file decides").
- denominal-verb: a noun pressed into service as a verb ("footnote the exception").
- reduced-object-relative: an object relative clause without "that" ("the format the reader expects").
- hyphen-compound: an ad hoc hyphenated noun-noun compound used as a modifier ("storage-shrink use case").
- inline-list: four or more coordinated items, or slash-joined items, inside one sentence.

Code spans in the sentence may appear as the placeholder word "Xcode"; treat it as a code identifier.
Return JSON matching the schema: one entry per finding, with its "i" unchanged."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["labels"],
    "properties": {"labels": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["i", "label", "present", "cause"],
        "properties": {
            "i": {"type": "integer"},
            "label": {"type": "string", "enum": ["c", "d", "w"]},
            "present": {"type": "boolean"},
            "cause": {"type": "string"},
        }}}},
}


def main(corpus: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "schema.json").write_text(json.dumps(SCHEMA))
    rows = [json.loads(line) for line in (corpus / "results/sample.jsonl").read_text().splitlines()]
    items = [{"i": i, "rule": r["feature"], "message": r["message"], "excerpt": r["excerpt"],
              "sentence": r["sentence"]} for i, r in enumerate(rows)]
    labels = {}
    if (out / "labels2.json").exists():
        labels = {int(k): v for k, v in json.loads((out / "labels2.json").read_text()).items()}
    for start in range(0, len(items), 30):
        batch = [x for x in items[start:start + 30] if x["i"] not in labels]
        if not batch:
            continue
        prompt = RUBRIC + "\n\nFindings:\n" + json.dumps(batch, ensure_ascii=False, indent=1)
        (out / f"prompt-{start:03d}.txt").write_text(prompt)
        answer = out / f"answer-{start:03d}.json"
        t = time.time()
        proc = subprocess.run(
            ["gtimeout", "600", "codex", "exec", "--model", "gpt-6.1-sol", "--sandbox", "read-only",
             "--ephemeral", "--skip-git-repo-check", "--ignore-rules", "-c", "project_doc_max_bytes=0",
             "--output-schema", str(out / "schema.json"), "-o", str(answer), "-"],
            input=prompt, capture_output=True, text=True, cwd=out, check=False)
        print(f"batch {start}: exit {proc.returncode} in {time.time() - t:.0f}s", flush=True)
        if proc.returncode != 0 or not answer.exists():
            (out / f"stderr-{start:03d}.txt").write_text(proc.stderr[-4000:])
            continue
        for lab in json.loads(answer.read_text())["labels"]:
            labels[lab["i"]] = {"label": lab["label"], "present": lab["present"], "cause": lab["cause"]}
        (out / "labels2.json").write_text(json.dumps(labels, indent=1))
    print(len(labels), "of", len(items), "labelled")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
