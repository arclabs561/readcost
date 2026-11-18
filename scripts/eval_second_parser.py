"""Does a second parser or tagger make three rules more precise? Scored on hand-corrected parses.

    python scripts/eval_second_parser.py \\
        --group held-out ref/ud/UD_English-EWT/en_ewt-ud-test.conllu ref/ud/UD_English-GUM/en_gum-ud-test.conllu \\
        --group other ref/ud/UD_English-PUD/*.conllu ref/ud/UD_English-LinES/*.conllu \\
        --second-spacy en_core_web_trf \\
        --biaffine ref/models/biaffine --kniv ref/models/kniv \\
        --rulebench ref/rulebench/rulebench.jsonl --json second_parser.json

The default parser (en_core_web_sm) reads some verbs as nouns and attaches
some clauses to the wrong word, and three rules inherit those errors:
stacked-nouns, reduced-object-relative and long-dependency
(scripts/eval_gold_treebank.py). This script measures what a second model
buys. Each configuration is a parser that the rules run on, and optionally a
filter that drops a finding the second model does not support:

  sm                 en_core_web_sm, readcost's default
  trf                the second spaCy model (--second-spacy) in place of sm
  sm & trf           a finding of sm is kept when the second spaCy model
                     reports the same rule on overlapping words
  sm + NAME pos-verb the tagger NAME must not tag a word of a noun stack as
                     a verb, and must tag the verb of a relative clause as one
  sm + NAME pos      stricter: every word of a stack is a noun; the head and
                     subject of a relative clause are nominals and its verb a
                     verb; the head of a long dependency is a verb
  sm + NAME ud       NAME's own Universal Dependencies tree must hold the
                     construction, by the definitions used on the gold tree
                     (eval_gold_treebank.gold_stacks and the others)
  sm + biaffine, readcost verify_model
                     the tests in readcost/verify.py: pos-verb for
                     stacked-nouns, ud for the other two rules

NAME is one of two ONNX models from Hugging Face:

  biaffine  ghotriw/deberta-v3-xsmall-biaffine-dep-pos-feats-en-ewt-gum-norm
            (MIT). Input: an int64 grid [1, words + 1, 20], one row of
            subword ids per word, each word tokenized alone, padded with 0;
            row 0 is the root and holds only [CLS]. Outputs: arc scores
            [dependent, head], relation scores, part-of-speech scores.
  kniv      dragonscale-ai/kniv-v7-small-en (Apache-2.0), the `plain` graph
            only, for its part-of-speech scores. Input: the subword ids of
            the words joined by spaces, and each word's first subword.

Both were trained on UD English EWT; the first also on GUM. Scoring them on
text they were trained on would flatter them, so pass the treebanks in
groups and read the group that fits: the test splits of EWT and GUM, which
neither model saw in training, and treebanks neither was trained on (PUD,
LinES, ParTUT). The spaCy models were trained on OntoNotes, not on any of
these.

Two references come from the gold annotation, as in eval_gold_treebank.py:
the construction defined on the gold tree, and the same rule run on the gold
tree converted to the parser's label scheme. Precision is the share of
findings that overlap a reference; recall is the share of references that a
finding overlaps. Intervals are percentile bootstrap intervals over
documents (over sentences where a treebank marks no documents); differences
from `sm` are paired: the same resampled documents for both.

The `ud` filter and the gold construction share a definition, so a perfect
UD parser would score 100% precision there by construction. That is the
point of a verifier, and also why the gold-tree-rule columns are reported
beside it.

Wall time is per 1,000 words on the machine that runs this. A filter's time
is the time of the default parser plus the second model on the sentences
with a finding, since nothing else needs a second look.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_gold_treebank as tb  # noqa: E402

RULES = ("stacked-nouns", "reduced-object-relative", "long-dependency")
NOUNS = ("NOUN", "PROPN")
VERBS = ("VERB", "AUX")
NOMINALS = ("NOUN", "PROPN", "PRON", "NUM", "DET")
RELATIVE_PRONOUNS = ("that", "which", "who", "whom")
# Columns of a sentence's counts for one configuration and rule.
FINDINGS, RIGHT, REFS, FOUND, TREE_RIGHT, TREE_REFS, TREE_FOUND = range(7)


# ------------------------------------------------------------------ findings

@dataclass(frozen=True)
class Finding:
    """One finding, with the words of its sentence so that a tagger can be asked about it.

    ``tokens`` index ``words``: the nouns of a stack in order; the head, the
    subject and the verb of a relative clause; the dependent and the head of
    a long dependency.
    """
    rule: str
    start: int
    end: int
    words: tuple[str, ...]
    offsets: tuple[tuple[int, int], ...]
    tokens: tuple[int, ...]

    @property
    def span(self) -> tuple[int, int]:
        return self.start, self.end


def doc_findings(ctx, doc) -> list[Finding]:
    """Findings of the three rules on a parsed text, following the sentence loop of `Analyzer.analyze`."""
    from readcost.features import NOUN_RUN_RULES, detect, misparsed_verb

    out = []
    for sent in doc.sents:
        if len([t for t in sent if t.is_alpha]) < 4:
            continue
        rules = None
        if not any(t.pos_ in VERBS for t in sent):
            if not misparsed_verb(sent):
                continue
            rules = NOUN_RUN_RULES
        found = [(rule, toks) for rule, _sev, _msg, toks in detect(sent, ctx, rules) if rule in RULES and toks]
        if not found:
            continue
        kept = [t for t in sent if not t.is_space]
        index = {t.i: k for k, t in enumerate(kept)}
        words = tuple(t.text for t in kept)
        offsets = tuple((t.idx, t.idx + len(t.text)) for t in kept)
        for rule, toks in found:
            if rule == "stacked-nouns":
                toks = sorted(toks, key=lambda t: t.i)
            out.append(Finding(rule, min(t.idx for t in toks), max(t.idx + len(t.text) for t in toks),
                               words, offsets, tuple(index[t.i] for t in toks)))
    return out


# -------------------------------------------------------------- second models

@dataclass
class Parse:
    """What a second model says about the words of one sentence. ``heads`` is 0-based, -1 for the root."""
    upos: list[str]
    heads: list[int] | None = None
    deprels: list[str] | None = None


class Biaffine:
    """The biaffine parser's ONNX graph: words in, part of speech, heads and relations out.

    The graph takes one int64 grid [batch, words + 1, fix_len]. Each word is
    tokenized alone with the encoder's tokenizer and padded with 0 to
    ``fix_len`` subwords; row 0 stands for the root and holds only [CLS].
    Heads are each word's highest-scoring head, with no tree constraint: the
    filters here read single arcs, not whole trees.
    """

    def __init__(self, directory: Path, session=None, tokenizer=None, file: str = "model.onnx"):
        directory = Path(directory)
        cfg = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        self.fix_len = int(cfg["fix_len"])
        self.pos = {v: k for k, v in cfg["pos_vocab"].items()}
        self.rel = {v: k for k, v in cfg["rel_vocab"].items()}
        # Indices 0 and 1 are <pad> and <bos>; a real word never has them.
        self.first_label = 2
        if tokenizer is None:
            from tokenizers import Tokenizer

            tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
            tokenizer.no_padding()
            tokenizer.no_truncation()
        self.tokenizer = tokenizer
        self.cls = tokenizer.token_to_id("[CLS]")
        self.unk = tokenizer.token_to_id("[UNK]")
        if session is None:
            import onnxruntime as ort

            session = ort.InferenceSession(str(directory / file), providers=["CPUExecutionProvider"])
        self.session = session
        self.input = session.get_inputs()[0].name
        names = [o.name for o in session.get_outputs()]
        # The card gives the order s_arc, s_rel, s_pos, s_feats; use the names when the graph has them.
        self.order = [names.index(n) if n in names else k for k, n in enumerate(("s_arc", "s_rel", "s_pos"))]

    def grid(self, words: list[str]) -> np.ndarray:
        rows = [[self.cls]]
        for w in words:
            ids = self.tokenizer.encode(w, add_special_tokens=False).ids[:self.fix_len]
            rows.append(ids or [self.unk])
        out = np.zeros((1, len(rows), self.fix_len), dtype=np.int64)
        for k, ids in enumerate(rows):
            out[0, k, :len(ids)] = ids
        return out

    def tag(self, words: list[str]) -> Parse:
        outputs = self.session.run(None, {self.input: self.grid(words)})
        arc, rel, pos = (np.asarray(outputs[k], dtype=np.float32)[0] for k in self.order)
        lo = self.first_label
        upos = [self.pos[int(k) + lo] for k in pos[1:, lo:].argmax(-1)]
        arc = arc[1:].copy()                       # rows: words; columns: root, then words
        arc[np.arange(len(words)), np.arange(1, len(words) + 1)] = -np.inf   # no word heads itself
        head_col = arc.argmax(-1)
        deprels = [self.rel[int(rel[d + 1, h, lo:].argmax()) + lo] for d, h in enumerate(head_col)]
        return Parse(upos, [int(h) - 1 for h in head_col], deprels)


class Kniv:
    """The `plain` graph of a kniv v7 model, read for its part-of-speech scores only.

    The words are joined by spaces and tokenized once with special tokens;
    the graph pools each word at its first subword. Its other inputs say
    which sentence each word is in (one sentence here). Text over the
    graph's subword limit is not tagged.
    """

    def __init__(self, directory: Path, session=None, tokenizer=None, file: str = "plain-int8.onnx"):
        directory = Path(directory)
        meta = json.loads((directory / "onnx" / "onnx_meta.json").read_text(encoding="utf-8"))
        self.labels = meta["labels"]["pos"]
        self.max_subwords = int(meta["max_subwords"])
        self.outputs = meta["graphs"]["plain"]["outputs"]
        if tokenizer is None:
            from tokenizers import Tokenizer

            tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
            tokenizer.no_padding()
            tokenizer.no_truncation()
        self.tokenizer = tokenizer
        if session is None:
            import onnxruntime as ort

            session = ort.InferenceSession(str(directory / "onnx" / file), providers=["CPUExecutionProvider"])
        self.session = session
        self.inputs = {i.name: i.type for i in session.get_inputs()}
        names = [o.name for o in session.get_outputs()]
        self.pos_at = names.index("pos") if "pos" in names else self.outputs.index("pos")

    def align(self, words: list[str]) -> tuple[list[int], list[int]]:
        """Subword ids of the joined words, and each word's first subword (-1: none)."""
        starts, at = [], 0
        for w in words:
            starts.append(at)
            at += len(w) + 1
        enc = self.tokenizer.encode(" ".join(words), add_special_tokens=True)
        first = [-1] * len(words)
        for k, (a, b) in enumerate(enc.offsets):
            if b <= a:
                continue  # a special token
            w = bisect.bisect_right(starts, b - 1) - 1
            if first[w] < 0:
                first[w] = k
        return list(enc.ids), first

    def tag(self, words: list[str]) -> Parse | None:
        ids, first = self.align(words)
        if len(ids) > self.max_subwords:
            return None
        first_arr = np.asarray(first, dtype=np.int64)
        n = len(ids)
        end = np.ones(len(first), dtype=np.int64)    # as kniv_v7.runtime.word_ends
        nxt = n - 1
        for k in range(len(first) - 1, -1, -1):
            f = int(first_arr[k])
            if 0 <= f < nxt:
                end[k], nxt = nxt, f
            else:
                end[k] = min(max(f, 0) + 1, n)
        feeds = {"input_ids": np.asarray([ids], dtype=np.int64),
                 "attention_mask": np.ones((1, n), dtype=np.int64),
                 "first_subword": np.maximum(first_arr, 0)[None],
                 "word_end": end[None],
                 "word_mask": (first_arr >= 0)[None],
                 "sent_of_word": np.zeros((1, len(words)), dtype=np.int64),
                 "sent_ids": np.zeros(1, dtype=np.int64)}
        feeds = {k: (v.astype(bool) if "bool" in self.inputs[k] else v) for k, v in feeds.items() if k in self.inputs}
        pos = np.asarray(self.session.run(None, feeds)[self.pos_at])[0].argmax(-1)
        return Parse([self.labels[int(k)] if f >= 0 else "X" for k, f in zip(pos, first)])


