"""Analyse the records that dataset_matrix.py writes, one dataset at a time.

    python scripts/dataset_matrix_report.py RECORDS_DIR [--out OUTDIR] [--resamples N]
    python scripts/dataset_matrix_report.py RECORDS_DIR --derived DERIVED_DIR

For each dataset and each outcome, the association of each readcost measure
with the outcome after length (log words), mean word length and mean Zipf
frequency are held constant. Where several texts answer one prompt or
summarise one article, the comparison is within that group (group means are
removed first). The association is a partial correlation, signed so that a
positive value means the measure goes with the outcome that is worse for the
reader ("worse" in DATASETS); outcomes with no worse direction are printed
with their raw sign. Intervals are percentile bootstraps over groups.

Datasets are reported one by one and never blended. Rated outcomes
("readers dislike it") and reading times ("it slows readers") are kept in
separate tables. The one pooled test is a leave-one-dataset-out check of a
combined score: weights for the rule rates are fitted on every dataset of a
family but one, and the score is tested on the one left out, so no score is
fitted and tested on the same data. readcost's own weighted findings, which
nothing here fits, are tested on every dataset alongside it.

Revision corpora: among pairs whose text before the edit has a finding, how
often the edit removes one, for the target intent (clarity, fluency,
readability, concision) against the others, raw and with edit size and
length held. Scarecrow also gets a word-level test: are words inside a
finding marked by more annotators than their length and frequency predict.

--derived writes the publishable form: the records without any text, a
manifest with each file's SHA-256 and licence, and the dataset card.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dataset_matrix import DATASETS  # noqa: E402

DEFAULT_RULES = ("stacked-nouns", "long-dependency", "inanimate-subject", "reduced-object-relative",
                 "hyphen-compound", "inline-list")
OPT_IN_RULES = ("long-sentence", "nominalization", "participial-clause", "center-embedding", "undefined-acronym")
METRICS = ("mean_dep_z", "mtld", "idea_density", "center_embedding_mean", "reading_ms_per_word")
MIN_FLAGGED = 15   # texts (or pairs) that must have the measure, and that must not, for a row


# ------------------------------------------------------------------ loading

def load(records_dir: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for p in sorted(Path(records_dir).glob("*.jsonl")):
        if p.name.endswith(".words.jsonl"):
            continue
        rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = [r for r in rows if "error" not in r]
        if rows:
            out[rows[0]["dataset"]] = rows
    return out


def _num(x) -> float:
    return float("nan") if x is None else float(x)


def controls(rows: list[dict]) -> np.ndarray:
    return np.array([[math.log(max(r["words"], 1)), _num(r["mean_word_len"]), _num(r["mean_zipf"])] for r in rows])


def measures(rows: list[dict]) -> dict[str, np.ndarray]:
    """Each readcost measure as a column."""
    out = {"weighted findings, default rules": np.array([_num(r["points_per100"]) for r in rows]),
           "any default finding": np.array([float(any(r["counts"].get(k, 0) for k in DEFAULT_RULES)) for r in rows])}
    for k in DEFAULT_RULES + OPT_IN_RULES:
        out[k] = np.array([_num(r["rates"].get(k)) for r in rows])
    for k in METRICS:
        out[k] = np.array([_num(r["metrics"].get(k)) for r in rows])
    return out


# --------------------------------------------------------------- statistics

def demean(values: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Remove group means, when any group has more than one row; otherwise return as is."""
    values = np.asarray(values, dtype=float)
    labels, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    if counts.max() <= 1:
        return values
    out = values.copy()
    if out.ndim == 1:
        out = out[:, None]
    for j in range(out.shape[1]):
        sums = np.bincount(inverse, weights=out[:, j])
        out[:, j] = out[:, j] - (sums / counts)[inverse]
    return out[:, 0] if values.ndim == 1 else out


def residual(y: np.ndarray, C: np.ndarray) -> np.ndarray:
    C1 = np.column_stack([np.ones(len(y)), C])
    beta, *_ = np.linalg.lstsq(C1, y, rcond=None)
    return y - C1 @ beta


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 5 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def partial_r(y, x, C) -> float:
    return _corr(residual(y, C), residual(x, C))


