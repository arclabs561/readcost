"""The pre-registered test of repetition against reader judgements.

    python scripts/eval_repetition_prereg.py verify
    python scripts/eval_repetition_prereg.py extract NAME ROOT OUTDIR [--jobs J]
    python scripts/eval_repetition_prereg.py report OUTDIR [--resamples N]

docs/prereg/repetition.md fixes every choice made here: the two measures,
the four datasets and their samples, the outcomes, the controls, the
model, Holm's correction over the eight tests, the smallest effect that
counts and the decision rules. This script implements that text and adds
nothing to the pre-registered part; whatever else it prints is under
"Exploratory, not pre-registered".

`verify` checks that the measurement code is the code the pre-registration
names (SHA-256 of each file) and fails otherwise. `extract` writes one
record per eligible text, with features from `dataset_matrix.features` and
no text (a SHA-256 instead). `report` runs the tests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import dataset_matrix as dm  # noqa: E402

# ------------------------------------------------------- pre-registered part

MEASUREMENT_SHA256 = {
    "src/readcost/patterns.py": "f8fe7ef76b93b447760c6c563e907e9a84cbc0c9f65093c9ad72a4a9ace4728a",
    "scripts/dataset_matrix.py": "744b1b39efce6213ec0c14f3caed013579803778bbcefb36a4654eba0ff9625b",
    "scripts/human_signals.py": "eae332b59c09677d9ea12c0c762259e8416b0f763287705e9363c235663a8e03",
    "src/readcost/readtime.py": "d8484e6fc9564cf27a5ac4c24ffebf89d5166e3cc371b568b8255ff7cc7e8a3a",
}

MIN_WORDS = 50
MIN_TEXTS = 30
SMALLEST = 0.05
ALPHA = 0.05
RESAMPLES = 2000

# M1 and M2: keys of the record's "patterns" dict (dataset_matrix.pattern_measures).
MEASURES = {"M1": ("given_rate", "share of content words already used"),
            "M2": ("restatement", "restatements per 100 words")}

DATASETS = {
    "D1": dict(name="helpsteer", label="HelpSteer v1, coherence", fmt="markdown", outcome="coherence",
               sign=-1, writer="models"),
    "D2": dict(name="helpsteer3_code", label="HelpSteer3 preference, code domain", fmt="markdown",
               outcome="preference", sign=-1, writer="models, technical"),
    "D3": dict(name="stackexchange", label="Stack Exchange answers, four technical sites", fmt="text",
               outcome="pm_score", sign=-1, writer="people, technical"),
    "D4": dict(name="ellipse", label="ELLIPSE learner essays, cohesion", fmt="text", outcome="cohesion",
               sign=-1, writer="people"),
}

SE_SITES = ("softwareengineering.stackexchange.com", "unix.stackexchange.com", "serverfault.com",
            "superuser.com")
CAP_D1 = 12000
CAP_D2_PAIRS = 6000
CAP_D3_QUESTIONS = 1000

CLAIMS = (
    ("The discovery replicates on new model text", ("D1",)),
    ("Repetition predicts reader judgements of technical text", ("D2", "D3")),
    ("Repetition predicts reader judgements of human-written text", ("D3", "D4")),
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify(root: Path = ROOT) -> list[str]:
    """Files whose SHA-256 differs from the pre-registered value."""
    bad = []
    for rel, want in MEASUREMENT_SHA256.items():
        got = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        if got != want:
            bad.append(f"{rel}: {got} (pre-registered {want})")
    return bad


# ------------------------------------------------------------------ prose

class _HTMLProse(HTMLParser):
    """Plain prose from a Stack Exchange answer: code and quotes removed, paragraphs kept."""

    SKIP = {"pre", "code", "blockquote"}
    BLOCK = {"p", "div", "li", "ul", "ol", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
             "table", "tr", "td", "th", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_startendtag(self, tag, attrs):
        if tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_prose(html: str) -> str:
    p = _HTMLProse()
    p.feed(html or "")
    p.close()
    paras = [" ".join(x.split()) for x in re.split(r"\n\s*\n", "".join(p.parts))]
    return "\n\n".join(x for x in paras if x)


def prose_words(text: str, fmt: str) -> int:
    """Whitespace-separated tokens of the prose the measures see."""
    return len((dm.strip_code(text) if fmt == "markdown" else text).split())


# ---------------------------------------------------------------- loaders
#
# Each returns items with id, group, text, outcomes and pointer, after
# eligibility step 1 and the sampling of step 2.

def _parquet_rows(path: Path, columns: list[str] | None = None) -> list[dict]:
    import pyarrow.parquet as pq
    return pq.read_table(path, columns=columns).to_pylist()


def load_helpsteer(root: Path) -> list[dict]:
    hs2 = set()
    for split in ("train", "validation"):
        for r in _parquet_rows(root / "helpsteer2" / f"{split}.parquet", ["response"]):
            hs2.add(sha(r["response"] or ""))
    items = []
    for split in ("train", "validation"):
        for i, r in enumerate(_parquet_rows(root / "helpsteer" / f"{split}.parquet")):
            text = r["response"] or ""
            if sha(text) in hs2 or prose_words(text, "markdown") < MIN_WORDS:
                continue
            items.append({"id": f"{split}:{i}", "group": sha(r["prompt"] or "")[:16], "text": text,
                          "pointer": {"split": split, "row": i},
                          "outcomes": {k: float(r[k]) for k in ("coherence", "helpfulness", "correctness",
                                                                "complexity", "verbosity")}})
    return dm._sample_groups(items, CAP_D1, seed=0)


def load_helpsteer3_code(root: Path) -> list[dict]:
    pairs = []
    for split in ("train", "validation"):
        rows = _parquet_rows(root / "helpsteer3" / f"{split}.parquet",
                             ["domain", "response1", "response2", "overall_preference"])
        for i, r in enumerate(rows):
            if r["domain"] != "code":
                continue
            a, b = r["response1"] or "", r["response2"] or ""
            if a == b or min(prose_words(a, "markdown"), prose_words(b, "markdown")) < MIN_WORDS:
                continue
            pairs.append((split, i, a, b, float(r["overall_preference"])))
    keep = sorted(random.Random(0).sample(range(len(pairs)), min(CAP_D2_PAIRS, len(pairs))))
    items = []
    for k in keep:
        split, i, a, b, pref = pairs[k]
        group = f"{split}:{i}"
        # overall_preference < 0 means response 1 is better; each text gets its own preference.
        for side, text, own in (("1", a, -pref), ("2", b, pref)):
            items.append({"id": f"{group}:{side}", "group": group, "text": text,
                          "pointer": {"split": split, "row": i, "response": int(side)},
                          "outcomes": {"preference": own}})
    return items


def load_stackexchange(root: Path) -> list[dict]:
    items = []
    for site in SE_SITES:
        questions = []
        for r in _parquet_rows(root / "stackexchange" / f"{site}.parquet", ["qid", "answers"]):
            answers = []
            for a in r["answers"] or []:
                text = html_prose(a.get("text") or "")
                if prose_words(text, "text") >= MIN_WORDS:
                    answers.append((a, text))
            if len(answers) >= 2:
                questions.append((r["qid"], answers))
        keep = sorted(random.Random(0).sample(range(len(questions)), min(CAP_D3_QUESTIONS, len(questions))))
        for k in keep:
            qid, answers = questions[k]
            for a, text in answers:
                items.append({"id": f"{site}:{a['answer_id']}", "group": f"{site}:{qid}", "text": text,
                              "pointer": {"site": site, "qid": qid, "answer_id": a["answer_id"]},
                              "outcomes": {"pm_score": float(a["pm_score"]),
                                           "accepted": float(bool(a.get("selected")))},
                              "site": site})
    return items


ELLIPSE_SCORES = ("Overall", "Cohesion", "Syntax", "Vocabulary", "Phraseology", "Grammar", "Conventions")


def load_ellipse(root: Path) -> list[dict]:
    path = root / "ellipse" / "ELLIPSE_Final_github_train.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    items = []
    for i, r in enumerate(rows):
        text = (r.get("full_text") or "").replace("\r\n", "\n")
        if prose_words(text, "text") < MIN_WORDS or not (r.get("Cohesion") or "").strip():
            continue
        items.append({"id": r.get("text_id_kaggle") or str(i), "group": r["prompt"], "text": text,
                      "pointer": {"row": i + 2, "text_id_kaggle": r.get("text_id_kaggle")},
                      "outcomes": {k.lower(): float(r[k]) for k in ELLIPSE_SCORES if (r.get(k) or "").strip()}})
    return items


LOADERS = {"helpsteer": load_helpsteer, "helpsteer3_code": load_helpsteer3_code,
           "stackexchange": load_stackexchange, "ellipse": load_ellipse}
FMT = {spec["name"]: spec["fmt"] for spec in DATASETS.values()}


def _work(args):
    name, item = args
    try:
        rec = {"dataset": name, "id": item["id"], "group": item["group"], "pointer": item["pointer"],
               "sha256": sha(item["text"]), "outcomes": item["outcomes"]}
        if "site" in item:
            rec["site"] = item["site"]
        rec.update(dm.features(item["text"], FMT[name]))
        return rec
    except Exception as e:  # one bad row must not stop the run; errors are counted and printed
        return {"dataset": name, "id": item.get("id"), "error": repr(e)}


def extract(name: str, root: Path, outdir: Path, jobs: int = 1) -> Path:
    items = LOADERS[name](root)
    work = [(name, it) for it in items]
    if jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(jobs, initializer=dm._init) as pool:
            records = pool.map(_work, work, chunksize=16)
    else:
        records = [_work(w) for w in work]
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{name}.jsonl"
    bad = [r for r in records if "error" in r]
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            if "error" not in r:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"{name}: {len(records) - len(bad)} records, {len(bad)} errors -> {out}", file=sys.stderr)
    for r in bad[:5]:
        print("  error:", r["id"], r["error"], file=sys.stderr)
    return out


# ------------------------------------------------------------- statistics

def _num(v) -> float:
    return float("nan") if v is None else float(v)


def controls(rows: list[dict]) -> np.ndarray:
    return np.array([[math.log(max(r["words"], 1)), _num(r["mean_word_len"]), _num(r["mean_zipf"])]
                     for r in rows])


def demean(values: np.ndarray, groups: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    _, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    out = values.copy() if values.ndim == 2 else values[:, None].copy()
    for j in range(out.shape[1]):
        out[:, j] -= (np.bincount(inverse, weights=out[:, j]) / counts)[inverse]
    return out if values.ndim == 2 else out[:, 0]


def residual(y: np.ndarray, C: np.ndarray) -> np.ndarray:
    C1 = np.column_stack([np.ones(len(y)), C])
    beta, *_ = np.linalg.lstsq(C1, y, rcond=None)
    return y - C1 @ beta


def _prepare(y, x, C, groups):
    """Steps 1 and 2 of the model, after dropping undefined values and groups with fewer than two texts."""
    ok = np.isfinite(y) & np.isfinite(x) & np.isfinite(C).all(axis=1)
    y, x, C, groups = y[ok], x[ok], C[ok], groups[ok]
    labels, counts = np.unique(groups, return_counts=True)
    keep = np.isin(groups, labels[counts >= 2])
    y, x, C, groups = y[keep], x[keep], C[keep], groups[keep]
    return demean(y, groups), demean(x, groups), demean(C, groups), groups


def _slope(yd, xd, Cd):
    ry, rx = residual(yd, Cd), residual(xd, Cd)
    if ry.std() == 0 or rx.std() == 0:
        return float("nan"), ry, rx
    ry, rx = ry / ry.std(), rx / rx.std()
    return float((rx @ ry) / (rx @ rx)), ry, rx


def cluster_se(ry: np.ndarray, rx: np.ndarray, beta: float, groups: np.ndarray) -> float:
    """CR1 standard error of the slope of ry on rx, clustered by group."""
    _, inverse = np.unique(groups, return_inverse=True)
    G = int(inverse.max()) + 1
    scores = np.bincount(inverse, weights=rx * (ry - beta * rx), minlength=G)
    return float(math.sqrt(G / (G - 1) * float(scores @ scores)) / float(rx @ rx))


def bootstrap(stat, groups: np.ndarray, resamples: int, seed: int = 0) -> tuple[float, float]:
    _, inverse = np.unique(groups, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    members = np.split(order, np.flatnonzero(np.diff(inverse[order])) + 1)
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


def test(y, x, C, groups, resamples: int = RESAMPLES) -> dict:
    """The pre-registered model: partial r given controls within groups, cluster-robust one-sided p."""
    from scipy import stats
    yd, xd, Cd, g = _prepare(np.asarray(y, float), np.asarray(x, float), np.asarray(C, float), np.asarray(groups))
    G = len(np.unique(g))
    res = {"n": int(len(yd)), "groups": G, "r": float("nan"), "se": float("nan"), "p": 1.0,
           "ci": (float("nan"), float("nan")), "ran": False}
    if len(yd) < MIN_TEXTS or G < 2:
        return res
    r, ry, rx = _slope(yd, xd, Cd)
    if r != r:
        return res
    se = cluster_se(ry, rx, r, g)
    res.update(r=r, se=se, ran=True, df=G - 1,
               p=float(stats.t.sf(r / se, G - 1)) if se > 0 else (0.0 if r > 0 else 1.0),
               two_sided=(r - stats.t.ppf(0.975, G - 1) * se, r + stats.t.ppf(0.975, G - 1) * se))
    if resamples:
        res["ci"] = bootstrap(lambda k: _slope(yd[k], xd[k], Cd[k])[0], g, resamples)
    return res


def holm(pvalues: list[float]) -> list[float]:
    """Holm's step-down adjusted p-values, in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [1.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def label(res: dict, p_holm: float) -> str:
    if not res["ran"]:
        return "not run"
    if p_holm < ALPHA and res["r"] >= SMALLEST:
        return "pass"
    if res["r"] + 1.645 * res["se"] < SMALLEST:
        return "below the smallest effect"
    return "inconclusive"


