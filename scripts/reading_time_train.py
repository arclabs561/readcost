# /// script
# dependencies = ["numpy", "scikit-learn", "spacy>=3.7"]
# ///
"""Train and evaluate readcost's word-level reading-time model (Cekini et al. 2026 design).

    uv run scripts/reading_time_train.py ROOT WORDS_TSV OUT_DIR [--surprisal]

ROOT is the directory scripts/reading_time_prep.py wrote; WORDS_TSV is the
output of scripts/build_word_freq.py before compression. Without
--surprisal the selected model is also written to
src/readcost/data/reading_time_model.json.gz. --surprisal adds SmolLM2-135M
surprisal features (needs torch and transformers) to measure what they add;
on OneStop and Provo they added nothing, so readcost ships the lexical model.

ROOT/texts.jsonl comes from reading_time_prep.py. OneStop articles are split 60/20/20
by article (train/validation/test); Provo is an external test set. Models are
compared by text-level mean absolute error of mean reading time per word
(ms/word), as in the paper. Writes OUT_DIR/report.json and, for the selected
configuration, OUT_DIR/model.json: gradient-boosted trees as plain arrays.
"""
import gzip
import json
import math
import random
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from spacy.lang.en.stop_words import STOP_WORDS

DATA = Path(__file__).resolve().parent.parent / "src/readcost/data/reading_time_model.json.gz"
FEATURES = ["len", "digit", "hyphen", "punct_end", "index", "rel_pos", "zipf", "stop",
            "prev_len", "next_len", "prev_zipf", "next_zipf", "prev_punct", "next_punct"]


def load_zipf(path: Path) -> tuple[dict, float]:
    with open(path) as fh:
        total = int(next(fh).split("\t")[1])
        z = {}
        for line in fh:
            w, k = line.rstrip("\n").split("\t")
            z[w] = math.log10(int(k) / total * 1e9)
    floor = math.log10(10 / total * 1e9)  # below the 20-count cut-off
    return z, floor


def clean(w: str) -> str:
    return re.sub(r"[^a-z']", "", w.lower())


def word_features(words: list[str], zipf: dict, floor: float) -> np.ndarray:
    n = len(words)
    base = []
    for k, w in enumerate(words):
        c = clean(w)
        base.append([len(re.sub(r"[^A-Za-z0-9]", "", w)), float(any(ch.isdigit() for ch in w)), float("-" in w),
                     float(bool(re.search(r"[.,;:!?)\"']$", w))), k, k / max(n - 1, 1),
                     zipf.get(c, floor) if c else floor, float(c in STOP_WORDS)])
    rows = []
    for k in range(n):
        prev = base[k - 1] if k else [0, 0, 0, 0, 0, 0, 7.0, 1]
        nxt = base[k + 1] if k + 1 < n else [0, 0, 0, 1, 0, 0, 7.0, 1]
        rows.append(base[k] + [prev[0], nxt[0], prev[6], nxt[6], prev[3], nxt[3]])
    return np.array(rows, dtype=np.float64)


def word_surprisal(words: list[str], tok, lm) -> list[float]:
    """Sum of subword surprisals (bits) for each word, words joined by spaces."""
    import torch
    text, spans = "", []
    for w in words:
        start = len(text) + (1 if text else 0)
        text = (text + " " + w) if text else w
        spans.append((start, len(text)))
    enc = tok(text, return_offsets_mapping=True, return_tensors="pt")
    ids = enc.input_ids[:, :2048]
    with torch.no_grad():
        logp = torch.log_softmax(lm(ids).logits[0], -1)
    tok_s = [0.0] + [float(-logp[i - 1, ids[0, i]] / math.log(2)) for i in range(1, ids.shape[1])]
    offs = enc.offset_mapping[0].tolist()[: ids.shape[1]]
    out = []
    for a, b in spans:
        out.append(sum(s for (x, y), s in zip(offs, tok_s) if x < b and y > a))
    return out


def text_mae(texts, preds) -> float:
    return float(np.mean([abs(np.mean(p) - np.mean(t["rt"])) for t, p in zip(texts, preds)]))


def tree_predict(spec: dict, X: np.ndarray) -> np.ndarray:
    """The same evaluation as readcost.readtime.predict, for the export check."""
    out = np.full(len(X), spec["init"])
    X = np.asarray(X, dtype=np.float32).astype(np.float64)  # as sklearn compares
    for t in spec["trees"]:
        for k, row in enumerate(X):
            node = 0
            while t["left"][node] != -1:
                node = t["left"][node] if row[t["feature"][node]] <= t["threshold"][node] else t["right"][node]
            out[k] += spec["learning_rate"] * t["value"][node]
    return out


def export(gb: GradientBoostingRegressor, names: list[str]) -> dict:
    trees = []
    for est in gb.estimators_[:, 0]:
        t = est.tree_
        trees.append({"feature": t.feature.tolist(), "threshold": t.threshold.tolist(),
                      "left": t.children_left.tolist(), "right": t.children_right.tolist(),
                      "value": [round(float(v), 6) for v in t.value[:, 0, 0]]})
    return {"features": names, "init": float(gb.init_.constant_[0][0]),
            "learning_rate": gb.learning_rate, "trees": trees}


