"""Report for the wider panel of the held-out precision study.

The outcomes are those of the amendment of 19 November 2026 in
docs/prereg/heldout-precision.md, "a wider panel": per rule and stratum, the
share the majority of twelve primed raters accepts (c or d), the share it
labels c, the same per model (majority of its three), and for three unprimed
raters the share their majority labels c or d, and c alone, beside the
decoys'. Agreement is Fleiss' kappa over the twelve and between the four
model majorities.

Usage: uv run python scripts/heldout_panel_report.py --labels DIR [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heldout_report import (
    DEFAULT_RULES,
    ROOT,
    RULES,
    fleiss,
    parse_labels,
    wilson,
)

MODELS = {
    "Opus 5.5": ("rater1", "rater2", "rater3"),
    "Sonnet 5.5": ("rater4", "rater5", "rater6"),
    "Haiku 5.5": ("rater7", "rater8", "rater9"),
    "Fable 5.2": ("rater10", "rater11", "rater12"),
}
PRIMED = tuple(r for group in MODELS.values() for r in group)
UNPRIMED = ("blind1", "blind2", "blind3")


def load(folder: Path, names) -> dict[str, dict[int, dict]]:
    return {r: parse_labels(json.loads((folder / f"{r}.json").read_text())) for r in names}


def majority(labels: list[str | None], accept: set[str]) -> bool:
    """More than half of the raters gave a label in ``accept``; a missing label counts against."""
    return sum(1 for x in labels if x in accept) * 2 > len(labels)


def share(flags: list[bool]) -> dict:
    k, n = sum(flags), len(flags)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": k / n if n else None, "lo": lo, "hi": hi}


def item_votes(item: dict, labels: dict[str, dict[int, dict]], names) -> list[str | None]:
    return [labels[r].get(item["i"], {}).get("label") for r in names]


def analyse(sample: list[dict], primed: dict, unprimed: dict) -> dict:
    res: dict = {"strata": {}, "counts": {}}
    for r in (*PRIMED, *UNPRIMED):
        lab = primed.get(r) or unprimed.get(r) or {}
        res["counts"][r] = Counter(v["label"] or "missing" for v in lab.values())
    for stratum in ("S1", "S2"):
        items = [it for it in sample if it["stratum"] == stratum]
        groups = {"real": [it for it in items if not it["decoy"]], "decoy": [it for it in items if it["decoy"]]}
        rows = {}
        keys = [(rule, "real") for rule in RULES] + [("all decoys", "decoy")]
        for rule, kind in keys:
            its = [it for it in groups[kind] if kind == "decoy" or it["rule"] == rule]
            if not its:
                continue
            v12 = [item_votes(it, primed, PRIMED) for it in its]
            vu = [item_votes(it, unprimed, UNPRIMED) for it in its]
            row = {
                "n": len(its),
                "acc12": share([majority(v, {"c", "d"}) for v in v12]),
                "c12": share([majority(v, {"c"}) for v in v12]),
                "models": {m: share([majority(item_votes(it, primed, names), {"c", "d"}) for it in its])
                           for m, names in MODELS.items()},
                "models_c": {m: share([majority(item_votes(it, primed, names), {"c"}) for it in its])
                             for m, names in MODELS.items()},
                "u_acc": share([majority(v, {"c", "d"}) for v in vu]),
                "u_c": share([majority(v, {"c"}) for v in vu]),
            }
            full = [v for v in v12 if all(x is not None for x in v)]
            row["kappa12"] = fleiss([[sum(1 for x in v if x in ("c", "d")), sum(1 for x in v if x == "w")]
                                     for v in full]) if len(full) > 1 else None
            rows[rule] = row
        real = groups["real"]
        v12 = [item_votes(it, primed, PRIMED) for it in real]
        full = [v for v in v12 if all(x is not None for x in v)]
        model_maj = [[majority(item_votes(it, primed, names), {"c", "d"}) for names in MODELS.values()]
                     for it in real]
        res["strata"][stratum] = {
            "rows": rows,
            "kappa12_cdw": fleiss([[sum(1 for x in v if x == c) for c in "cdw"] for v in full]),
            "kappa12_acc": fleiss([[sum(1 for x in v if x in ("c", "d")), sum(1 for x in v if x == "w")]
                                   for v in full]),
            "kappa_models": fleiss([[sum(m), len(m) - sum(m)] for m in model_maj]),
            "n_complete": len(full), "n_real": len(real),
            "default_acc12": share([majority(item_votes(it, primed, PRIMED), {"c", "d"})
                                    for it in real if it["rule"] in DEFAULT_RULES]),
            "default_c12": share([majority(item_votes(it, primed, PRIMED), {"c"})
                                  for it in real if it["rule"] in DEFAULT_RULES]),
            "default_u_c": share([majority(item_votes(it, unprimed, UNPRIMED), {"c"})
                                  for it in real if it["rule"] in DEFAULT_RULES]),
        }
    return res


def f(s: dict) -> str:
    if not s["n"]:
        return "–"
    return f"{s['k']}/{s['n']} ({s['p']:.0%}; {s['lo']:.0%}–{s['hi']:.0%})"


def p(s: dict) -> str:
    return "–" if not s["n"] else f"{s['p']:.0%}"


def k(x) -> str:
    return "–" if x is None else f"{x:.2f}"


def render(res: dict) -> str:
    out = ["# Held-out precision: twelve-rater panel and unprimed raters", ""]
    out += ["Label counts per rater:", "", "| Rater | c | d | w | missing |", "| --- | --- | --- | --- | --- |"]
    for r, c in res["counts"].items():
        out.append(f"| {r} | {c.get('c', 0)} | {c.get('d', 0)} | {c.get('w', 0)} | {c.get('missing', 0)} |")
    for stratum, st in res["strata"].items():
        kappas = (f"Fleiss' kappa over twelve primed raters: c/d/w {k(st['kappa12_cdw'])}, accepted "
                  f"{k(st['kappa12_acc'])} ({st['n_complete']} of {st['n_real']} findings with all twelve "
                  f"labels). Between the four model majorities (accepted): {k(st['kappa_models'])}.")
        pooled = (f"Default rules together: accepted by the twelve {f(st['default_acc12'])}; labelled c by "
                  f"the twelve {f(st['default_c12'])}; labelled c by the unprimed raters {f(st['default_u_c'])}.")
        head = ("| Rule | Accepted, 12 | c, 12 | Opus | Sonnet | Haiku | Fable | Unprimed c or d | Unprimed c "
                "| kappa, 12 |")
        out += ["", f"## {stratum}", "", kappas, "", pooled, "", head,
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for rule, row in st["rows"].items():
            m = row["models"]
            out.append(f"| {rule} | {f(row['acc12'])} | {f(row['c12'])} | {p(m['Opus 5.5'])} | "
                       f"{p(m['Sonnet 5.5'])} | {p(m['Haiku 5.5'])} | {p(m['Fable 5.2'])} | {f(row['u_acc'])} | "
                       f"{f(row['u_c'])} | {k(row['kappa12'])} |")
        out += ["", "Share labelled c by each model's majority:", "",
                "| Rule | Opus | Sonnet | Haiku | Fable |", "| --- | --- | --- | --- | --- |"]
        for rule, row in st["rows"].items():
            m = row["models_c"]
            out.append(f"| {rule} | {p(m['Opus 5.5'])} | {p(m['Sonnet 5.5'])} | {p(m['Haiku 5.5'])} | "
                       f"{p(m['Fable 5.2'])} |")
    return "\n".join(out) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels", type=Path, default=Path("/home/claude/heldout-batches/labels"))
    ap.add_argument("--sample", type=Path, default=ROOT / "eval/heldout/sample.jsonl")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    sample = [json.loads(x) for x in args.sample.read_text().splitlines()]
    text = render(analyse(sample, load(args.labels, PRIMED), load(args.labels, UNPRIMED)))
    if args.out:
        args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