class Cached:
    """A tagger with its answers kept by the hash of the words, and its time counted."""

    def __init__(self, tagger):
        self.tagger = tagger
        self.cache: dict[str, Parse | None] = {}
        self.seconds = 0.0
        self.calls = 0
        self.words = 0

    def tag(self, words: tuple[str, ...]) -> Parse | None:
        key = hashlib.sha256("\x1f".join(words).encode()).hexdigest()
        if key not in self.cache:
            start = time.perf_counter()
            self.cache[key] = self.tagger.tag(list(words))
            self.seconds += time.perf_counter() - start
            self.calls += 1
            self.words += len(words)
        return self.cache[key]


# -------------------------------------------------------------------- filters

def keep_pos_verb(f: Finding, p: Parse) -> bool:
    """The least a tagger can say: no verb inside a noun stack; the verb of a relative clause is a verb."""
    if f.rule == "stacked-nouns":
        return not any(p.upos[k] in VERBS for k in f.tokens)
    if f.rule == "reduced-object-relative":
        return p.upos[f.tokens[2]] in VERBS
    return True


def keep_pos(f: Finding, p: Parse) -> bool:
    """Every word of the finding has the part of speech the construction needs."""
    if f.rule == "stacked-nouns":
        return all(p.upos[k] in NOUNS for k in f.tokens)
    if f.rule == "reduced-object-relative":
        head, subj, verb = f.tokens
        return p.upos[verb] in VERBS and p.upos[head] in NOMINALS and p.upos[subj] in NOMINALS
    return p.upos[f.tokens[1]] in VERBS