def _members(groups: np.ndarray) -> list[np.ndarray]:
    _, inverse = np.unique(groups, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    bounds = np.flatnonzero(np.diff(inverse[order])) + 1
    return np.split(order, bounds)


def bootstrap(stat, groups: np.ndarray, resamples: int, seed: int = 0) -> tuple[float, float]:
    members = _members(groups)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(resamples):
        idx = np.concatenate([members[k] for k in rng.integers(0, len(members), len(members))])
        v = stat(idx)
        if v == v:
            vals.append(v)
    if len(vals) < resamples / 2:
        return float("nan"), float("nan")
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def association(y, x, C, groups, resamples: int, within: bool = False, continuous: bool = False) -> dict:
    """Partial r of x with y given C, with a bootstrap over groups.

    With ``within``, group means are removed first, so the comparison is
    between texts of the same group (answers to one prompt, summaries of one
    article). Otherwise groups only keep related texts together in the
    bootstrap.
    """
    ok = np.isfinite(y) & np.isfinite(x) & np.isfinite(C).all(axis=1)
    y, x, C, groups = y[ok], x[ok], C[ok], groups[ok]
    flagged = int((x != 0).sum())
    res = {"n": int(len(y)), "with": flagged, "r": float("nan"), "ci": (float("nan"), float("nan")),
           "raw": _corr(y, x) if len(y) else float("nan")}
    if continuous:
        if len(y) < 2 * MIN_FLAGGED:
            return res
    elif flagged < MIN_FLAGGED or len(y) - flagged < MIN_FLAGGED:
        return res
    if within:
        yd, xd, Cd = demean(y, groups), demean(x, groups), demean(C, groups)
    else:
        yd, xd, Cd = y, x, C
    res["r"] = partial_r(yd, xd, Cd)
    res["ci"] = bootstrap(lambda k: partial_r(yd[k], xd[k], Cd[k]), groups, resamples)
    return res


# -------------------------------------------------------------- text tables

def _fmt(v: float, signed: bool = True) -> str:
    if v != v:
        return ""
    return f"{v:+.2f}" if signed else f"{v:.2f}"


def _cell(a: dict) -> str:
    if a["r"] != a["r"]:
        return ""
    lo, hi = a["ci"]
    mark = "*" if (lo == lo and (lo > 0 or hi < 0)) else ""
    return f"{a['r']:+.2f} ({lo:+.2f}, {hi:+.2f}){mark}"


def text_dataset(name: str, rows: list[dict], resamples: int) -> tuple[list[str], list[dict]]:
    spec = DATASETS[name]
    groups = np.array([str(r["group"]) for r in rows])
    C = controls(rows)
    meas = measures(rows)
    outcomes = list(spec["direction"])
    lines = [f"### {name}", "", f"{spec['signal']}. {spec['source']}; licence: {spec['licence']}.", ""]
    words = np.array([r["words"] for r in rows])
    any_flag = meas["any default finding"]
    lines.append(f"{len(rows):,} texts in {len(set(groups)):,} groups; median {int(np.median(words))} words; "
                 f"{100 * any_flag.mean():.0f}% have a default-rule finding; weighted findings per 100 words "
                 f"{np.nanmean(meas['weighted findings, default rules']):.2f}.")
    lines.append("")
    header = "| Measure | texts with it | " + " | ".join(
        f"{o}{'' if spec['direction'][o] else ' (raw sign)'}" for o in outcomes) + " |"
    lines += [header, "| --- | --- | " + " | ".join("---" for _ in outcomes) + " |"]
    table = []
    for mname, x in meas.items():
        cells, n_with = [], None
        for o in outcomes:
            y = np.array([_num(r["outcomes"].get(o)) for r in rows])
            sign = spec["direction"][o] or 1
            a = association(sign * y, x, C, groups, resamples, spec.get("within", False), mname in METRICS)
            n_with = a["with"] if mname not in METRICS else a["n"]
            cells.append(_cell(a))
            table.append({"dataset": name, "family": spec["family"], "outcome": o, "measure": mname,
                          "primary": o == spec["primary"], "direction": spec["direction"][o], "n": a["n"],
                          "with": a["with"], "r": a["r"], "lo": a["ci"][0], "hi": a["ci"][1], "raw_r": sign * a["raw"]})
        if any(cells):
            lines.append(f"| {mname} | {n_with:,} | " + " | ".join(cells) + " |")
    # The primary outcome without controls, to show what length and words carry.
    y = np.array([_num(r["outcomes"].get(spec["primary"])) for r in rows]) * (spec["direction"][spec["primary"]] or 1)
    raw = [t for t in table if t["primary"] and t["measure"] == "weighted findings, default rules"][0]["raw_r"]
    ok = np.isfinite(y) & np.isfinite(C).all(axis=1)
    lines += ["", f"Primary outcome {spec['primary']}: weighted findings without controls r = {_fmt(raw)}; "
              f"log words alone r = {_fmt(_corr(y[ok], C[ok, 0]))}; mean Zipf alone r = "
              f"{_fmt(_corr(y[ok], C[ok, 2]))} (signed toward worse)."]
    return lines, table


# ------------------------------------------------------------ revision pairs

def _pts(f: dict) -> float:
    p = f["points_per100"]
    return 0.0 if p != p or p is None else p * f["checked_words"] / 100.0


def revision_dataset(name: str, rows: list[dict], resamples: int) -> tuple[list[str], list[dict]]:
    spec = DATASETS[name]
    groups = np.array([str(r["group"]) for r in rows])
    target = np.array([r["target"] for r in rows], dtype=float)
    size = np.array([r["edit_size"] for r in rows])
    blen = np.array([math.log(max(r["before"]["words"], 1)) for r in rows])
    lines = [f"### {name}", "", f"{spec['signal']}. {spec['source']}; licence: {spec['licence']}. "
             f"Target intent: {spec['target']}; others: {spec['other']}.", "",
             f"{len(rows):,} pairs, {int(target.sum()):,} with the target intent; median edit size "
             f"{np.median(size):.2f} (share of words changed).", "",
             "| Findings before the edit | pairs | target: removed | others: removed | difference | "
             "difference, edit size and length held |",
             "| --- | --- | --- | --- | --- | --- |"]
    table = []
    preds = {"weighted findings, default rules": (lambda f: _pts(f))}
    for k in DEFAULT_RULES + OPT_IN_RULES:
        preds[k] = (lambda f, k=k: float(f["counts"].get(k, 0)))
    for pname, get in preds.items():
        before = np.array([get(r["before"]) for r in rows])
        after = np.array([get(r["after"]) for r in rows])
        has = before > 0
        if has.sum() < MIN_FLAGGED or target[has].sum() < 5 or (1 - target[has]).sum() < 5:
            continue
        removed = (after < before).astype(float)
        t, g, s, bl, rm = target[has], groups[has], size[has], blen[has], removed[has]

        def diff(k, t=t, rm=rm):
            tk = t[k]
            if tk.min() == tk.max():
                return float("nan")
            return float(rm[k][tk == 1].mean() - rm[k][tk == 0].mean())

        def adj(k, t=t, rm=rm, s=s, bl=bl):
            X = np.column_stack([np.ones(len(k)), t[k], s[k], bl[k]])
            if t[k].min() == t[k].max():
                return float("nan")
            beta, *_ = np.linalg.lstsq(X, rm[k], rcond=None)
            return float(beta[1])

        allk = np.arange(len(t))
        d, a = diff(allk), adj(allk)
        dci, aci = bootstrap(diff, g, resamples), bootstrap(adj, g, resamples)
        lines.append(f"| {pname} | {int(has.sum()):,} | {100 * rm[t == 1].mean():.0f}% of {int(t.sum())} | "
                     f"{100 * rm[t == 0].mean():.0f}% of {int((1 - t).sum())} | {100 * d:+.0f} pts "
                     f"({100 * dci[0]:+.0f}, {100 * dci[1]:+.0f}) | {100 * a:+.0f} pts ({100 * aci[0]:+.0f}, "
                     f"{100 * aci[1]:+.0f}) |")
        table.append({"dataset": name, "family": "revision", "outcome": "removed", "measure": pname,
                      "primary": pname.startswith("weighted"), "direction": 0, "n": int(has.sum()),
                      "with": int(t.sum()), "r": a, "lo": aci[0], "hi": aci[1], "raw_r": d})
    # The other direction: an edit can also add findings to a clean text.
    bpts = np.array([_pts(r["before"]) for r in rows])
    apts = np.array([_pts(r["after"]) for r in rows])
    clean = bpts == 0
    if clean.sum() and target[clean].sum() and (1 - target[clean]).sum():
        added_t = float((apts[clean & (target == 1)] > 0).mean())
        added_o = float((apts[clean & (target == 0)] > 0).mean())
        lines += ["", f"Pairs with no finding before the edit that have one after it: target {100 * added_t:.0f}% "
                  f"of {int(target[clean].sum())}, others {100 * added_o:.0f}% of {int((1 - target[clean]).sum())}."]
    # Net change in weighted findings per 100 words over all pairs.
    delta = np.array([_num(r["after"]["points_per100"]) - _num(r["before"]["points_per100"]) for r in rows])
    ok = np.isfinite(delta)
    lines += ["", f"Change in weighted findings per 100 words, all pairs: target {np.mean(delta[ok & (target == 1)]):+.2f}, "
              f"others {np.mean(delta[ok & (target == 0)]):+.2f}. Words per text, before to after: target "
              f"{np.mean([r['before']['words'] for r, t in zip(rows, target) if t]):.0f} to "
              f"{np.mean([r['after']['words'] for r, t in zip(rows, target) if t]):.0f}."]
    return lines, table


# ----------------------------------------------------------- word-level spans

def scarecrow_words(rows: list[dict], resamples: int) -> list[str]:
    words = [(i, w) for i, r in enumerate(rows) for w in r.get("words_table", [])]
    if not words:
        return []
    groups = np.array([i for i, _ in words])
    C = np.array([[w["len"], w["zipf"] if w["zipf"] is not None else np.nan] for _, w in words], dtype=float)
    inside = np.array([float(bool(w["inside"])) for _, w in words])
    lines = ["", "Word level: share of annotators who marked the word, words inside a default-rule finding "
             "against the rest of the same paragraph, word length and frequency held; bootstrap over paragraphs.", "",
             "| Category | words inside | mean share outside | difference, percentage points | 95% CI |",
             "| --- | --- | --- | --- | --- |"]
    for cat in ("redundant", "jargon", "incoherent", "grammar", "off_prompt"):
        y = np.array([w["marked"].get(cat, 0.0) for _, w in words])
        ok = np.isfinite(C).all(axis=1)
        yd, xd, Cd = demean(y[ok], groups[ok]), demean(inside[ok], groups[ok]), demean(C[ok], groups[ok])

        def coef(k):
            X = np.column_stack([np.ones(len(k)), xd[k], Cd[k]])
            beta, *_ = np.linalg.lstsq(X, yd[k], rcond=None)
            return float(beta[1])

        b = coef(np.arange(len(yd)))
        lo, hi = bootstrap(coef, groups[ok], resamples)
        lines.append(f"| {cat} | {int(inside[ok].sum()):,} | {100 * y[ok][inside[ok] == 0].mean():.1f}% | "
                     f"{100 * b:+.1f} | {100 * lo:+.1f} to {100 * hi:+.1f} |")
    return lines


# --------------------------------------------------- leave one dataset out

def _prepared(name: str, rows: list[dict]):
    spec = DATASETS[name]
    o = spec["primary"]
    y = np.array([_num(r["outcomes"].get(o)) for r in rows]) * spec["direction"][o]
    X = np.array([[_num(r["rates"].get(k)) for k in DEFAULT_RULES + OPT_IN_RULES] for r in rows])
    fixed = np.array([_num(r["points_per100"]) for r in rows])
    C = controls(rows)
    g = np.array([str(r["group"]) for r in rows])
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1) & np.isfinite(C).all(axis=1) & np.isfinite(fixed)
    y, X, C, g, fixed = y[ok], X[ok], C[ok], g[ok], fixed[ok]
    if spec.get("within"):
        yd, Xd, Cd, fd = demean(y, g), demean(X, g), demean(C, g), demean(fixed, g)
    else:
        yd, Xd, Cd, fd = y, X, C, fixed
    ry = residual(yd, Cd)
    RX = np.column_stack([residual(Xd[:, j], Cd) for j in range(X.shape[1])])

    def z(v):
        s = v.std(axis=0)
        return np.where(s > 0, v / np.where(s > 0, s, 1), 0.0)

    return {"y": z(ry), "X": z(RX), "g": g, "fixed": residual(fd, Cd)}


