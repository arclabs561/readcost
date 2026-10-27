"""Does readcost flag non-native writers more? Learner essays by CEFR level against native essays.

    D=/Volumes/Rebuildable/readcost-ref/datasets/wi-locness
    curl -sfL --max-time 120 -o $D/wi+locness_v2.1.bea19.tar.gz \
      https://www.cl.cam.ac.uk/research/nl/bea2019st/data/wi+locness_v2.1.bea19.tar.gz
    mkdir -p $D/x && tar -xzf $D/wi+locness_v2.1.bea19.tar.gz -C $D/x
    python3 -I scripts/eval_learner_essays.py $D/x/wi+locness/json

Data: W&I+LOCNESS v2.1, released for the BEA-2019 shared task on grammatical
error correction (https://www.cl.cam.ac.uk/research/nl/bea2019st/).
Write & Improve essays by learners of English with a CEFR level assigned by
annotators (A, B, C; finer levels such as B1.ii in the JSON), and 50 essays by
native English students from LOCNESS (level N; dev split only). Both licences
allow non-commercial research use only; LOCNESS text may not be passed to
third parties and W&I excerpts are limited to under 100 words, so the text
stays outside the repository and only aggregates are reported.

Each essay is checked as plain text with readcost's default rules, then again
after applying the first annotator's corrections. The corrected version tells
how much of a group's rate comes from grammatical errors (which can mislead
the parser) rather than from the constructions themselves. Printed per group:
essays, words, median cost index, verdict shares, predicted ms per word, and
findings per 1,000 words for each rule, pooled over the group.
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from readcost import Analyzer, Config


def corrected(text: str, edits: list) -> str:
    if not edits:
        return text
    out, last = [], len(text)
    for e in sorted(edits[0][1], key=lambda e: e[0], reverse=True):
        start, end, repl = e[0], e[1], e[2]
        if end > last:  # overlaps an edit already applied
            continue
        out.append(text[end:last])
        out.append(repl or "")
        last = start
    out.append(text[:last])
    return "".join(reversed(out))


def main(root: Path) -> None:
    a = Analyzer(Config())
    rules = [f for f in a.enabled if f != "long-sentence"]
    stats: dict[tuple[str, str], dict] = defaultdict(lambda: {"n": 0, "words": 0, "counts": Counter(), "ci": [],
                                                              "verdicts": Counter(), "ms": []})
    for p in sorted(root.glob("*.json")):
        for line in p.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            level = e["cefr"]
            groups = [level[0], level.split(".")[0]] if level != "N" else ["N"]
            for version, text in (("original", e["text"]), ("corrected", corrected(e["text"], e.get("edits")))):
                r = a.check_text(text, "text")
                if r.words < 40:
                    continue
                for g in dict.fromkeys(groups):
                    s = stats[(g, version)]
                    s["n"] += 1
                    s["words"] += r.words
                    s["counts"].update(r.counts())
                    s["ci"].append(r.cost_index)
                    s["verdicts"][r.verdict] += 1
                    if r.reading_ms_per_word is not None:
                        s["ms"].append(r.reading_ms_per_word)
    order = ["A", "B", "C", "N", "A1", "A2", "B1", "B2", "C1", "C2"]
    for version in ("original", "corrected"):
        print(f"\n### {version} text\n")
        head = ["Group", "Essays", "Words", "CI p50", "CI p90", "Not passing", "ms/word p50", "all rules",
                *rules]
        print("| " + " | ".join(head) + " |")
        print("|" + " --- |" * len(head))
        for g in order:
            s = stats.get((g, version))
            if not s or not s["n"]:
                continue
            ci = sorted(s["ci"])
            p90 = ci[int(0.9 * (len(ci) - 1))]
            notpass = 1 - s["verdicts"]["pass"] / s["n"]
            per = [1000 * s["counts"][f] / s["words"] for f in rules]
            cells = [g, s["n"], s["words"], f"{statistics.median(ci):.1f}", f"{p90:.1f}", f"{notpass:.0%}",
                     f"{statistics.median(s['ms']):.0f}", f"{sum(per):.2f}", *(f"{x:.2f}" for x in per)]
            print("| " + " | ".join(str(c) for c in cells) + " |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