def ud_tokens(f: Finding, p: Parse) -> list[dict]:
    """The second model's tree in the token form that eval_gold_treebank's gold functions read."""
    return [{"form": w, "lemma": w.lower(), "upos": p.upos[k], "xpos": "", "feats": "", "head": p.heads[k],
             "deprel": p.deprels[k], "cxn": [], "space": True, "start": a, "end": b}
            for k, (w, (a, b)) in enumerate(zip(f.words, f.offsets))]


def keep_ud(f: Finding, p: Parse) -> bool:
    """The second model's UD tree holds the construction, by the definitions used on the gold tree.

    A noun stack must overlap a compound of three or more nouns, and a long
    dependency a subject or object arc of nine or more words. A reduced
    object relative needs its verb to be a relative clause (acl:relcl) with
    a subject of its own and no relative pronoun before the verb.
    """
    if p.heads is None or p.deprels is None:
        return True
    tokens = ud_tokens(f, p)
    if f.rule == "stacked-nouns":
        return any(tb.overlaps(f.span, (s["start"], s["end"])) for s in tb.gold_stacks(tokens))
    if f.rule == "long-dependency":
        return any(tb.overlaps(f.span, (a["start"], a["end"])) for a in tb.gold_long_dependencies(tokens))
    verb = f.tokens[2]
    if p.deprels[verb] != "acl:relcl":
        return False
    kids = [k for k, h in enumerate(p.heads) if h == verb]
    subject = any(p.deprels[k] in ("nsubj", "nsubj:pass") and f.words[k].lower() not in RELATIVE_PRONOUNS
                  for k in kids)
    relativizer = any(k < verb and f.words[k].lower() in RELATIVE_PRONOUNS for k in kids)
    return subject and not relativizer