def lodo(data: dict[str, list[dict]], family: str, resamples: int, ridge: float = 1.0) -> list[str]:
    names = [n for n in data if DATASETS[n]["family"] == family and DATASETS[n]["direction"].get(DATASETS[n]["primary"])]
    if len(names) < 3:
        return [f"Fewer than three {family} datasets; no leave-one-out test."]
    prep = {n: _prepared(n, data[n]) for n in names}
    lines = ["| Left out | texts | fitted score: r | 95% CI | readcost weighted findings: r | 95% CI |",
             "| --- | --- | --- | --- | --- | --- |"]
    for held in names:
        train = [prep[n] for n in names if n != held]
        k = train[0]["X"].shape[1]
        A, b = ridge * np.eye(k), np.zeros(k)
        for t in train:  # each dataset weighs the same, whatever its size
            A += t["X"].T @ t["X"] / len(t["y"])
            b += t["X"].T @ t["y"] / len(t["y"])
        w = np.linalg.solve(A, b)
        h = prep[held]
        score = h["X"] @ w
        r = _corr(score, h["y"])
        ci = bootstrap(lambda i: _corr(score[i], h["y"][i]), h["g"], resamples)
        rf = _corr(h["fixed"], h["y"])
        cif = bootstrap(lambda i: _corr(h["fixed"][i], h["y"][i]), h["g"], resamples)
        lines.append(f"| {held} | {len(h['y']):,} | {_fmt(r)} | {_fmt(ci[0])} to {_fmt(ci[1])} | {_fmt(rf)} | "
                     f"{_fmt(cif[0])} to {_fmt(cif[1])} |")
    return lines


