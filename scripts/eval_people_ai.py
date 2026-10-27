"""Compare respected authors with a community baseline, and AI-written text with matched human text.

    PYTHONPATH=src python3 scripts/fetch_people_text.py REF/broad/people
    PYTHONPATH=src python3 scripts/fetch_ai_text.py REF/broad/ai
    PYTHONPATH=src python3 scripts/eval_people_ai.py REF/broad

Scores every item of ``REF/broad/people/manifest.json`` and
``REF/broad/ai/manifest.json`` once with readcost's default settings, as
scripts/eval_broad.py does (cached by content hash in
``REF/broad/results-people-ai/texts.jsonl``), and writes aggregates only (no
text) to ``results-people-ai/summary.json`` and ``summary.md``:

- respected authors against the community baseline, for each kind of text
  (issue or pull request body, review comment, thread comment, forum post):
  medians and a two-sided Mann-Whitney U test over texts; and over units, with
  each respected person and each community repository or forum one unit whose
  rates pool its texts (findings over words), so prolific authors do not
  dominate;
- each generator against its matched human text (RAID: the human text the
  generation continues; MAGE: a human text of the same domain; M4: the human
  text of the same record): per pair the machine value minus the human value,
  the share of pairs where the machine text is lower, and a two-sided Wilcoxon
  signed-rank test;
- agent pull requests against human pull requests of the same repository
  (AIDev and a live GitHub sample), the same paired test.

Words per sentence and mean word length are reported next to every
comparison, since sentence length and vocabulary are confounds. Texts under
25 words (as readcost counts them) are left out, and pairs lose both sides.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from scipy.stats import mannwhitneyu, wilcoxon

from readcost.config import Config
from readcost.engine import Analyzer
from readcost.features import FEATURES

_spec = importlib.util.spec_from_file_location("eval_broad", Path(__file__).with_name("eval_broad.py"))
broad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broad)

SUBS = ("people", "ai")
MIN_WORDS = 25  # words as readcost counts them; a pair is dropped when either side is shorter
HEAD = ("findings_per_1k", "cost_index", "ms_per_word", "words_per_sentence", "mean_word_length", "words")
KINDS = {"people-issue": "issue/PR bodies", "people-review": "review comments",
         "people-comment": "thread comments", "people-forum": "forum posts"}
MGT = {"mgt-raid": "RAID", "mgt-mage": "MAGE", "mgt-m4": "M4"}
AGENT = {"agent-pr": "AIDev v3", "agent-pr-live": "live GitHub sample"}


def paired(rows: list[dict], a_role: str, b_role: str, measures: list[str]) -> list[dict]:
    """``b`` minus ``a`` per pair: medians, median difference, share of pairs where ``b`` is lower, Wilcoxon p."""
    by_pair: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by_pair[r["pair_id"]][r["role"]] = r
    pairs = [(p[a_role], p[b_role]) for p in by_pair.values() if a_role in p and b_role in p]
    out = []
    for m in measures:
        d = [(broad.value(a, m), broad.value(b, m)) for a, b in pairs]
        d = [(x, y) for x, y in d if x is not None and y is not None]
        diffs = [y - x for x, y in d]
        nz = [x for x in diffs if x]
        out.append({"measure": m, "pairs": len(d),
                    f"{a_role}_median": statistics.median(x for x, _ in d) if d else None,
                    f"{b_role}_median": statistics.median(y for _, y in d) if d else None,
                    "median_diff": statistics.median(diffs) if d else None,
                    f"{b_role}_lower": sum(x < 0 for x in diffs) / len(d) if d else None,
                    "p": broad.pvalue(wilcoxon, nz) if len(nz) >= 2 else None})
    return out


def unpaired(a: list[dict], b: list[dict], measures: list[str]) -> list[dict]:
    out = []
    for m in measures:
        va = [v for r in a if (v := broad.value(r, m)) is not None]
        vb = [v for r in b if (v := broad.value(r, m)) is not None]
        out.append({"measure": m, "n_respected": len(va), "n_community": len(vb),
                    "respected": statistics.median(va) if va else None,
                    "community": statistics.median(vb) if vb else None,
                    "p": broad.pvalue(mannwhitneyu, va, vb) if va and vb else None})
    return out


def pool(rows: list[dict], features: list[str]) -> dict:
    """One unit's rates over all its texts: findings and rule counts over total words; medians of the rest."""
    words = sum(r["words"] for r in rows)
    sents = sum(r["sentences"] for r in rows)
    counts: dict[str, int] = defaultdict(int)
    nfind = 0
    for r in rows:
        nfind += round((r["findings_per_1k"] or 0) * r["words"] / 1000)
        for k, v in r["counts"].items():
            counts[k] += v
    ms = [(r["ms_per_word"], r["words"]) for r in rows if r["ms_per_word"] is not None and r["words"]]
    mwl = [(r["mean_word_length"], r["words"]) for r in rows if r["mean_word_length"] is not None and r["words"]]
    return {"texts": len(rows), "words": words, "sentences": sents, "counts": dict(counts),
            "findings_per_1k": 1000 * nfind / words if words else None,
            "cost_index": statistics.median(r["cost_index"] for r in rows),
            "ms_per_word": sum(a * w for a, w in ms) / sum(w for _, w in ms) if sum(w for _, w in ms) else None,
            "words_per_sentence": words / sents if sents else None,
            "mean_word_length": sum(a * w for a, w in mwl) / sum(w for _, w in mwl) if mwl else None}