FILTERS = {"pos-verb": keep_pos_verb, "pos": keep_pos, "ud": keep_ud}


def apply_filter(findings: list[Finding], tagger: Cached, keep) -> list[Finding]:
    """Findings the tagger supports. A sentence the tagger cannot read keeps its findings."""
    out = []
    for f in findings:
        parse = tagger.tag(f.words)
        if parse is None or keep(f, parse):
            out.append(f)
    return out


VERIFY = "sm + biaffine, readcost verify_model"


def package_filter(findings: list[Finding], tagger: Cached) -> list[Finding]:
    """readcost.verify's per-rule tests on the biaffine parse: the setting this experiment led to."""
    from readcost import verify

    out = []
    for f in findings:
        p = tagger.tag(f.words)
        parse = None if p is None else verify.Parse(tuple(p.upos), tuple(p.heads), tuple(p.deprels))
        if verify.keep(f.rule, parse, list(f.words), list(f.tokens)):
            out.append(f)
    return out


def agree(findings: list[Finding], other: list[Finding]) -> list[Finding]:
    """Findings that the other parser reports too: the same rule on overlapping words."""
    return [f for f in findings if any(g.rule == f.rule and tb.overlaps(f.span, g.span) for g in other)]


# -------------------------------------------------------------------- scoring

def references(analyzer, tokens: list[dict]) -> dict[str, dict]:
    """Per rule: spans that make a finding right, spans to be found, and the rule's findings on the gold tree."""
    stacks = tb.gold_stacks(tokens)
    relatives = tb.gold_reduced_relatives(tokens)
    arcs = tb.gold_long_dependencies(tokens)
    spans = [(a["start"], a["end"]) for a in arcs]
    always = [(a["start"], a["end"]) for a in arcs if a["distance"] >= tb.DEP_ALWAYS]
    tree = tb.gold_tree_findings(analyzer, tokens)
    out = {
        "stacked-nouns": {"right": [(s["start"], s["end"]) for s in stacks],
                          "refs": [(s["start"], s["end"]) for s in stacks if s["target"]]},
        "reduced-object-relative": {"right": [r["verb"] for r in relatives if r["object"]],
                                    "refs": [r["verb"] for r in relatives if r["target"]]},
        "long-dependency": {"right": spans,
                            "refs": always[:1] if tb.long_dependency_applies(tokens) else []},
    }
    for rule in RULES:
        out[rule]["tree"] = [(a, b) for r, a, b in tree if r == rule]
    return out


def counts(findings: list[Finding], refs: dict[str, dict]) -> dict[str, np.ndarray]:
    """One row of counts per rule for a sentence: findings, right, references, found, and the same against the gold-tree rule."""
    out = {}
    for rule in RULES:
        mine = [f.span for f in findings if f.rule == rule]
        r = refs[rule]
        row = np.zeros(7, dtype=np.int64)
        row[FINDINGS] = len(mine)
        row[RIGHT] = sum(1 for f in mine if any(tb.overlaps(f, x) for x in r["right"]))
        row[REFS] = len(r["refs"])
        row[FOUND] = sum(1 for x in r["refs"] if any(tb.overlaps(f, x) for f in mine))
        row[TREE_RIGHT] = sum(1 for f in mine if any(tb.overlaps(f, x) for x in r["tree"]))
        row[TREE_REFS] = len(r["tree"])
        row[TREE_FOUND] = sum(1 for x in r["tree"] if any(tb.overlaps(f, x) for f in mine))
        out[rule] = row
    return out


def by_cluster(rows: np.ndarray, clusters: list) -> np.ndarray:
    """Sum the sentence rows of each cluster (a document)."""
    labels, inverse = np.unique(np.asarray(clusters, dtype=object).astype(str), return_inverse=True)
    out = np.zeros((len(labels), rows.shape[1]), dtype=np.int64)
    np.add.at(out, inverse, rows)
    return out


