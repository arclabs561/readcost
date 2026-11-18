"""One record per text for many human-signal datasets, with readcost's features.

    python scripts/dataset_matrix.py extract NAME PATH OUTDIR [--limit N] [--jobs J]
    python scripts/dataset_matrix.py prep-geco ROOT       # ROOT/texts.jsonl from the GECO files
    python scripts/dataset_matrix.py list                 # the datasets and what each answers

Every dataset goes through the same harness, so every text gets the same
record: readcost findings per rule per 100 checked words (default and opt-in
rules), the default rules' weighted findings per 100 words, the document
metrics (MTLD, idea density, embedding depth, mean dependency z, predicted
reading time), length, mean word length, mean Zipf frequency, and the human
outcomes. A revision corpus gives one record per pair, with the same
features for the text before and after the edit and the edit's intent.
`scripts/dataset_matrix_report.py` analyses the records.

The records hold no third-party text: each has a pointer to the row it came
from and the SHA-256 of the text, so the text can be recovered from the
source and checked. docs/datasets.md lists the sources, their licences and
the download commands (the `matrix` jobs in .github/workflows/eval.yml).

Derived labels: two datasets get outcomes that this script computes from
human-written text, not labels the dataset ships. HelpSteer3-Feedback's
complaint shares come from matching each annotator's feedback against the
word lists below; HelpSteer3-Edit's intent comes from matching the editor's
change summary. Both are marked "derived" in DATASETS.
"""

from __future__ import annotations

import argparse
import ast
import csv
import difflib
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

OPT_IN = ("long-sentence", "nominalization", "participial-clause", "center-embedding", "undefined-acronym")
WEIGHTS = {"info": 0.5, "warn": 1.0, "error": 2.0}

