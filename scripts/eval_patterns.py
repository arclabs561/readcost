"""Discourse patterns and redundancy: do they mark model text, and do they track readers?

    python scripts/eval_patterns.py hape   ref/patterns/hape           [--texts 300]
    python scripts/eval_patterns.py hc3    ref/patterns/hc3.parquet    [--texts 500]
    python scripts/eval_patterns.py lamp   ref/patterns/creativity_eval/Writing_Alignment/LAMP/LAMP-train-val-test.json
    python scripts/eval_patterns.py arena  ref/patterns/creativity_eval/WritingRewards/WQ-benchmark-data/wq_lmarena.json
    python scripts/eval_patterns.py arena55 ref/patterns/arena55.parquet [--texts 1500]
    python scripts/eval_patterns.py rt     ref/rt/texts.jsonl
    python scripts/eval_patterns.py emtec  ref/patterns/emtec

Each part answers one of two questions and says which. The parts ``hape``
and ``hc3`` ask whether a measure differs between people and models writing
to the same prompt ("marks model text"). The others ask whether it tracks
something readers did, with text length, word length and word frequency
held constant ("tracks readers"), and put readcost's construction findings
through the same test. A measure that only does the first is of no use to
readcost, which is not an AI-text detector.

Data, none of it in this repository:

- ``hape``: HAP-E (Reinhart et al. 2025), huggingface.co/datasets/browndw/
  human-ai-parallel-corpus, MIT. A model continues a 500-word human text;
  the human continuation is the pair. The directory holds the Parquet files.
- ``hc3``: HC3 (Guo et al. 2023), Hello-SimpleAI/HC3, CC BY-SA 4.0, the
  ``all`` Parquet file: people's and ChatGPT's (2022) answers to a question.
- ``lamp``: LAMP (Chakrabarty, Laban and Wu 2025), github.com/salesforce/
  creativity_eval, BSD-3-Clause. Professional writers edited paragraphs
  written by GPT-4o, Claude 3.5 Sonnet and Llama 3, labelled each edit
  ("Unnecessary Exposition" among the labels) and scored the paragraph
  before and after.
- ``arena``: the Chatbot Arena part of the same repository's writing-quality
  benchmark (Chakrabarty et al. 2025, "AI-Slop to AI-Polish?"): two models'
  answers to a writing request and the one the user preferred.
- ``arena55``: lmarena-ai/arena-human-preference-55k, Apache-2.0: the same
  kind of vote on any request. One-turn battles with a winner, English prose
  answers of 60 to 600 words.
- ``rt``: the per-text reading times that scripts/reading_time_prep.py
  builds from OneStop Eye Movements and Provo (both CC BY 4.0).
- ``emtec``: EMTeC (Bolliger et al. 2025), osf.io/ajqze: eye movements of
  107 people on texts by three models. ``stimuli.csv`` and
  ``reading_measures_corrected.csv`` in the directory.

Needs numpy; the Parquet parts need pyarrow. Intervals are bootstraps over
prompts, paragraphs, pairs or texts. Nothing here is corrected for the
number of measures tested, so read an interval that just clears zero as a
candidate, not a result.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("human_signals", HERE / "human_signals.py")
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)

from readcost import patterns  # noqa: E402  (human_signals puts src on the path)

RATES = ("contrast", "contrast/not-but", "contrast/comma-not", "contrast/rather-than",
         "contrast/setup-resolution", "triple", "anticipatory-it", "restatement")
MEASURES = ("triple_share", "sentence_cv", "paragraph_cv", "opener_share", "adjacent_overlap",
            "given_rate", "closer_given", "lexical_density", "gzip_ratio")
EXISTING = ("findings", "ms_per_word", "mtld", "idea_density", "words_per_sentence")
NEW = RATES + MEASURES
CONTROLS = ("log_words", "letters", "zipf")
MIN_NONZERO = 15
FENCE = re.compile(r"```.*?```", re.S)


# ---------------------------------------------------------------- features

class Featurizer:
    def __init__(self):
        from readcost.config import Config
        from readcost.engine import Analyzer
        from readcost.readtime import _zipf

        self.analyzer = Analyzer(Config())
        self.zipf, self.unseen = _zipf()

    def __call__(self, text: str, fmt: str = "markdown") -> dict | None:
        """One text's pattern rates per 1,000 words, document measures, readcost's own measures and the controls."""
        from readcost.extract import extract

        paragraphs = [s.text for s in extract(text, "text.md", fmt) if not s.in_list]
        report = patterns.measure(self.analyzer.nlp, paragraphs)
        if report.words < 30:
            return None
        result = self.analyzer.check_text(text, fmt)
        words, letters, zipf = hs.lexical(" ".join(paragraphs), self.zipf, self.unseen)
        row = {"words": report.words, "log_words": float(np.log(report.words)), "letters": letters, "zipf": zipf}
        for key in RATES:
            pattern, _, kind = key.partition("/")
            row[key] = report.per_1000(pattern, kind or None)
        row["triple_share"] = report.count("triple") / report.lists if report.lists else None
        row.update(report.measures)
        row["findings"] = 100.0 * len(result.findings) / max(result.words, 1)
        row["ms_per_word"] = result.reading_ms_per_word
        row["mtld"] = result.metrics.get("mtld")
        row["idea_density"] = result.metrics.get("idea_density")
        row["words_per_sentence"] = report.words / max(report.sentences, 1)
        return row


def column(rows: list[dict], key: str) -> np.ndarray:
    return np.array([np.nan if r.get(key) is None else r[key] for r in rows], dtype=float)


def controls_of(rows: list[dict]) -> np.ndarray:
    return np.column_stack([column(rows, c) for c in CONTROLS])


# -------------------------------------------------------------- statistics

def paired(human: list[dict], model: list[dict], key: str, resamples: int = 2000) -> dict | None:
    """Mean of each side, the mean paired difference with its interval, and how often the model is higher."""
    h, m = column(human, key), column(model, key)
    ok = ~np.isnan(h) & ~np.isnan(m)
    if ok.sum() < 20:
        return None
    h, m = h[ok], m[ok]
    d = m - h
    rng = np.random.default_rng(0)
    boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(resamples)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    differ = d != 0
    return {"n": int(ok.sum()), "human": float(h.mean()), "model": float(m.mean()), "diff": float(d.mean()),
            "ci": (float(lo), float(hi)),
            "model_higher": float((d > 0).sum() / differ.sum()) if differ.any() else float("nan")}


def partial(rows: list[dict], y: np.ndarray, key: str, groups, controls: np.ndarray | None = None,
            resamples: int = 1000) -> dict | None:
    """Spearman's rho of a measure with an outcome, the controls held, with a cluster bootstrap interval."""
    x = column(rows, key)
    Z = controls_of(rows) if controls is None else controls
    ok = ~np.isnan(x) & ~np.isnan(y) & ~np.isnan(Z).any(axis=1)
    if ok.sum() < 30 or (x[ok] != 0).sum() < MIN_NONZERO or np.nanstd(x[ok]) == 0:
        return None     # a pattern found in a handful of texts gives a rho that is one text's doing
    x, yy, Z, g = x[ok], y[ok], Z[ok], np.asarray(groups)[ok]
    rho = hs.partial_spearman(x, yy, Z)
    lo, hi = hs.cluster_bootstrap(lambda k: hs.partial_spearman(x[k], yy[k], Z[k]) if x[k].std() > 0 else float("nan"),
                                  g, resamples)
    return {"n": int(ok.sum()), "nonzero": float((x != 0).mean()), "raw": hs.spearman(x, yy), "rho": rho, "ci": (lo, hi)}