def resample_sums(tables: dict, resamples: int = 2000, seed: int = 0, chunk: int = 200) -> dict:
    """Column sums of every table under the same resampled clusters: name -> [resamples, columns]."""
    n = len(next(iter(tables.values())))
    rng = np.random.default_rng(seed)
    out = {k: np.zeros((resamples, v.shape[1])) for k, v in tables.items()}
    for lo in range(0, resamples, chunk):
        size = min(chunk, resamples - lo)
        weights = rng.multinomial(n, np.full(n, 1.0 / n), size=size).astype(np.float64)
        for k, v in tables.items():
            out[k][lo:lo + size] = weights @ v
    return out


def ratio(sums: np.ndarray, top: int, bottom: int) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sums[..., bottom] > 0, sums[..., top] / sums[..., bottom], np.nan)


def interval(values: np.ndarray) -> tuple[float, float]:
    values = values[~np.isnan(values)]
    if not len(values):
        return float("nan"), float("nan")
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def summarize(tables: dict, base: str, resamples: int = 2000, seed: int = 0) -> dict:
    """Precision and recall of each configuration with intervals, and paired differences from ``base``.

    ``tables`` maps a configuration to its [clusters, 7] counts for one rule.
    """
    boot = resample_sums(tables, resamples, seed)
    pairs = {"precision": (RIGHT, FINDINGS), "recall": (FOUND, REFS),
             "tree_precision": (TREE_RIGHT, FINDINGS), "tree_recall": (TREE_FOUND, TREE_REFS)}
    out = {}
    for name, table in tables.items():
        total = table.sum(0)
        row = {"findings": int(total[FINDINGS]), "right": int(total[RIGHT]), "refs": int(total[REFS]),
               "found": int(total[FOUND]), "tree_right": int(total[TREE_RIGHT]),
               "tree_refs": int(total[TREE_REFS]), "tree_found": int(total[TREE_FOUND])}
        for key, (top, bottom) in pairs.items():
            row[key] = float(ratio(total, top, bottom))
            row[key + "_ci"] = interval(ratio(boot[name], top, bottom))
            diff = ratio(boot[name], top, bottom) - ratio(boot[base], top, bottom)
            row[key + "_diff"] = row[key] - float(ratio(tables[base].sum(0), top, bottom))
            row[key + "_diff_ci"] = interval(diff)
        out[name] = row
    return out


# ------------------------------------------------------------------- running

def load_group(paths: list[Path]) -> list[dict]:
    """Sentences of the files with text: id, cluster, text, tokens and the word count."""
    out = []
    for path in paths:
        for n, (meta, tokens) in enumerate(tb.read_conllu(path)):
            text = tb.text_of(tokens)
            if not text.strip() or all(t["form"] == "_" for t in tokens):
                continue  # GUM's Reddit documents ship without their text
            out.append({"cluster": f"{path.name}:{meta['doc'] or n}", "text": text, "tokens": tokens,
                        "words": sum(1 for t in tokens if t["upos"] != "PUNCT"), "file": path.name})
    return out


def parse_all(analyzer, texts: list[str]) -> tuple[list[list[Finding]], float]:
    """Findings per text and the seconds the parser and the rules took."""
    from readcost.features import Context

    ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
    start = time.perf_counter()
    out = [doc_findings(ctx, doc) for doc in analyzer.nlp.pipe(texts)]
    return out, time.perf_counter() - start


