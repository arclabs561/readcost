"""Split labelled long-dependency findings by what fills the gap.

    uv run scripts/eval_gap_content.py ref/eval/results-RUN

RUN is a results directory written by scripts/eval_corpus.py. For every
long-dependency finding in its findings.jsonl that the raters labelled
(eval/labels/, keyed as in scripts/eval_report.py), the sentence is reparsed
with `long_dependency_gap = "content"` and the gap is classed as an object
relative, another clause, prepositional phrases only, or something else
without a verb (features.gap_content). The table gives, per class, how many
labelled findings fall in it and how many the eight-rater majority accepts.

The setting lowers the "prepositional" class to info. It is worth making the
default only if that class is accepted less often than the others; with the
10 to 30 findings per class this sample can give, only a large gap between
classes means anything. The corpus stays outside the repository, so this
runs locally, not in CI.
"""

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_report import LENIENT, key, load_labels, load_run  # noqa: E402

from readcost import Analyzer, Config  # noqa: E402

CLASSES = {"an object relative clause in between": "object relative",
           "a clause in between": "clause",
           "only prepositional phrases in between": "prepositional",
           "no clause in between": "other"}


def gap_class(analyzer: Analyzer, sentence: str) -> str | None:
    found = [f for f in analyzer.check_text(sentence, "markdown").findings if f.feature == "long-dependency"]
    if not found:
        return None  # not reported when the sentence is checked alone
    note = found[0].message.rsplit("; ", 1)[-1]
    return CLASSES.get(note)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    _, findings = load_run(Path(argv[0]))
    labels = load_labels()
    sample = set.intersection(*(set(v) for v in labels.values()))
    eight = [r for r in sorted(labels) if r not in LENIENT]
    analyzer = Analyzer(Config(long_dependency_gap="content"))
    rows: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for f in findings:
        k = key(f)
        if f["feature"] != "long-dependency" or k not in sample:
            continue
        cls = gap_class(analyzer, f["sentence"]) or "not reported alone"
        rows[cls]["labelled"] += 1
        rows[cls]["accepted"] += sum(labels[r][k] in "cd" for r in eight) > len(eight) / 2
    print("| Gap | Labelled | Accepted by the eight-rater majority |")
    print("| --- | --- | --- |")
    for cls in [*CLASSES.values(), "not reported alone"]:
        c = rows.get(cls)
        if c:
            print(f"| {cls} | {c['labelled']} | {c['accepted']} ({100 * c['accepted'] / c['labelled']:.0f}%) |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