def unit_of(r: dict, e: dict) -> str:
    if r["source"].startswith("respected:"):
        return r["source"]
    return f"community:{e.get('repo') or e.get('host') or r['source']}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    root: Path = args.root
    out = root / "results-people-ai"
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache_path = out / "texts.jsonl"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            r = json.loads(line)
            cache[(r["id"], r["sha256"])] = r
    analyzer = Analyzer(config=Config())
    features = [f for f in FEATURES if f in analyzer.enabled]
    rows, entry = [], {}
    counts: dict[str, dict] = {}
    for sub in SUBS:
        mf = root / sub / "manifest.json"
        if not mf.exists():
            continue
        entries = json.loads(mf.read_text())["entries"]
        for i, e in enumerate(entries):
            key = (e["id"], e["sha256"])
            r = cache[key] if key in cache else broad.score(analyzer, root, sub, e)
            r |= {k: e[k] for k in ("pair_id", "role", "generator", "agent", "domain") if k in e}
            rows.append(r)
            entry[r["id"]] = e
            c = counts.setdefault(f"{e['category']}/{e['source']}", {"texts": 0, "words": 0, "licence": e["license"]})
            c["texts"] += 1
            c["words"] += r["words"]
            if (i + 1) % 200 == 0:
                print(f"{sub}: {i + 1}/{len(entries)}", file=sys.stderr)
    cache_path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    short = [r["id"] for r in rows if r["words"] < MIN_WORDS]
    rows = [r for r in rows if r["words"] >= MIN_WORDS]
    measures = list(HEAD) + features
    summary: dict = {"readcost": broad.eval_corpus.code_version(), "settings": "Config() defaults",
                     "features": features, "min_words": MIN_WORDS,
                     "left_out_short": len(short), "item_counts": counts, "people": {}, "people_units": {},
                     "people_by_person": {}, "mgt": {}, "mgt_rules": {}, "agents": {}, "agents_rules": {}}

    # ---- respected against community
    ppl = [r for r in rows if r["category"] in KINDS]
    for cat in [*KINDS, "all"]:
        rs = ppl if cat == "all" else [r for r in ppl if r["category"] == cat]
        resp = [r for r in rs if r["source"].startswith("respected:")]
        comm = [r for r in rs if not r["source"].startswith("respected:")]
        if resp and comm:
            summary["people"][cat] = unpaired(resp, comm, measures)
        units: dict[str, list[dict]] = defaultdict(list)
        for r in rs:
            units[unit_of(r, entry[r["id"]])].append(r)
        pooled = {u: pool(v, features) for u, v in units.items()}
        ru = [p for u, p in pooled.items() if u.startswith("respected:")]
        cu = [p for u, p in pooled.items() if not u.startswith("respected:")]
        if ru and cu:
            summary["people_units"][cat] = unpaired(ru, cu, measures)
    by_person: dict[str, list[dict]] = defaultdict(list)
    for r in ppl + [r for r in rows if r["category"] == "people-wiki"]:
        if r["source"].startswith("respected:") or r["category"] == "people-wiki":
            by_person[r["source"]].append(r)
    summary["people_by_person"] = {k: {m: v for m, v in pool(rs, features).items() if m != "counts"}
                                   for k, rs in sorted(by_person.items())}
    comm_all = [r for r in ppl if not r["source"].startswith("respected:")]
    if comm_all:
        summary["people_by_person"]["community (all)"] = {m: v for m, v in pool(comm_all, features).items()
                                                          if m != "counts"}

    # ---- generators against matched human text
    for cat, label in MGT.items():
        rs = [r for r in rows if r["category"] == cat]
        if not rs:
            continue
        gens = sorted({r["generator"] for r in rs if r["role"] == "machine"})
        summary["mgt"][label] = {}
        for g in gens:
            pair_ids = {r["pair_id"] for r in rs if r.get("generator") == g}
            sel = [r for r in rs if r["pair_id"] in pair_ids and (r["role"] == "human" or r["generator"] == g)]
            # RAID shares one human text among generators: pair ids stay unique per generator
            sel = [r | {"pair_id": f"{r['pair_id']}|{g}"} for r in sel]
            summary["mgt"][label][g] = paired(sel, "human", "machine", list(HEAD))
        summary["mgt_rules"][label] = paired(
            [r | {"pair_id": f"{r['pair_id']}|{r.get('generator') if r['role'] == 'machine' else '*'}"}
             for r in rs if r["role"] == "machine"]
            + [r | {"pair_id": f"{r['pair_id']}|{g}"} for r in rs if r["role"] == "human"
               for g in {x["generator"] for x in rs if x["role"] == "machine" and x["pair_id"] == r["pair_id"]}],
            "human", "machine", measures)

    # ---- agent pull requests against human pull requests
    for cat, label in AGENT.items():
        rs = [r for r in rows if r["category"] == cat]
        if not rs:
            continue
        summary["agents"][label] = {}
        for ag in sorted({r["agent"] for r in rs}):
            summary["agents"][label][ag] = paired([r for r in rs if r["agent"] == ag], "human", "agent", list(HEAD))
        summary["agents_rules"][label] = paired(rs, "human", "agent", measures)

    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    write_markdown(out / "summary.md", summary, features)
    print(f"{len(rows)} texts -> {out}", file=sys.stderr)
    return 0