def tagger_accuracy(tagger, sentences: list[dict], limit: int = 400) -> dict:
    """Part-of-speech accuracy of a tagger on gold words, and how often it swaps noun and verb."""
    step = max(1, len(sentences) // limit)
    total = right = swapped = 0
    for s in sentences[::step][:limit]:
        parse = tagger.tag([t["form"] for t in s["tokens"]])
        if parse is None:
            continue
        for t, got in zip(s["tokens"], parse.upos):
            total += 1
            right += got == t["upos"]
            swapped += (t["upos"] in VERBS and got in NOUNS) or (t["upos"] in NOUNS and got in VERBS)
    return {"words": total, "accuracy": right / total if total else float("nan"),
            "noun_verb_swaps_per_1000": 1000.0 * swapped / total if total else float("nan")}


class SpacyTagger:
    """A spaCy pipeline run on given words, for `tagger_accuracy`."""

    def __init__(self, nlp):
        self.nlp = nlp

    def tag(self, words: list[str]) -> Parse:
        from spacy.tokens import Doc

        doc = Doc(self.nlp.vocab, words=words)
        for _name, proc in self.nlp.pipeline:
            doc = proc(doc)
        return Parse([t.pos_ for t in doc])


def run_group(name: str, sentences: list[dict], analyzers: dict, taggers: dict[str, Cached],
              resamples: int, examples: int = 0) -> dict:
    """Every configuration on one group of sentences."""
    texts = [s["text"] for s in sentences]
    words = sum(s["words"] for s in sentences)
    base = analyzers["sm"]
    refs = [references(base, s["tokens"]) for s in sentences]
    found: dict[str, list[list[Finding]]] = {}
    seconds: dict[str, float] = {}
    reparsed: dict[str, int] = {}
    for key, analyzer in analyzers.items():
        found[key], seconds[key] = parse_all(analyzer, texts)
        reparsed[key] = len(texts)
    flagged = [k for k, fs in enumerate(found["sm"]) if fs]
    if "trf" in analyzers:
        # The verifier reads only the sentences with a finding; time that pass alone.
        subset = [texts[k] for k in flagged]
        start = time.perf_counter()
        for _doc in analyzers["trf"].nlp.pipe(subset):
            pass
        found["sm & trf"] = [agree(a, b) for a, b in zip(found["sm"], found["trf"])]
        seconds["sm & trf"] = seconds["sm"] + time.perf_counter() - start
        reparsed["sm & trf"] = len(subset)
    for tname, tagger in taggers.items():
        before = tagger.seconds
        for fs in found["sm"]:
            for f in fs:
                tagger.tag(f.words)
        cost = tagger.seconds - before
        for fname, keep in FILTERS.items():
            if fname == "ud" and tname == "kniv":
                continue  # only its part-of-speech scores are read
            key = f"sm + {tname} {fname}"
            found[key] = [apply_filter(fs, tagger, keep) for fs in found["sm"]]
            seconds[key] = seconds["sm"] + cost
            reparsed[key] = len(flagged)
        if tname == "biaffine":
            found[VERIFY] = [package_filter(fs, tagger) for fs in found["sm"]]
            seconds[VERIFY] = seconds["sm"] + cost
            reparsed[VERIFY] = len(flagged)
    tables = {rule: {} for rule in RULES}
    clusters = [s["cluster"] for s in sentences]
    for key, per_sentence in found.items():
        rows = [counts(fs, r) for fs, r in zip(per_sentence, refs)]
        for rule in RULES:
            tables[rule][key] = by_cluster(np.stack([r[rule] for r in rows]), clusters)
    result = {"name": name, "sentences": len(sentences), "words": words,
              "clusters": len(set(clusters)), "files": sorted({s["file"] for s in sentences}),
              "has_cxn": any(c.startswith("rc-") for s in sentences for t in s["tokens"] for c in t["cxn"]),
              "ms_per_1000_words": {k: 1000.0 * 1000.0 * v / words for k, v in seconds.items()},
              "sentences_read_by_second_model": reparsed,
              "rules": {rule: summarize(tables[rule], "sm", resamples) for rule in RULES}}
    if examples:
        result["examples"] = dropped_examples(sentences, found, refs, examples)
    return result


def dropped_examples(sentences, found, refs, limit: int) -> dict:
    """A few findings each filter dropped, with whether the gold construction was there."""
    out: dict[str, list] = {}
    for key, per_sentence in found.items():
        if key in ("sm", "trf"):
            continue
        rows = out.setdefault(key, [])
        for s, mine, kept, r in zip(sentences, found["sm"], per_sentence, refs):
            for f in mine:
                if f in kept or len(rows) >= limit:
                    continue
                rows.append({"rule": f.rule, "words": s["text"][f.start:f.end][:120],
                             "gold_has_it": any(tb.overlaps(f.span, x) for x in r[f.rule]["right"])})
    return out


def run_rulebench(path: Path, analyzers: dict, taggers: dict[str, Cached], verify_dir: Path | None = None) -> dict:
    """The labelled bench under each configuration: an item fires when a finding of its rule survives."""
    from readcost.extract import extract
    from readcost.features import NOUN_RUN_RULES, Context, detect, misparsed_verb

    items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def fired(analyzer, item) -> tuple[set[str], list[Finding]]:
        ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
        rules: set[str] = set()
        mine: list[Finding] = []
        for seg in extract(item["text"], "<bench>", "markdown"):
            ctx.codes = seg.codes
            doc = analyzer.nlp(seg.text)
            mine.extend(doc_findings(ctx, doc))
            for sent in doc.sents:
                if len([t for t in sent if t.is_alpha]) < 4:
                    continue
                only = None
                if not any(t.pos_ in VERBS for t in sent):
                    if not misparsed_verb(sent):
                        continue
                    only = NOUN_RUN_RULES
                rules.update(rule for rule, *_ in detect(sent, ctx, only) if rule not in seg.skip)
        return rules, mine

    per = {key: [fired(a, it) for it in items] for key, a in analyzers.items()}
    configs: dict[str, list[bool]] = {}
    for key, rows in per.items():
        configs[key] = [it["rule"] in rules for it, (rules, _f) in zip(items, rows)]

    def filtered(kept_of) -> list[bool]:
        """``kept_of(k, findings)``: the findings of item k that survive."""
        out = []
        for k, (it, (rules, mine)) in enumerate(zip(items, per["sm"])):
            if it["rule"] in RULES:
                out.append(any(f.rule == it["rule"] for f in kept_of(k, mine)))
            else:
                out.append(it["rule"] in rules)  # a rule the filters do not touch
        return out

    if "trf" in per:
        configs["sm & trf"] = filtered(lambda k, mine: agree(mine, per["trf"][k][1]))
    for tname, tagger in taggers.items():
        for fname, keep in FILTERS.items():
            if fname == "ud" and tname == "kniv":
                continue
            configs[f"sm + {tname} {fname}"] = filtered(lambda k, mine, keep=keep, tagger=tagger:
                                                        apply_filter(mine, tagger, keep))
        if tname == "biaffine":
            configs[VERIFY] = filtered(lambda k, mine, tagger=tagger: package_filter(mine, tagger))
    if verify_dir is not None:
        # End to end: readcost's own check_text with the setting on, as a user would run it.
        from readcost import Analyzer, Config

        a = Analyzer(Config(verify_model=str(verify_dir)))
        configs["readcost check, verify_model on"] = [
            it["rule"] in {f.feature for f in a.check_text(it["text"], "markdown").findings} for it in items]
    out = {}
    for key, fires in configs.items():
        scores: dict[str, dict] = {}
        for it, f in zip(items, fires):
            for rule in (it["rule"], "all rules", "three rules" if it["rule"] in RULES else None):
                if rule is None:
                    continue
                s = scores.setdefault(rule, {"tp": 0, "fn": 0, "tn": 0, "fp": 0})
                s[("tp" if f else "fn") if it["expected"] == "fire" else ("fp" if f else "tn")] += 1
        out[key] = scores
    return {"items": len(items), "configs": out}


# ------------------------------------------------------------------ reporting

def pct(x: float) -> str:
    return "-" if x != x else f"{x:.0%}"


def with_ci(x: float, ci: tuple[float, float]) -> str:
    return "-" if x != x else f"{x:.0%} ({ci[0]:.0%} to {ci[1]:.0%})"


def signed(x: float, ci: tuple[float, float]) -> str:
    if x != x:
        return "-"
    return f"{100 * x:+.0f} ({100 * ci[0]:+.0f} to {100 * ci[1]:+.0f})"


def report_group(g: dict) -> str:
    lines = [f"### {g['name']}", "",
             f"{g['sentences']} sentences, {g['words']} words, {g['clusters']} resampling units, from "
             f"{', '.join(g['files'])}.", ""]
    for rule in RULES:
        rows = g["rules"][rule]
        base = rows["sm"]
        lines += [f"**{rule}**" + ("" if rule != "reduced-object-relative" or g["has_cxn"] else
                                   " (no treebank here marks the construction; only the gold-tree rule applies)"),
                  "",
                  "| Configuration | Findings | Dropped (of them right) | Is the construction | Change, points | "
                  "Recall of the construction | Change | Agrees with rule on gold tree | Change | "
                  "Gold-tree findings found | Change |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        marked = rule != "reduced-object-relative" or g["has_cxn"]
        for key, r in rows.items():
            dropped = base["findings"] - r["findings"]
            was_right = f" ({base['right'] - r['right']})" if marked else ""
            lines.append(
                f"| {key} | {r['findings']} | "
                + ("-" if key in ("sm", "trf") else f"{dropped}{was_right}") + " | "
                + (f"{with_ci(r['precision'], r['precision_ci'])} | " if marked else "- | ")
                + ("-" if key == "sm" or not marked else signed(r["precision_diff"], r["precision_diff_ci"])) + " | "
                + (f"{r['found']}/{r['refs']} = {pct(r['recall'])} | " if marked else "- | ")
                + ("-" if key == "sm" or not marked else signed(r["recall_diff"], r["recall_diff_ci"])) + " | "
                + f"{with_ci(r['tree_precision'], r['tree_precision_ci'])} | "
                + ("-" if key == "sm" else signed(r["tree_precision_diff"], r["tree_precision_diff_ci"])) + " | "
                + f"{r['tree_found']}/{r['tree_refs']} = {pct(r['tree_recall'])} | "
                + ("-" if key == "sm" else signed(r["tree_recall_diff"], r["tree_recall_diff_ci"])) + " |")
        lines.append("")
    lines += ["| Configuration | ms per 1,000 words | Sentences the second model read |", "| --- | --- | --- |"]
    for key, ms in g["ms_per_1000_words"].items():
        lines.append(f"| {key} | {ms:.0f} | {'-' if key == 'sm' else g['sentences_read_by_second_model'][key]} |")
    return "\n".join(lines) + "\n"


def report_rulebench(bench: dict) -> str:
    lines = [f"### Labelled bench (eval/rulebench), {bench['items']} items with text", "",
             "| Configuration | Rules | TP | FN | TN | FP | Precision | Recall |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for key, scores in bench["configs"].items():
        for rule in ("all rules", "three rules", *RULES):
            s = scores.get(rule)
            if not s:
                continue
            p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else float("nan")
            r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else float("nan")
            lines.append(f"| {key} | {rule} | {s['tp']} | {s['fn']} | {s['tn']} | {s['fp']} | {pct(p)} | {pct(r)} |")
    return "\n".join(lines) + "\n"


def report_accuracy(rows: dict) -> str:
    lines = ["### Part of speech on gold words", "",
             "A sample of each group, tagged from the gold tokens. spaCy maps its OntoNotes tags to "
             "UD's, so its accuracy is lowered by convention differences; the noun and verb swaps are "
             "the errors that matter here.", "",
             "| Group | Model | Words | UPOS accuracy | Noun/verb swaps per 1,000 words |", "| --- | --- | --- | --- | --- |"]
    for (group, model), r in rows.items():
        lines.append(f"| {group} | {model} | {r['words']} | {r['accuracy']:.1%} | {r['noun_verb_swaps_per_1000']:.1f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--group", nargs="+", action="append", metavar=("NAME", "CONLLU"), required=True,
                    help="a name, then the CoNLL-U files scored together")
    ap.add_argument("--second-spacy", help="a spaCy model to compare with and to verify against (en_core_web_trf)")
    ap.add_argument("--biaffine", type=Path, help="directory with the biaffine parser's model.onnx, config.json, tokenizer.json")
    ap.add_argument("--kniv", type=Path, help="directory of a kniv v7 model (onnx/, tokenizer.json)")
    ap.add_argument("--rulebench", type=Path, help="rulebench.jsonl with text, from scripts/fetch_rulebench.py")
    ap.add_argument("--resamples", type=int, default=2000)
    ap.add_argument("--limit", type=int, default=0, help="read at most this many sentences per group (for a trial run)")
    ap.add_argument("--examples", type=int, default=0, help="keep this many dropped findings per filter in the JSON")
    ap.add_argument("--json", type=Path, help="write every number here")
    args = ap.parse_args(argv)

    from readcost import Analyzer, Config

    analyzers = {"sm": Analyzer(Config())}
    load_seconds = {}
    if args.second_spacy:
        start = time.perf_counter()
        analyzers["trf"] = Analyzer(Config(model=args.second_spacy))
        analyzers["trf"].nlp  # load now, so that the load is not counted as parsing
        load_seconds["trf"] = time.perf_counter() - start
    taggers: dict[str, Cached] = {}
    for name, directory, cls in (("biaffine", args.biaffine, Biaffine), ("kniv", args.kniv, Kniv)):
        if directory is None:
            continue
        try:
            start = time.perf_counter()
            taggers[name] = Cached(cls(directory))
            load_seconds[name] = time.perf_counter() - start
            session = taggers[name].tagger.session
            print(f"<!-- {name}: inputs {[(i.name, i.shape, i.type) for i in session.get_inputs()]}; "
                  f"outputs {[(o.name, o.shape) for o in session.get_outputs()][:6]} -->")
        except Exception as exc:  # noqa: BLE001 - one model failing to load must not lose the rest of the run
            print(f"**{name} did not load: {type(exc).__name__}: {exc}**\n")
    analyzers["sm"].nlp("Warm the pipeline up before any timing.")

    result: dict = {"second_spacy": args.second_spacy, "load_seconds": load_seconds, "groups": [], "accuracy": {}}
    accuracy: dict = {}
    print("## A second parser or tagger as a check on three rules\n")
    print(f"Second spaCy model: {args.second_spacy or 'none'}. Taggers: {', '.join(taggers) or 'none'}. "
          f"Load time, seconds: {', '.join(f'{k} {v:.1f}' for k, v in load_seconds.items()) or '-'}.\n")
    for name, *paths in args.group:
        sentences = load_group([Path(p) for p in paths])
        if args.limit:
            step = max(1, len(sentences) // args.limit)
            sentences = sentences[::step][:args.limit]
        models = {key: SpacyTagger(a.nlp) for key, a in analyzers.items()} | {k: t.tagger for k, t in taggers.items()}
        for key, model in models.items():
            try:
                accuracy[(name, key)] = tagger_accuracy(model, sentences)
            except Exception as exc:  # noqa: BLE001
                print(f"**{key} failed on gold words: {type(exc).__name__}: {exc}**\n")
                taggers.pop(key, None)
        group = run_group(name, sentences, analyzers, taggers, args.resamples, args.examples)
        result["groups"].append(group)
        print(report_group(group), flush=True)
    result["accuracy"] = {f"{g} / {m}": r for (g, m), r in accuracy.items()}
    print(report_accuracy(accuracy))
    if args.rulebench and args.rulebench.is_file():
        result["rulebench"] = run_rulebench(args.rulebench, analyzers, taggers,
                                            args.biaffine if "biaffine" in taggers else None)
        print(report_rulebench(result["rulebench"]))
    if args.json:
        args.json.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