# ----------------------------------------------------------------- report

def load_records(outdir: Path) -> dict[str, list[dict]]:
    out = {}
    for spec in DATASETS.values():
        p = Path(outdir) / f"{spec['name']}.jsonl"
        if p.exists():
            out[spec["name"]] = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
                                 if line.strip()]
    return out


def _xy(rows, outcome, sign, getter):
    y = np.array([sign * _num(r["outcomes"].get(outcome)) for r in rows])
    x = np.array([_num(getter(r)) for r in rows])
    return y, x, controls(rows), np.array([str(r["group"]) for r in rows])


def preregistered(records: dict[str, list[dict]], resamples: int = RESAMPLES) -> list[dict]:
    tests = []
    for dkey, spec in DATASETS.items():
        rows = records.get(spec["name"], [])
        for mkey, (field, _desc) in MEASURES.items():
            if rows:
                res = test(*_xy(rows, spec["outcome"], spec["sign"], lambda r, f=field: r["patterns"].get(f)),
                           resamples=resamples)
            else:
                res = {"n": 0, "groups": 0, "r": float("nan"), "se": float("nan"), "p": 1.0,
                       "ci": (float("nan"), float("nan")), "ran": False}
            tests.append({"dataset": dkey, "measure": mkey, **res})
    for t, ph in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = ph
        t["label"] = label(t, ph)
        lo, hi = t.get("two_sided", (float("nan"), float("nan")))
        t["opposite"] = bool(t["ran"] and hi < 0)
    return tests