def write_markdown(path: Path, s: dict, features: list[str]) -> None:
    md_table = broad.md_table
    md = ["# People and AI: readcost on community and AI-written text", "",
          (f"readcost {s['readcost']}; Config() defaults. Aggregates only; the text stays under this directory. "
          f"{s['left_out_short']} texts under {s['min_words']} words (as readcost counts them) are left out, "
          "with their pair partners."),
          "", "## Items", ""]
    md += md_table([{"source": k, "texts": v["texts"], "words": v["words"], "licence basis": v["licence"]}
                    for k, v in sorted(s["item_counts"].items())], ["source", "texts", "words", "licence basis"])
    ucols = ["measure", "n_respected", "n_community", "respected", "community", "p"]
    for cat, tab in s["people"].items():
        md += ["", f"## Respected vs community: {KINDS.get(cat, 'all kinds pooled')} (texts, Mann-Whitney U)", ""]
        md += md_table(tab, ucols)
        if cat in s["people_units"]:
            md += ["", "Units (each person, repository or forum pooled):", ""] + md_table(s["people_units"][cat], ucols)
    md += ["", "## Per person and per wiki (pooled over their texts)", ""]
    md += md_table([{"unit": k, **v} for k, v in s["people_by_person"].items()],
                   ["unit", "texts", "words", "findings_per_1k", "cost_index", "ms_per_word",
                    "words_per_sentence", "mean_word_length"])
    pcols = ["measure", "pairs", "human_median", "machine_median", "median_diff", "machine_lower", "p"]
    for label, gens in s["mgt"].items():
        md += ["", f"## {label}: each generator minus its matched human text (Wilcoxon signed-rank)", ""]
        rows = []
        for g, tab in gens.items():
            for r in tab:
                rows.append({"generator": g, **r})
        md += md_table(rows, ["generator"] + pcols, ("machine_lower",))
        md += ["", f"### {label}: all generators pooled, per rule", ""]
        md += md_table(s["mgt_rules"][label], pcols, ("machine_lower",))
    acols = ["measure", "pairs", "human_median", "agent_median", "median_diff", "agent_lower", "p"]
    for label, ags in s["agents"].items():
        md += ["", f"## Agent vs human pull requests, same repository: {label} (Wilcoxon signed-rank)", ""]
        rows = [{"agent": a, **r} for a, tab in ags.items() for r in tab]
        md += md_table(rows, ["agent"] + acols, ("agent_lower",))
        md += ["", f"### {label}: all agents pooled, per rule", ""]
        md += md_table(s["agents_rules"][label], acols, ("agent_lower",))
    md += ["", "Rule abbreviations: " + ", ".join(f"{broad.eval_corpus.ABBREV.get(x, x)} = {x}" for x in features) + "."]
    path.write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    sys.exit(main())