def main(root: Path, words_tsv: Path, out: Path, use_surprisal: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    texts = [json.loads(x) for x in (root / "texts.jsonl").read_text().splitlines()]
    zipf, floor = load_zipf(words_tsv)
    names = list(FEATURES)
    tok = lm = None
    if use_surprisal:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-135M")
        lm = AutoModelForCausalLM.from_pretrained("HuggingFaceTB/SmolLM2-135M").eval()
        names += ["surprisal", "prev_surprisal"]
    for t in texts:
        X = word_features(t["words"], zipf, floor)
        if use_surprisal:
            s = word_surprisal(t["words"], tok, lm)
            X = np.column_stack([X, s, [0.0] + s[:-1]])
        t["X"] = X
    articles = sorted({t["article"] for t in texts if t["corpus"] == "onestop"})
    random.Random(7).shuffle(articles)
    k1, k2 = int(0.6 * len(articles)), int(0.8 * len(articles))
    split = {a: "train" for a in articles[:k1]} | {a: "val" for a in articles[k1:k2]} | {a: "test" for a in articles[k2:]}
    sets = {s: [t for t in texts if t["corpus"] == "onestop" and split[t["article"]] == s] for s in ("train", "val", "test")}
    sets["provo"] = [t for t in texts if t["corpus"] == "provo"]
    Xtr = np.vstack([t["X"] for t in sets["train"]])
    ytr = np.concatenate([t["rt"] for t in sets["train"]])

    def evaluate(predict) -> dict:
        out = {}
        for s in ("val", "test", "provo"):
            preds = [predict(t["X"]) for t in sets[s]]
            out[s] = round(text_mae(sets[s], preds), 2)
            # Word-level fit, the measure most surprisal studies report.
            p, y = np.concatenate(preds), np.concatenate([t["rt"] for t in sets[s]])
            out[f"{s}_word_r"] = round(float(np.corrcoef(p, y)[0, 1]), 3)
            out[f"{s}_word_rmse"] = round(float(np.sqrt(np.mean((p - y) ** 2))), 1)
            # Mean signed error per text: a level shift between corpora shows here.
            out[f"{s}_bias"] = round(float(np.mean([np.mean(q) - np.mean(t["rt"]) for q, t in zip(preds, sets[s])])), 1)
        return out

    mean_rt = float(ytr.mean())
    report = {"surprisal": use_surprisal, "n_words": {s: int(sum(len(t["rt"]) for t in v)) for s, v in sets.items()},
              "n_texts": {s: len(v) for s, v in sets.items()},
              "observed_ms_per_word": {s: round(float(np.mean([np.mean(t["rt"]) for t in v])), 1) for s, v in sets.items()},
              "baselines": {"train_mean": evaluate(lambda X: np.full(len(X), mean_rt))}}
    lin = Ridge(alpha=1.0).fit(Xtr[:, [0]], ytr)
    report["baselines"]["length_only_ridge"] = evaluate(lambda X: lin.predict(X[:, [0]]))
    ridge = Ridge(alpha=1.0).fit(Xtr, ytr)
    report["baselines"]["ridge_all_features"] = evaluate(ridge.predict)
    best = None
    report["boosting"] = []
    for depth in (3, 4):
        for n in (150, 300):
            for lr in (0.05, 0.1):
                gb = GradientBoostingRegressor(n_estimators=n, max_depth=depth, learning_rate=lr,
                                               subsample=0.8, random_state=0).fit(Xtr, ytr)
                r = {"depth": depth, "trees": n, "lr": lr, **evaluate(gb.predict)}
                report["boosting"].append(r)
                if best is None or r["val"] < best[0]["val"]:
                    best = (r, gb)
    report["selected"] = best[0]
    importance = [round(float(v), 3) for v in best[1].feature_importances_]
    report["importance"] = dict(sorted(zip(names, importance), key=lambda kv: -kv[1]))
    spec = export(best[1], names)
    # The exported arrays must reproduce sklearn exactly (up to the 6-decimal rounding).
    Xval = np.vstack([t["X"] for t in sets["val"]])
    gap = float(np.max(np.abs(tree_predict(spec, Xval) - best[1].predict(Xval))))
    assert gap < 1e-3, f"exported model differs from sklearn by {gap} ms"
    report["export_max_abs_diff_ms"] = gap
    (out / "report.json").write_text(json.dumps(report, indent=1))
    (out / "model.json").write_text(json.dumps(spec))
    if not use_surprisal:
        DATA.write_bytes(gzip.compress(json.dumps(spec).encode(), mtime=0))
    print(json.dumps({k: report[k] for k in ("n_texts", "observed_ms_per_word", "baselines", "selected", "importance")}, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "--surprisal" in sys.argv)