def explained_by_existing(rows: list[dict], key: str) -> float | None:
    """R squared of a new measure regressed on readcost's existing measures and the controls."""
    cols = [column(rows, k) for k in (*EXISTING, *CONTROLS)]
    x = column(rows, key)
    ok = ~np.isnan(x) & ~np.isnan(np.column_stack(cols)).any(axis=1)
    if ok.sum() < 50 or x[ok].std() == 0:
        return None
    return hs.ols(np.column_stack(cols)[ok], x[ok])[1]


def added_r2(rows: list[dict], y: np.ndarray, keys: tuple[str, ...], base: tuple[str, ...]) -> tuple[int, float, float]:
    """R squared of the outcome on ``base`` and on ``base`` plus ``keys``, over rows that have every column."""
    B = np.column_stack([column(rows, k) for k in base])
    K = np.column_stack([column(rows, k) for k in keys])
    ok = ~np.isnan(y) & ~np.isnan(B).any(axis=1) & ~np.isnan(K).any(axis=1)
    if ok.sum() < 50:
        return int(ok.sum()), float("nan"), float("nan")
    return int(ok.sum()), hs.ols(B[ok], y[ok])[1], hs.ols(np.column_stack([B, K])[ok], y[ok])[1]


# ------------------------------------------------------------------ output