# name -> what the dataset is and how to read its outcomes. "direction" says
# which way is worse for the reader: +1 if a higher value is worse, -1 if a
# lower value is worse, 0 if neither (reported, never pooled). "primary" is
# the outcome chosen before seeing any result for the pooled and
# leave-one-dataset-out tests. "within" means several texts answer one
# prompt or summarise one article, so texts are compared within that group.
DATASETS: dict[str, dict] = {
    "helpsteer2": dict(
        kind="text", within=True, family="rated", fmt="markdown", cap=4000, licence="CC-BY-4.0",
        source="nvidia/HelpSteer2 (Hugging Face), train and validation",
        signal="Scale AI annotators rate each response 0 to 4 on five attributes",
        primary="coherence",
        direction={"coherence": -1, "helpfulness": -1, "correctness": -1, "verbosity": +1, "complexity": 0}),
    "helpsteer3_feedback": dict(
        kind="text", within=True, family="rated", fmt="markdown", cap=4000, licence="CC-BY-4.0", derived=True,
        source="nvidia/HelpSteer3 config feedback (Hugging Face); General and STEM domains, English",
        signal="three annotators each write a paragraph about a response; shares that complain "
               "about length, clarity or repetition are matched here",
        primary="complain_any",
        direction={"complain_any": +1, "complain_verbose": +1, "complain_clarity": +1,
                   "complain_repetition": +1, "helpful": -1}),
    "summeval": dict(
        kind="text", within=True, family="rated", fmt="text", cap=None, licence="MIT",
        source="mteb/summeval (Hugging Face), from Yale-LILY/SummEval",
        signal="mean of three expert ratings, 1 to 5, of 16 systems' summaries of 100 CNN/DM articles",
        primary="coherence",
        direction={"coherence": -1, "fluency": -1, "consistency": 0, "relevance": 0}),
    "tldr_axis": dict(
        kind="text", within=True, family="rated", fmt="text", cap=3000, licence="Modified MIT (OpenAI)",
        source="openai/summarize_from_feedback config axis (Hugging Face), TL;DR posts",
        signal="labellers rate summaries of Reddit posts 1 to 7 on overall, accuracy, coverage, coherence",
        primary="coherence",
        direction={"coherence": -1, "overall": -1, "accuracy": 0, "coverage": 0}),
    "cnndm_axis": dict(
        kind="text", within=True, family="rated", fmt="text", cap=3000, licence="Modified MIT (OpenAI)",
        source="openai/summarize_from_feedback config axis (Hugging Face), CNN/DM articles",
        signal="as tldr_axis, for news summaries",
        primary="coherence",
        direction={"coherence": -1, "overall": -1, "accuracy": 0, "coverage": 0}),
    "readmepp": dict(
        kind="text", family="rated", fmt="text", cap=None, licence="research and non-commercial use",
        source="github.com/tareknaous/readme, dataset/en",
        signal="CEFR level 1 to 6 per sentence, rated in context by annotators, 20 domains",
        primary="cefr", direction={"cefr": +1}),
    "scarecrow": dict(
        kind="text", family="rated", fmt="text", cap=None, licence="none stated",
        source="github.com/yao-dou/scarecrow, data/grouped_data.csv",
        signal="10 crowd annotators mark spans of ten error types in model-written paragraphs",
        primary="readability",
        direction={"readability": +1, "redundant": +1, "jargon": +1, "incoherent": +1,
                   "grammar": +1, "off_prompt": 0}),
    "geco": dict(
        kind="text", family="reading", fmt="text", cap=None, licence="free for research with citation",
        source="expsy.ugent.be/downloads/geco, English monolingual reading data",
        signal="14 English readers' eye movements on a whole novel; total reading time per word",
        primary="ms_per_word", direction={"ms_per_word": +1}),
    "onestop": dict(
        kind="text", within=True, family="reading", fmt="text", cap=None, licence="CC-BY-4.0",
        source="OneStop Eye Movements (OSF), via scripts/reading_time_prep.py",
        signal="eye movements of 360 readers on news paragraphs at two levels; dwell time per word",
        primary="ms_per_word", direction={"ms_per_word": +1}),
    "provo": dict(
        kind="text", family="reading", fmt="text", cap=None, licence="CC-BY-4.0",
        source="Provo (OSF), via scripts/reading_time_prep.py",
        signal="84 readers' eye movements on 55 short passages; dwell time per word",
        primary="ms_per_word", direction={"ms_per_word": +1}),
    "iterater": dict(
        kind="revision", family="revision", fmt="text", cap=None, licence="Apache-2.0",
        source="wanyu/IteraTeR_human_sent (Hugging Face)",
        signal="crowd annotators label the intent of each sentence revision in arXiv, Wikipedia "
               "and news drafts",
        target="clarity or fluency", other="coherence, style or meaning-changed"),
    "arxivedits": dict(
        kind="revision", family="revision", fmt="text", cap=None, licence="none stated; arXiv texts",
        source="github.com/chaojiang06/arXivEdits, data/edits",
        signal="annotators label each edit between two arXiv versions of a sentence",
        target="improve readability or simplify", other="grammar, content, format or other language edits"),
    "pararev": dict(
        kind="revision", family="revision", fmt="text", cap=None, licence="CC-BY-NC-SA-4.0",
        source="taln-ls2n/pararev config pararev_annot_subset (Hugging Face)",
        signal="two annotators label the intent of each revised paragraph of an OpenReview paper",
        target="concision", other="rewriting, development or content"),
    "helpsteer3_edit": dict(
        kind="revision", family="revision", fmt="markdown", cap=2000, licence="CC-BY-4.0", derived=True,
        source="nvidia/HelpSteer3 config edit (Hugging Face); General and STEM domains, English",
        signal="annotators edit a model response from others' feedback and summarise the change",
        target="change summary mentions concision or clarity", other="other edits"),
}

# Word lists for the derived labels. Matching is case-insensitive.
VERBOSE = re.compile(r"\b(verbose|verbosity|wordy|wordiness|lengthy|too long|overly long|unnecessarily long|"
                     r"long-winded|rambl\w*|filler|padding|could be (?:more )?(?:concise|shorter|succinct)|"
                     r"(?:unnecessary|irrelevant|extraneous) (?:details?|information|text|content))\b", re.I)
CLARITY = re.compile(r"\b(unclear|confusing|confused|(?:hard|difficult) to (?:read|follow|understand)|ambiguous|"
                     r"awkward\w*|convoluted|not clear|lacks? (?:of )?clarity|jargon|"
                     r"poorly (?:written|worded|structured|organi[sz]ed))\b", re.I)