# -------------------------------------------------------------------- main

def report(data: dict[str, list[dict]], resamples: int) -> tuple[str, list[dict]]:
    out = ["# readcost against human signals, dataset by dataset", "",
           "Partial correlations, signed toward the outcome that is worse for the reader, with log length, "
           "mean word length and mean Zipf frequency held; where a dataset has several texts per prompt or "
           "article, group means are removed. * marks an interval "
           f"that excludes zero. Rows need {MIN_FLAGGED} texts with and without the measure.", ""]
    table: list[dict] = []
    for family, title in (("rated", "## Readers dislike it: ratings and complaints"),
                          ("reading", "## It slows readers: reading time"),
                          ("revision", "## Edits by intent")):
        names = [n for n in DATASETS if n in data and DATASETS[n]["family"] == family]
        if not names:
            continue
        out += [title, ""]
        for n in names:
            if family == "revision":
                lines, t = revision_dataset(n, data[n], resamples)
            else:
                lines, t = text_dataset(n, data[n], resamples)
                if n == "scarecrow":
                    lines += scarecrow_words(data[n], resamples)
            out += lines + [""]
            table += t
        if family in ("rated", "reading"):
            out += [f"### Leave one dataset out ({family})", "",
                    "Weights for the eleven rule rates fitted on the other datasets' primary outcomes (ridge, "
                    "each dataset weighted equally, after the controls), tested on the one left out. The "
                    "untuned weighted findings of the default rules are shown on the same texts.", ""]
            out += lodo(data, family, resamples) + [""]
    tests = [t for t in table if t["r"] == t["r"] and t["lo"] == t["lo"]]
    clear = [t for t in tests if t["lo"] > 0 or t["hi"] < 0]
    prim = [t for t in tests if t["primary"] and t["measure"] == "weighted findings, default rules"]
    out += ["## Multiple comparisons", "",
            f"{len(tests)} intervals in all; {len(clear)} exclude zero (about {round(0.05 * len(tests))} would by "
            f"chance if nothing were there, and the tests are not independent). Of the {len(prim)} primary tests "
            f"(weighted findings against each dataset's primary outcome, or removal by target edits), "
            f"{sum(1 for t in prim if t['lo'] > 0 or t['hi'] < 0)} exclude zero.", ""]
    return "\n".join(out), table