def fmt(x: float, digits: int = 2) -> str:
    return "n/a" if x != x else f"{x:+.{digits}f}"


def marks_table(title: str, human: list[dict], model: list[dict]) -> None:
    print(f"\n### {title}\n")
    print("| Measure | Pairs | People | Models | Difference | 95% CI | Model higher |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for key in (*NEW, *EXISTING, "words"):
        r = paired(human, model, key)
        if r is None:
            continue
        print(f"| {key} | {r['n']} | {r['human']:.3g} | {r['model']:.3g} | {fmt(r['diff'], 3)} | "
              f"{fmt(r['ci'][0], 3)} to {fmt(r['ci'][1], 3)} | {100 * r['model_higher']:.0f}% |")


def tracks_table(title: str, rows: list[dict], y: np.ndarray, groups, controls=None, keys=(*NEW, *EXISTING)) -> None:
    print(f"\n### {title}\n")
    print("| Measure | Texts | Nonzero | rho | Partial rho | 95% CI |")
    print("| --- | --- | --- | --- | --- | --- |")
    for key in keys:
        r = partial(rows, y, key, groups, controls)
        if r is None:
            continue
        print(f"| {key} | {r['n']} | {100 * r['nonzero']:.0f}% | {fmt(r['raw'])} | {fmt(r['rho'])} | "
              f"{fmt(r['ci'][0])} to {fmt(r['ci'][1])} |")


def overlap_table(rows: list[dict]) -> None:
    print("\n### Share of each new measure that readcost's existing measures explain\n")
    print("R squared of the measure on findings per 100 words, predicted ms per word, MTLD, idea density, "
          "words per sentence, length, word length and word frequency.\n")
    print("| Measure | R squared |")
    print("| --- | --- |")
    for key in NEW:
        r2 = explained_by_existing(rows, key)
        if r2 is not None:
            print(f"| {key} | {r2:.2f} |")


def added_table(rows: list[dict], y: np.ndarray, label: str) -> None:
    dense = ("contrast", "triple", "anticipatory-it", "restatement", "adjacent_overlap", "given_rate",
             "lexical_density")
    base = CONTROLS
    n, r0, r1 = added_r2(rows, y, ("findings",), base)
    print(f"\nVariance in {label} explained ({n} texts): controls {r0:.3f}; with construction findings {r1:.3f}.")
    n, r0, r1 = added_r2(rows, y, dense, base)
    print(f"With the seven discourse measures that every text has ({n} texts): controls {r0:.3f}; with them {r1:.3f}.")
    n, r0, r1 = added_r2(rows, y, dense, (*base, "findings", "mtld", "idea_density", "words_per_sentence"))
    print(f"Over readcost's existing measures as well ({n} texts): without {r0:.3f}; with them {r1:.3f}.")


# ------------------------------------------------------------------- parts

def _parquet_rows(path: Path, columns: list[str]):
    import pyarrow.parquet as pq

    files = sorted(path.glob("*.parquet")) if path.is_dir() else [path]
    for f in files:
        for batch in pq.ParquetFile(f).iter_batches(batch_size=2000, columns=columns):
            yield from batch.to_pylist()


def part_hape(path: Path, args, feat: Featurizer) -> None:
    by_key: dict[str, dict[str, str]] = defaultdict(dict)
    for r in _parquet_rows(path, ["doc_id", "text"]):
        key, _, source = r["doc_id"].partition("@")
        if source and source != "chunk_1":
            by_key[key][source] = r["text"]
    keys = sorted(k for k, v in by_key.items() if "chunk_2" in v and len(v) > 1)
    random.Random(0).shuffle(keys)
    human_rows: dict[str, list[dict]] = defaultdict(list)
    model_rows: dict[str, list[dict]] = defaultdict(list)
    genres: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    pooled: list[dict] = []
    for key in keys[:args.texts]:
        h = feat(by_key[key]["chunk_2"], "text")
        if h is None:
            continue
        pooled.append(h)
        for source, text in by_key[key].items():
            if source == "chunk_2":
                continue
            m = feat(text, "text")
            if m is None:
                continue
            human_rows[source].append(h)
            model_rows[source].append(m)
            genres[key.split("_")[0]].append((h, m))
            pooled.append(m)
    print("## HAP-E: people and models continuing the same text (marks model text)\n")
    print(f"{min(args.texts, len(keys))} of {len(keys)} source texts, drawn at random; rates are per 1,000 words.")
    for source in sorted(model_rows):
        marks_table(source, human_rows[source], model_rows[source])
    for genre in sorted(genres):
        marks_table(f"genre {genre}, all models", [h for h, _ in genres[genre]], [m for _, m in genres[genre]])
    overlap_table(pooled)


def part_hc3(path: Path, args, feat: Featurizer) -> None:
    rows = [r for r in _parquet_rows(path, ["question", "human_answers", "chatgpt_answers", "source"])
            if r["human_answers"] and r["chatgpt_answers"]
            and len(r["human_answers"][0].split()) >= 60 and len(r["chatgpt_answers"][0].split()) >= 60]
    random.Random(0).shuffle(rows)
    human, model = [], []
    for r in rows[:args.texts]:
        h, m = feat(r["human_answers"][0], "text"), feat(r["chatgpt_answers"][0], "text")
        if h and m:
            human.append(h)
            model.append(m)
    print("## HC3: people's and ChatGPT's (2022) answers to the same question (marks model text)\n")
    print(f"{len(human)} of {len(rows)} questions where both answers have 60 words; rates are per 1,000 words.")
    marks_table("all sources", human, model)


def _sentence_rows(feat: Featurizer, text: str, edits: list[dict]) -> list[dict]:
    """One row per sentence of an edited paragraph: was it edited, cut, and what readcost and the patterns found."""
    spans = []
    for e in edits:
        original = e.get("originalText") or ""
        at = text.find(original) if original.strip() else -1
        if at >= 0:
            spans.append((at, at + len(original), e.get("categorization", ""), not (e.get("editedText") or "").strip()))
    report = patterns.measure(feat.analyzer.nlp, [text])
    out = []
    for s in hs.detect_spans(feat.analyzer, text):
        body = text[s["start"]:s["end"]]
        words, letters, zipf = hs.lexical(body, feat.zipf, feat.unseen)
        if words < 3:
            continue
        touching = [sp for sp in spans if sp[0] < s["end"] and sp[1] > s["start"]]
        row = {"log_words": float(np.log(words)), "letters": letters, "zipf": zipf,
               "edited": float(bool(touching)), "cut": float(any(sp[3] for sp in touching)),
               "redundant": float(any("Exposition" in sp[2] for sp in touching)),
               "findings": float(bool(s["findings"]))}
        for p in patterns.PATTERNS:
            row[p] = float(any(h.pattern == p and h.start < s["end"] and h.end > s["start"] for h in report.hits))
        row["any pattern"] = float(any(row[p] for p in patterns.PATTERNS))
        out.append(row)
    return out


def part_lamp(path: Path, args, feat: Featurizer) -> None:
    data = json.loads(path.read_text())
    if args.texts:
        random.Random(0).shuffle(data)
        data = data[:args.texts]
    rows, score, edited, redundant, groups, sentences, sentence_groups = [], [], [], [], [], [], []
    ids: dict[str, int] = {}
    for d in data:
        text = " ".join((d.get("preedit") or "").split())
        i = ids.setdefault(text, len(ids))   # some paragraphs were edited by more than one writer
        row = feat(text, "text")
        if row is None:
            continue
        edits = d.get("fine_grained_edits") or []
        n = max(len(text.split()), 1)
        rows.append(row)
        try:
            score.append(float(d.get("creativity_z_score_pre") or "nan"))
        except ValueError:
            score.append(float("nan"))
        edited.append(sum(len((e.get("originalText") or "").split()) for e in edits) / n)
        redundant.append(sum(len((e.get("originalText") or "").split()) for e in edits
                             if "Exposition" in (e.get("categorization") or "")) / n)
        groups.append(i)
        sent = _sentence_rows(feat, text, edits)
        sentences.extend(sent)
        sentence_groups.extend([i] * len(sent))
    groups = np.array(groups)
    print("## LAMP: model paragraphs edited and scored by professional writers (tracks readers)\n")
    print(f"{len(rows)} edits of {len(ids)} paragraphs, {len(sentences)} sentences. Every text is model-written, so nothing here "
          "can come from who wrote it. A negative rho with the score, or a positive one with the share of words "
          "edited, means the measure goes with what writers disliked.")
    tracks_table("Writer's score of the paragraph before editing (standardised per writer)", rows,
                 np.array(score), groups)
    tracks_table("Share of the paragraph's words that the writer edited", rows, np.array(edited), groups)
    tracks_table("Share of words edited as unnecessary exposition", rows, np.array(redundant), groups)
    added_table(rows, np.array(score), "the writer's score")
    added_table(rows, np.array(redundant), "the share edited as unnecessary exposition")
    overlap_table(rows)
    print("\n### Sentences: is a flagged sentence edited more often than its length and words predict?\n")
    print("Change in the probability that the writer edited the sentence (percentage points), with the "
          "sentence's log length, word length and word frequency held. Bootstrap over paragraphs.\n")
    print("| Flag | Sentences flagged | Edited at all | 95% CI | Cut outright | 95% CI | Edited as unnecessary exposition | 95% CI |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    Z = np.column_stack([[s[c] for s in sentences] for c in CONTROLS])
    for flag in ("findings", "any pattern", *patterns.PATTERNS):
        x = np.array([s[flag] for s in sentences])
        if x.sum() < 10:
            print(f"| {flag} | {int(x.sum())} | too few | | | | | |")
            continue
        cells = [f"| {flag} | {int(x.sum())} "]
        for outcome in ("edited", "cut", "redundant"):
            y = np.array([s[outcome] for s in sentences])
            c = hs.coefficient(y, x, Z, np.array(sentence_groups), resamples=500)
            cells.append(f"| {fmt(100 * c['coef'], 1)} | {fmt(100 * c['ci'][0], 1)} to {fmt(100 * c['ci'][1], 1)} ")
        print("".join(cells) + "|")
    base = {o: float(np.mean([s[o] for s in sentences])) for o in ("edited", "cut", "redundant")}
    print(f"\nOf all sentences, {100 * base['edited']:.0f}% were edited, {100 * base['cut']:.0f}% cut and "
          f"{100 * base['redundant']:.0f}% edited as unnecessary exposition.")


def _preference(pairs_in, feat: Featurizer, title: str, note: str) -> None:
    diffs, win, groups = [], [], []
    for i, (a, b, first_wins) in enumerate(pairs_in):
        ra, rb = feat(a), feat(b)
        if ra is None or rb is None:
            continue
        diffs.append({k: (None if ra.get(k) is None or rb.get(k) is None else ra[k] - rb[k])
                      for k in (*NEW, *EXISTING, *CONTROLS, "words")})
        win.append(1.0 if first_wins else 0.0)
        groups.append(i)
    print(f"## {title} (tracks readers)\n")
    print(f"{len(diffs)} pairs of model answers to one request. {note} Each measure is the first answer's value "
          "minus the second's; a positive rho means the answer with more of it was preferred. Controls: the "
          "differences in log length, word length and word frequency.")
    y = np.array(win)
    longer = column(diffs, "log_words")
    decided = longer != 0
    print(f"\nThe longer answer was preferred in {100 * ((longer > 0) == (y > 0))[decided].mean():.0f}% of pairs "
          f"(rho of the length difference with preference {fmt(hs.spearman(longer, y))}).")
    tracks_table("Preference for the first answer", diffs, y, np.array(groups))
    added_table(diffs, y, "the preference")


def part_arena(path: Path, args, feat: Featurizer) -> None:
    data = [d for d in json.loads(path.read_text()) if d.get("reference_preference") in ("1", "2")]
    if args.texts:
        random.Random(0).shuffle(data)
        data = data[:args.texts]
    pairs_in = [(d["paragraph1"], d["paragraph2"], d["reference_preference"] == "1") for d in data]
    _preference(pairs_in, feat, "Chatbot Arena writing requests: which answer the user preferred",
                "Every text is model-written.")


def _prose(cell: str) -> str | None:
    try:
        turns = json.loads(cell)
    except (TypeError, ValueError):
        return None
    if not isinstance(turns, list) or len(turns) != 1 or not isinstance(turns[0], str):
        return None
    text = turns[0]
    if FENCE.search(text) or not 60 <= len(text.split()) <= 600:
        return None
    if sum(c.isascii() for c in text) < 0.97 * len(text):
        return None
    return text


def part_arena55(path: Path, args, feat: Featurizer) -> None:
    pairs_in = []
    for r in _parquet_rows(path, ["response_a", "response_b", "winner_model_a", "winner_model_b"]):
        if r["winner_model_a"] + r["winner_model_b"] != 1:
            continue
        a, b = _prose(r["response_a"]), _prose(r["response_b"])
        if a and b:
            pairs_in.append((a, b, r["winner_model_a"] == 1))
    random.Random(0).shuffle(pairs_in)
    total = len(pairs_in)
    _preference(pairs_in[:args.texts], feat, "Chatbot Arena, any request: which answer the user preferred",
                f"Drawn at random from {total} one-turn battles with a winner and two English prose answers of "
                "60 to 600 words without code. Every text is model-written.")


def part_rt(path: Path, args, feat: Featurizer) -> None:
    texts = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    print("## Observed reading time per word, OneStop and Provo (tracks readers)\n")
    print("Texts written by people. A positive rho means more of the measure goes with slower reading per word. "
          "Reading time per word cannot show what padding costs: a padded text can be read quickly per word and "
          "still take longer for the same content.")
    by_corpus: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for t in texts:
        words = [w for w in t["words"] if w]
        row = feat(" ".join(words), "text")
        if row is not None:
            row["rt"] = float(np.mean(t["rt"]))
            by_corpus[t["corpus"]].append((t, row))
    for corpus, items in sorted(by_corpus.items()):
        rows = [r for _, r in items]
        groups = np.array(["/".join(t["id"].split("/")[:2]) for t, _ in items])
        tracks_table(f"{corpus}: ms per word, {len(rows)} texts", rows, column(rows, "rt"), groups)
    levels: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for t, row in by_corpus.get("onestop", []):
        parts = t["id"].split("/")
        if len(parts) == 4:
            levels[(parts[0], parts[1], parts[3])][parts[2].lower()[:3]] = row
    diffs = []
    for versions in levels.values():
        if len(versions) == 2:
            hard, easy = (versions[k] for k in sorted(versions))   # "adv" sorts before "ele"
            diffs.append({k: (None if hard.get(k) is None or easy.get(k) is None else hard[k] - easy[k])
                          for k in (*NEW, *EXISTING, *CONTROLS, "rt")})
    if len(diffs) >= 30:
        Z = np.column_stack([column(diffs, "letters"), column(diffs, "zipf")])
        tracks_table(f"OneStop pairs: advanced minus elementary version, {len(diffs)} paragraphs "
                     "(controls: differences in word length and frequency)", diffs, column(diffs, "rt"),
                     np.arange(len(diffs)), Z)


def _read_table(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        head = f.readline()
        f.seek(0)
        return list(csv.DictReader(f, delimiter="\t" if head.count("\t") > head.count(",") else ","))


def part_emtec(path: Path, args, feat: Featurizer) -> None:
    csv.field_size_limit(10 ** 9)
    stimuli = _read_table(path / "stimuli.csv")
    cols = list(stimuli[0]) if stimuli else []
    text_col = next((c for c in ("gen_seq_trunc", "gen_seq", "text", "generated_text") if c in cols), None)
    keys = [c for c in ("item_id", "model", "decoding_strategy") if c in cols]
    print("## EMTeC: eye movements on model-written texts (tracks readers)\n")
    if text_col is None or len(keys) < 3:
        print(f"stimuli.csv does not have the expected columns; found: {', '.join(cols[:40])}")
        return
    total: dict[tuple, list[float]] = defaultdict(list)
    measure_col = None
    with (path / "reading_measures_corrected.csv").open(newline="", encoding="utf-8", errors="replace") as f:
        head = f.readline()
        f.seek(0)
        reader = csv.DictReader(f, delimiter="\t" if head.count("\t") > head.count(",") else ",")
        measure_col = next((c for c in ("TFT", "total_fixation_time") if c in (reader.fieldnames or [])), None)
        if measure_col is None or any(k not in reader.fieldnames for k in keys):
            print(f"reading measures do not have the expected columns; found: {', '.join((reader.fieldnames or [])[:40])}")
            return
        for r in reader:
            try:
                total[tuple(r[k] for k in keys)].append(float(r[measure_col]))
            except ValueError:
                continue
    rows, groups = [], []
    for s in stimuli:
        times = total.get(tuple(s[k] for k in keys))
        row = feat(s[text_col], "text") if times else None
        if row is not None:
            row["rt"] = float(np.mean(times))
            rows.append(row)
            groups.append(s["item_id"])
    print(f"{len(rows)} texts by three models under five decoding strategies; mean total fixation time per word "
          f"({measure_col}), a skipped word counting as 0 ms. Every text is model-written. Bootstrap over prompts.")
    tracks_table("ms per word", rows, column(rows, "rt"), np.array(groups))
    added_table(rows, column(rows, "rt"), "ms per word")


PARTS = {"hape": part_hape, "hc3": part_hc3, "lamp": part_lamp, "arena": part_arena, "arena55": part_arena55,
         "rt": part_rt, "emtec": part_emtec}
DEFAULT_TEXTS = {"hape": 300, "hc3": 500, "lamp": 0, "arena": 0, "arena55": 1500, "rt": 0, "emtec": 0}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("part", choices=sorted(PARTS))
    ap.add_argument("path", type=Path)
    ap.add_argument("--texts", type=int, default=None, help="how many prompts, paragraphs or pairs to draw (0: all)")
    args = ap.parse_args(argv)
    if args.texts is None:
        args.texts = DEFAULT_TEXTS[args.part]
    PARTS[args.part](args.path, args, Featurizer())
    return 0


if __name__ == "__main__":
    sys.exit(main())