REPETITION = re.compile(r"\b(repetitive|repetition|repeats|repeated|repeating|redundan\w*)\b", re.I)
HELPFUL = re.compile(r"\bresponse is (not|slightly|partially|mostly|perfectly) helpful", re.I)
HELPFUL_LEVEL = {"not": 0, "slightly": 1, "partially": 2, "mostly": 3, "perfectly": 4}
EDIT_TARGET = re.compile(r"\b(concis\w*|shorten\w*|shorter|verbos\w*|wordy|redundan\w*|repetiti\w*|"
                         r"unnecessary|clarity|clearer|clarif\w*|readab\w*|simplif\w*|streamlin\w*|"
                         r"condens\w*|trimm?\w*|succinct\w*)\b", re.I)

SCARECROW = {"Redundant": "redundant", "Technical_Jargon": "jargon", "Incoherent": "incoherent",
             "Grammar_Usage": "grammar", "Off-prompt": "off_prompt"}
SCARECROW_READABILITY = ("Redundant", "Technical_Jargon", "Incoherent")


# ------------------------------------------------------------------ helpers

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_code(text: str) -> str:
    """Markdown without fenced code blocks and inline code, for the lexical measures."""
    text = re.sub(r"```.*?(```|$)", " ", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", " ", text)


def detokenize(text: str) -> str:
    """Undo the space-separated punctuation of a tokenized corpus."""
    text = re.sub(r"\s+([,.;:!?%)\]}])", r"\1", text)
    text = re.sub(r"([(\[{$])\s+", r"\1", text)
    text = re.sub(r"\s+(n't|'t|'s|'re|'ve|'ll|'d|'m)\b", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _parquets(path: Path, pattern: str = "*.parquet") -> list[dict]:
    import pyarrow.parquet as pq
    rows: list[dict] = []
    for p in sorted(path.glob(pattern)):
        for r in pq.read_table(p).to_pylist():
            r["_file"] = p.name
            rows.append(r)
    return rows


def _sample_groups(rows: list[dict], cap: int | None, seed: int = 0) -> list[dict]:
    """Keep whole groups until about ``cap`` rows, so groups stay intact."""
    if cap is None or len(rows) <= cap:
        return rows
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r)
    keys = list(groups)
    random.Random(seed).shuffle(keys)
    out: list[dict] = []
    for k in keys:
        if len(out) >= cap:
            break
        out.extend(groups[k])
    return out


def _share(feedbacks, pattern) -> float:
    feedbacks = [f for f in feedbacks or [] if f]
    if not feedbacks:
        return float("nan")
    return sum(bool(pattern.search(f)) for f in feedbacks) / len(feedbacks)


def _helpful(feedbacks) -> float:
    levels = []
    for f in feedbacks or []:
        m = HELPFUL.search(f or "")
        if m:
            levels.append(HELPFUL_LEVEL[m.group(1).lower()])
    return sum(levels) / len(levels) if levels else float("nan")


# ------------------------------------------------------------------ loaders
#
# A text loader returns dicts with id, group, text, outcomes and pointer. A
# revision loader returns dicts with id, group, before, after, intents,
# target (bool) and pointer.

def load_helpsteer2(path: Path) -> list[dict]:
    out = []
    for i, r in enumerate(_parquets(path)):
        out.append({"id": f"{r['_file']}:{i}", "group": sha(r["prompt"])[:16], "text": r["response"],
                    "pointer": {"file": r["_file"], "row": i},
                    "outcomes": {k: float(r[k]) for k in ("helpfulness", "correctness", "coherence",
                                                          "complexity", "verbosity")}})
    return out


def _english_prose(r: dict) -> bool:
    return r.get("domain") in ("general", "stem") and (r.get("language") or "english").lower() == "english"


def load_helpsteer3_feedback(path: Path) -> list[dict]:
    out = []
    for i, r in enumerate(_parquets(path)):
        if not _english_prose(r):
            continue
        group = f"{r['_file']}:{i}"
        for side in ("1", "2"):
            fb = list(r.get("feedback" + side) or [])
            outcomes = {"complain_verbose": _share(fb, VERBOSE), "complain_clarity": _share(fb, CLARITY),
                        "complain_repetition": _share(fb, REPETITION), "helpful": _helpful(fb)}
            any_ = [bool(VERBOSE.search(f) or CLARITY.search(f) or REPETITION.search(f)) for f in fb if f]
            outcomes["complain_any"] = sum(any_) / len(any_) if any_ else float("nan")
            out.append({"id": f"{group}:{side}", "group": group, "text": r["response" + side],
                        "pointer": {"file": r["_file"], "row": i, "response": int(side)}, "outcomes": outcomes})
    return out


def load_summeval(path: Path) -> list[dict]:
    out = []
    for r in _parquets(path):
        for k, text in enumerate(r["machine_summaries"]):
            out.append({"id": f"{r['id']}:{k}", "group": r["id"], "text": text,
                        "pointer": {"id": r["id"], "summary": k},
                        "outcomes": {a: float(r[a][k]) for a in ("coherence", "fluency", "consistency", "relevance")}})
    return out


def _load_axis(path: Path, news: bool) -> list[dict]:
    by: dict[tuple, dict] = {}
    for r in _parquets(path):
        info, summ = r["info"], r["summary"]
        if bool(info.get("article")) != news:
            continue
        key = (info["id"], summ["text"])
        row = by.setdefault(key, {"id": f"{info['id']}:{sha(summ['text'])[:12]}", "group": info["id"],
                                  "text": summ["text"], "pointer": {"info_id": info["id"], "policy": summ.get("policy")},
                                  "_axes": {}})
        for a in ("overall", "accuracy", "coverage", "coherence"):
            v = (summ.get("axes") or {}).get(a)
            if v is not None:
                row["_axes"].setdefault(a, []).append(float(v))
    out = []
    for row in by.values():
        axes = row.pop("_axes")
        row["outcomes"] = {a: sum(v) / len(v) for a, v in axes.items() if v}
        if "coherence" in row["outcomes"]:
            out.append(row)
    return out


def load_tldr_axis(path: Path) -> list[dict]:
    return _load_axis(path, news=False)


def load_cnndm_axis(path: Path) -> list[dict]:
    return _load_axis(path, news=True)


def load_readmepp(path: Path) -> list[dict]:
    import openpyxl
    out = []
    for split in ("train", "val", "test"):
        f = path / "dataset" / "en" / f"readme_en_{split}.xlsx"
        if not f.exists():
            continue
        ws = openpyxl.load_workbook(f, read_only=True).active
        rows = ws.iter_rows(values_only=True)
        header = list(next(rows))
        col = {name: header.index(name) for name in ("Domain", "Paragraph", "Sentence", "Rating")}
        for i, r in enumerate(rows):
            if not r or r[col["Sentence"]] in (None, "") or r[col["Rating"]] is None:
                continue
            text = " ".join(str(r[col["Sentence"]]).split())
            out.append({"id": f"{split}:{i}", "group": sha(str(r[col["Paragraph"]]))[:16], "text": text,
                        "pointer": {"file": f.name, "row": i + 1, "domain": r[col["Domain"]]},
                        "outcomes": {"cefr": float(r[col["Rating"]])}})
    return out


def _scarecrow_rows(path: Path) -> list[dict]:
    csv.field_size_limit(10**9)
    with open(path / "data" / "grouped_data.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def scarecrow_coverage(text: str, responses: list) -> tuple[dict, list[dict]]:
    """Per category, the mean over annotators of the share of characters marked.

    Also returns the spans per annotator, as (category, start, end).
    """
    n = max(len(responses), 1)
    shares = {v: 0.0 for v in SCARECROW.values()}
    shares["readability"] = 0.0
    spans = []
    length = max(len(text), 1)
    for ann in responses:
        marked: dict[str, set[int]] = {}
        for s in ann:
            cat, start, end = s[0], int(s[3]), int(s[4])
            spans.append((cat, start, end))
            keys = [SCARECROW[cat]] if cat in SCARECROW else []
            if cat in SCARECROW_READABILITY:
                keys.append("readability")
            for k in keys:
                marked.setdefault(k, set()).update(range(max(start, 0), min(end, len(text))))
        for k, chars in marked.items():
            shares[k] += len(chars) / length / n
    return shares, spans


def load_scarecrow(path: Path) -> list[dict]:
    out = []
    for r in _scarecrow_rows(path):
        responses = ast.literal_eval(r["responses"])
        shares, spans = scarecrow_coverage(r["generation"], responses)
        out.append({"id": r["id"], "group": sha(r["prompt"])[:16], "text": r["generation"],
                    "pointer": {"id": r["id"], "gid": r["gid"], "model": r["model"]},
                    "outcomes": shares, "_spans": spans, "_annotators": len(responses)})
    return out


def _load_rt(path: Path, corpus: str) -> list[dict]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        if t.get("corpus") != corpus or not t["words"]:
            continue
        if corpus == "onestop":  # batch/article/level/paragraph; the two levels share a group
            parts = str(t["id"]).split("/")
            group = "/".join(parts[:2] + parts[3:]) if len(parts) == 4 else t["id"]
        else:
            group = str(t.get("group", t["id"]))
        rt = [float(x) for x in t["rt"]]
        out.append({"id": str(t["id"]), "group": group, "text": " ".join(map(str, t["words"])),
                    "pointer": {"corpus": corpus, "id": t["id"]},
                    "outcomes": {"ms_per_word": sum(rt) / len(rt)}})
    return out


def load_geco(path: Path) -> list[dict]:
    return _load_rt(path, "geco")


def load_onestop(path: Path) -> list[dict]:
    return _load_rt(path, "onestop")


def load_provo(path: Path) -> list[dict]:
    return _load_rt(path, "provo")


def load_iterater(path: Path) -> list[dict]:
    out = []
    for i, r in enumerate(_parquets(path)):
        label = (r.get("labels") or "").strip().lower()
        out.append({"id": f"{r['_file']}:{i}", "group": str(r.get("doc_id")), "before": r["before_sent"],
                    "after": r["after_sent"], "intents": [label], "target": label in ("clarity", "fluency"),
                    "pointer": {"file": r["_file"], "row": i, "doc_id": r.get("doc_id")}})
    return out


def load_arxivedits(path: Path) -> list[dict]:
    out = []
    for split in ("train", "dev", "test"):
        f = path / "data" / "edits" / f"{split}.json"
        if not f.exists():
            continue
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            intents = set()
            for ek, ev in v.items():
                if ek.startswith("edits-combination") and ev:
                    intents.update(str(e.get("intention")) for e in ev.values())
            out.append({"id": f"{split}:{k}", "group": str(v.get("arxiv-id")),
                        "before": detokenize(v["sentence-1"]), "after": detokenize(v["sentence-2"]),
                        "intents": sorted(intents), "target": "Lang-improve-readability-Simplify" in intents,
                        "pointer": {"file": f"{split}.json", "key": k, "arxiv_id": v.get("arxiv-id")}})
    return out


def load_pararev(path: Path) -> list[dict]:
    out = []
    for i, r in enumerate(_parquets(path)):
        labels = []
        for a in ("annot_1", "annot_2"):
            labels += [str(x) for x in ((r.get(a) or {}).get("annotation") or [])]
        out.append({"id": str(r["id_paragraph"]), "group": str(r.get("id_source")), "before": r["parag_1"],
                    "after": r["parag_2"], "intents": sorted(set(labels)),
                    "target": any("concis" in x.lower() for x in labels),
                    "pointer": {"id_paragraph": r["id_paragraph"]}})
    return out


def load_helpsteer3_edit(path: Path) -> list[dict]:
    out = []
    for i, r in enumerate(_parquets(path)):
        if not _english_prose(r):
            continue
        summary = r.get("change_summary") or ""
        out.append({"id": f"{r['_file']}:{i}", "group": f"{r['_file']}:{i}", "before": r["original_response"],
                    "after": r["edited_response"], "intents": ["concision or clarity" if EDIT_TARGET.search(summary)
                                                               else "other"],
                    "target": bool(EDIT_TARGET.search(summary)), "pointer": {"file": r["_file"], "row": i}})
    return out


LOADERS = {name: globals()["load_" + name] for name in DATASETS}


# ----------------------------------------------------------------- features

_STATE: dict = {}


def _init() -> None:
    from readcost import Analyzer, Config
    from readcost.readtime import _zipf
    _STATE["analyzer"] = Analyzer(Config(enable=list(OPT_IN)))
    _STATE["zipf"] = _zipf()


def features(text: str, fmt: str) -> dict:
    """readcost's measures and the lexical controls for one text."""
    if "analyzer" not in _STATE:
        _init()
    from readcost.features import FEATURES
    from human_signals import lexical
    a = _STATE["analyzer"]
    table, floor = _STATE["zipf"]
    res = a.check_text(text, fmt)
    prose = strip_code(text) if fmt == "markdown" else text
    words, word_len, zipf = lexical(prose, table, floor)
    checked = res.words
    counts = {rule: 0 for rule in FEATURES}
    points = 0.0
    for f in res.findings:
        counts[f.feature] = counts.get(f.feature, 0) + 1
        if f.feature in FEATURES and FEATURES[f.feature].default:
            points += WEIGHTS.get(f.severity, 0.0)
    per100 = (lambda n: 100.0 * n / checked) if checked else (lambda n: float("nan"))
    m = res.metrics or {}
    return {
        "words": words, "checked_words": checked, "sentences": res.sentences,
        "words_per_sentence": checked / res.sentences if res.sentences else float("nan"),
        "mean_word_len": word_len, "mean_zipf": zipf,
        "counts": counts, "rates": {k: per100(v) for k, v in counts.items()},
        "points_per100": per100(points),
        "metrics": {"mtld": m.get("mtld"), "idea_density": m.get("idea_density"),
                    "center_embedding_mean": m.get("center_embedding_mean"),
                    "center_embedding_max": m.get("center_embedding_max"),
                    "mean_dep_z": res.mean_dep_z, "reading_ms_per_word": res.reading_ms_per_word},
    }


def detect_word_spans(text: str) -> list[tuple[int, int, str]]:
    """Character spans (start, end, rule) of every finding of a default rule, at every use."""
    if "analyzer" not in _STATE:
        _init()
    from readcost import Analyzer, Config
    from human_signals import detect_spans
    plain = _STATE.setdefault("plain", Analyzer(Config()))
    return [(first, last, rule) for s in detect_spans(plain, text) for rule, _sev, first, last in s["findings"]]


def word_rows(text: str, spans: list, annotators: int, finding_spans: list) -> list[dict]:
    """One row per whitespace word: inside a finding, its length and frequency, and marked shares."""
    table, floor = _STATE["zipf"] if "zipf" in _STATE else (None, None)
    rows = []
    for m in re.finditer(r"\S+", text):
        a, b = m.start(), m.end()
        w = m.group().strip(".,;:!?\"'()[]{}-").lower()
        if not w:
            continue
        inside = sorted({rule for s, e, rule in finding_spans if s < b and a < e})
        marked: dict[str, int] = {}
        for cat, s, e in spans:
            if s < b and a < e and cat in SCARECROW:
                marked[SCARECROW[cat]] = marked.get(SCARECROW[cat], 0) + 1
        rows.append({"inside": inside, "len": len(w), "zipf": table.get(w, floor) if table else None,
                     "marked": {k: v / max(annotators, 1) for k, v in marked.items()}})
    return rows


def _text_record(name: str, spec: dict, item: dict) -> dict:
    rec = {"dataset": name, "kind": "text", "family": spec["family"], "id": item["id"], "group": item["group"],
           "pointer": item["pointer"], "sha256": sha(item["text"]), "licence": spec["licence"],
           "outcomes": item["outcomes"]}
    rec.update(features(item["text"], spec["fmt"]))
    if "_spans" in item:
        rec["words_table"] = word_rows(item["text"], item["_spans"], item["_annotators"],
                                       detect_word_spans(item["text"]))
    return rec


def _revision_record(name: str, spec: dict, item: dict) -> dict:
    b, a = item["before"] or "", item["after"] or ""
    bw, aw = b.split(), a.split()
    return {"dataset": name, "kind": "revision", "family": "revision", "id": item["id"], "group": item["group"],
            "pointer": item["pointer"], "sha256_before": sha(b), "sha256_after": sha(a), "licence": spec["licence"],
            "intents": item["intents"], "target": bool(item["target"]),
            "edit_size": 1.0 - difflib.SequenceMatcher(None, bw, aw, autojunk=False).ratio(),
            "before": features(b, spec["fmt"]), "after": features(a, spec["fmt"])}


def _work(args):
    name, item = args
    spec = DATASETS[name]
    try:
        return (_revision_record if spec["kind"] == "revision" else _text_record)(name, spec, item)
    except Exception as e:  # one bad row must not stop a run of thousands
        return {"dataset": name, "id": item.get("id"), "error": repr(e)}


def extract(name: str, path: Path, outdir: Path, limit: int | None = None, jobs: int = 1) -> Path:
    spec = DATASETS[name]
    items = LOADERS[name](path)
    cap = limit if limit is not None else spec.get("cap")
    items = _sample_groups(items, cap)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{name}.jsonl"
    work = [(name, it) for it in items]
    if jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(jobs, initializer=_init) as pool:
            records = pool.map(_work, work, chunksize=16)
    else:
        records = [_work(w) for w in work]
    bad = [r for r in records if "error" in r]
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            if "error" not in r:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"{name}: {len(records) - len(bad)} records, {len(bad)} errors -> {out}", file=sys.stderr)
    for r in bad[:5]:
        print("  error:", r["id"], r["error"], file=sys.stderr)
    return out


# --------------------------------------------------------------------- GECO

def prep_geco(root: Path) -> Path:
    """Sentence reading times from GECO's English monolingual data.

    Reads ROOT/EnglishMaterial.xlsx (word, word id, sentence id) and
    ROOT/MonolingualReadingData.xlsx (one row per reader and word). The
    total reading time of a skipped word (a "." in the file) counts as 0,
    as in reading_time_prep.py. Writes ROOT/texts.jsonl in that script's
    format, one line per sentence, grouped by the part of the novel.
    """
    import openpyxl

    def sheet_rows(path: Path, need: tuple[str, ...]):
        wb = openpyxl.load_workbook(path, read_only=True)
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            header = [str(h).strip().upper() if h is not None else "" for h in next(it)]
            if all(any(n in h for h in header) for n in need):
                col = {n: next(i for i, h in enumerate(header) if h == n or n in h) for n in need}
                print(f"{path.name}/{ws.title}: columns {header}", file=sys.stderr)
                return col, it
        raise SystemExit(f"{path.name}: no sheet has columns {need}")

    col, it = sheet_rows(root / "EnglishMaterial.xlsx", ("WORD_ID", "WORD", "SENTENCE_ID"))
    word_of: dict[str, str] = {}
    sentence_of: dict[str, str] = {}
    order: list[str] = []
    for r in it:
        wid = r[col["WORD_ID"]]
        if wid is None:
            continue
        wid = str(wid).strip()
        word_of[wid] = str(r[col["WORD"]])
        sentence_of[wid] = str(r[col["SENTENCE_ID"]]).strip()
        order.append(wid)
    col, it = sheet_rows(root / "MonolingualReadingData.xlsx", ("PP_NR", "WORD_ID", "WORD_TOTAL_READING_TIME"))
    total: dict[str, float] = {}
    readers: dict[str, set] = {}
    for r in it:
        wid = r[col["WORD_ID"]]
        if wid is None:
            continue
        wid = str(wid).strip()
        v = r[col["WORD_TOTAL_READING_TIME"]]
        try:
            ms = float(v)
        except (TypeError, ValueError):
            ms = 0.0
        total[wid] = total.get(wid, 0.0) + ms
        readers.setdefault(wid, set()).add(r[col["PP_NR"]])
    sentences: dict[str, dict] = {}
    for wid in order:
        if wid not in total:
            continue
        sid = sentence_of[wid]
        s = sentences.setdefault(sid, {"corpus": "geco", "id": sid, "group": sid.split("-")[0],
                                       "words": [], "rt": [], "readers": 99})
        s["words"].append(word_of[wid])
        s["rt"].append(total[wid] / len(readers[wid]))
        s["readers"] = min(s["readers"], len(readers[wid]))
    out = root / "texts.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for s in sentences.values():
            f.write(json.dumps(s) + "\n")
    print(f"geco: {len(sentences)} sentences -> {out}", file=sys.stderr)
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("name", choices=sorted(DATASETS))
    e.add_argument("path", type=Path)
    e.add_argument("outdir", type=Path)
    e.add_argument("--limit", type=int)
    e.add_argument("--jobs", type=int, default=1)
    g = sub.add_parser("prep-geco")
    g.add_argument("root", type=Path)
    sub.add_parser("list")
    args = p.parse_args(argv)
    if args.cmd == "extract":
        extract(args.name, args.path, args.outdir, args.limit, args.jobs)
    elif args.cmd == "prep-geco":
        prep_geco(args.root)
    else:
        for name, spec in DATASETS.items():
            print(f"{name:20} {spec['family']:9} {spec['licence']:35} {spec['signal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