def derive(records_dir: Path, out: Path) -> None:
    """The records without text, a manifest and the dataset card."""
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"generator": "scripts/dataset_matrix.py", "files": []}
    for p in sorted(Path(records_dir).glob("*.jsonl")):
        rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = [r for r in rows if "error" not in r]
        if not rows:
            continue
        name = rows[0]["dataset"]
        for r in rows:
            for k in ("text", "before_text", "after_text"):  # never present; guard against a future change
                r.pop(k, None)
        target = out / f"{name}.jsonl"
        with open(target, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        spec = DATASETS[name]
        manifest["files"].append({"file": target.name, "dataset": name, "records": len(rows),
                                  "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                                  "licence": spec["licence"], "source": spec["source"],
                                  "derived_labels": bool(spec.get("derived"))})
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    card = ROOT / "eval" / "derived" / "README.md"
    if card.exists():
        shutil.copy(card, out / "README.md")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("records", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--resamples", type=int, default=1000)
    p.add_argument("--derived", type=Path)
    args = p.parse_args(argv)
    if args.derived:
        derive(args.records, args.derived)
        return 0
    text, table = report(load(args.records), args.resamples)
    print(text)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "summary.md").write_text(text + "\n", encoding="utf-8")
        with open(args.out / "associations.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]) if table else ["dataset"])
            w.writeheader()
            w.writerows(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