def claims(tests: list[dict]) -> list[tuple[str, bool, str]]:
    m1 = {t["dataset"]: t for t in tests if t["measure"] == "M1"}
    out = []
    for text, need in CLAIMS:
        holds = all(m1[d]["label"] == "pass" for d in need)
        detail = ", ".join(f"{d} {m1[d]['label']}" for d in need)
        out.append((text, holds, detail))
    return out


def _f(v, fmt="+.3f"):
    return "" if v != v else format(v, fmt)


def _p(v):
    return "" if v != v else (f"{v:.2g}" if v >= 1e-4 else f"{v:.1e}")


def render(records: dict[str, list[dict]], tests: list[dict], resamples: int) -> str:
    lines = ["## Pre-registered tests (docs/prereg/repetition.md)", "",
             "Partial r of the measure with the outcome signed toward worse, within groups, with log words, "
             "mean word length and mean Zipf frequency held. One-sided p from cluster-robust (CR1) standard "
             "errors by group; Holm's correction over all eight tests. Bootstrap: 95% percentile interval over "
             f"groups, {resamples} resamples.", "",
             "| Test | Dataset | Measure | Texts | Groups | r | SE | Bootstrap 95% | p | p, Holm | Label |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for t in tests:
        spec, (field, desc) = DATASETS[t["dataset"]], MEASURES[t["measure"]]
        lo, hi = t["ci"]
        boot = "" if lo != lo else f"{lo:+.3f} to {hi:+.3f}"
        lines.append(f"| {t['dataset']}{t['measure']} | {spec['label']} | {t['measure']}: {desc} | {t['n']:,} | "
                     f"{t['groups']:,} | {_f(t['r'])} | {_f(t['se'], '.3f')} | {boot} | {_p(t['p'])} | "
                     f"{_p(t['p_holm'])} | {t['label']} |")
    opposite = [f"{t['dataset']}{t['measure']}" for t in tests if t["opposite"]]
    lines += ["", "Opposite direction with the two-sided 95% interval excluding zero: "
              + (", ".join(opposite) if opposite else "none") + ".", "", "### Claims (decided by M1)", ""]
    for text, holds, detail in claims(tests):
        lines.append(f"- {text}: **{'holds' if holds else 'does not hold'}** ({detail}).")
    lines += ["", "### Samples", ""]
    for spec in DATASETS.values():
        rows = records.get(spec["name"], [])
        if rows:
            words = np.array([r["words"] for r in rows])
            lines.append(f"- {spec['label']}: {len(rows):,} records in {len({r['group'] for r in rows}):,} groups, "
                         f"median {int(np.median(words))} words; written by {spec['writer']}.")
        else:
            lines.append(f"- {spec['label']}: no records.")
    lines += ["", exploratory(records)]
    return "\n".join(lines) + "\n"


# ---------------------------------------------- exploratory, not pre-registered

EXPLORATORY_MEASURES = {
    "given_rate": ("share of content words already used", lambda r: r["patterns"].get("given_rate"), 1),
    "restatement": ("restatements per 100 words", lambda r: r["patterns"].get("restatement"), 1),
    "adjacent_overlap": ("overlap of neighbouring sentences", lambda r: r["patterns"].get("adjacent_overlap"), 1),
    "gzip_ratio": ("gzip ratio of the first 150 words", lambda r: r["patterns"].get("gzip_ratio"), 1),
    "mtld": ("MTLD, sign flipped", lambda r: r["metrics"].get("mtld"), -1),
    "points": ("readcost weighted findings per 100 words", lambda r: r.get("points_per100"), 1),
}
EXPLORATORY_OUTCOMES = {
    "helpsteer": [("helpfulness", -1), ("correctness", -1), ("verbosity", +1)],
    "helpsteer3_code": [("preference", -1)],
    "stackexchange": [("pm_score", -1), ("accepted", -1)],
    "ellipse": [("cohesion", -1), ("overall", -1), ("vocabulary", -1), ("phraseology", -1)],
}


def exploratory(records: dict[str, list[dict]]) -> str:
    lines = ["## Exploratory, not pre-registered", "",
             "The same model with no correction and no bootstrap; r ± 1.96 SE. Read as leads only.", ""]
    for spec in DATASETS.values():
        rows = records.get(spec["name"], [])
        if not rows:
            continue
        subsets = [("all", rows)]
        if spec["name"] == "stackexchange":
            subsets += [(s, [r for r in rows if r.get("site") == s]) for s in SE_SITES]
        outcomes = EXPLORATORY_OUTCOMES[spec["name"]]
        lines += [f"### {spec['label']}", "",
                  "| Subset | Measure | " + " | ".join(f"{o} ({'+' if w > 0 else '-'})" for o, w in outcomes) + " |",
                  "| --- | --- | " + " | ".join("---" for _ in outcomes) + " |"]
        for sname, sub in subsets:
            for mname, (desc, get, flip) in EXPLORATORY_MEASURES.items():
                if sname != "all" and mname not in ("given_rate", "restatement"):
                    continue
                cells = []
                for o, worse in outcomes:
                    y, x, C, g = _xy(sub, o, worse, get)
                    res = test(y, flip * x, C, g, resamples=0)
                    cells.append("" if not res["ran"] else
                                 f"{res['r']:+.3f} ({res['r'] - 1.96 * res['se']:+.3f}, {res['r'] + 1.96 * res['se']:+.3f})")
                lines.append(f"| {sname} | {desc} | " + " | ".join(cells) + " |")
        lines.append("")
    lines.append("A sign after each outcome is the direction treated as worse: (-) means a lower value is worse.")
    return "\n".join(lines)


# ------------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    e = sub.add_parser("extract")
    e.add_argument("name", choices=sorted(LOADERS))
    e.add_argument("root", type=Path)
    e.add_argument("outdir", type=Path)
    e.add_argument("--jobs", type=int, default=1)
    r = sub.add_parser("report")
    r.add_argument("outdir", type=Path)
    r.add_argument("--resamples", type=int, default=RESAMPLES)
    r.add_argument("--json", type=Path)
    args = p.parse_args(argv)
    if args.cmd == "verify":
        bad = verify()
        for line in bad:
            print("changed:", line, file=sys.stderr)
        print("measurement code matches the pre-registration" if not bad else "measurement code differs",
              file=sys.stderr)
        return 1 if bad else 0
    if args.cmd == "extract":
        extract(args.name, args.root, args.outdir, args.jobs)
        return 0
    records = load_records(args.outdir)
    tests = preregistered(records, args.resamples)
    sys.stdout.write(render(records, tests, args.resamples))
    if args.json:
        args.json.write_text(json.dumps(tests, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
