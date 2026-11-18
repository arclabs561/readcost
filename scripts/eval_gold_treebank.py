"""Precision and recall of three rules against hand-corrected parses.

    git clone --depth 1 https://github.com/UniversalDependencies/UD_English-EWT /tmp/data/UD_English-EWT/repo
    git clone --depth 1 https://github.com/UniversalDependencies/UD_English-GUM /tmp/data/UD_English-GUM/repo
    uv run python scripts/eval_gold_treebank.py /tmp/data/UD_English-EWT/repo/*.conllu
    uv run python scripts/eval_gold_treebank.py --genres academic,textbook,whow /tmp/data/UD_English-GUM/repo/*.conllu

Data: Universal Dependencies English treebanks, with part-of-speech tags
and dependency trees corrected by annotators.

    UD_English-EWT  https://github.com/UniversalDependencies/UD_English-EWT
                    weblogs, newsgroups, email, reviews, question answers;
                    CC BY-SA 4.0. Its MISC column marks each relative
                    clause's type (Cxn=rc-red-obj is a reduced object
                    relative), produced by the treebank's own script from
                    the corrected trees.
    UD_English-GUM  https://github.com/UniversalDependencies/UD_English-GUM
                    academic, how-to, news, fiction, speech and more;
                    annotations CC BY-NC-SA 4.0, texts under their own
                    licences. Reddit documents ship without text and are
                    skipped. It has no relative-clause types.

The data stays outside this repository. readcost's default parser
(en_core_web_sm) was trained on OntoNotes, not on these treebanks, so every
split is unseen text and all three are used.

Each sentence is rebuilt from its tokens and checked alone. Two references
are derived from the gold annotation:

Gold constructions, defined on the UD tree with no readcost code:
  stacked-nouns            a noun with two or more `compound` noun
                           dependents, counted through the chain (three or
                           more nouns in one compound)
  reduced-object-relative  a clause marked Cxn=rc-red-obj (EWT only)
  long-dependency          a subject or object arc at least 9 words long
                           (readcost's own threshold; 15 for recall), after
                           moving the subject of a copular clause onto the
                           copula as readcost's parser does
A finding is right when its span overlaps the gold construction. Precision
against these says how many findings are the construction they name.
Recall is also given against the part of the gold set that the rule means
to report: readcost skips names, and object relatives with a pronoun
subject, on purpose.

Rules on the gold tree. The UD tree is converted to the label scheme of
readcost's parser and the detectors run on it. Agreement between the
findings on the parser's tree and on the gold tree isolates what the parser
costs, because the rule is the same on both sides. The conversion is
approximate (copulas, prepositions and a label map), so a few percent of the
disagreement is the conversion's.

What this can show: how often a finding names a construction that is not
there, and how much of that comes from the parser. What it cannot show:
whether a real construction is worth reporting, which is the larger part of
the low precision in docs/evaluation.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_signals import detect_spans  # noqa: E402

NOUNS = ("NOUN", "PROPN")
CORE_UD = ("nsubj", "nsubj:pass", "nsubj:outer", "csubj", "csubj:pass", "obj", "iobj")
MOVE_TO_COPULA = {"nsubj", "nsubj:pass", "nsubj:outer", "csubj", "csubj:pass", "aux", "aux:pass", "mark",
                  "cc", "punct", "advcl", "parataxis", "expl", "discourse", "vocative"}
LABELS = {"root": "ROOT", "acl:relcl": "relcl", "nsubj:pass": "nsubjpass", "csubj:pass": "csubjpass",
          "aux:pass": "auxpass", "obj": "dobj", "iobj": "dative", "obl:npmod": "npadvmod",
          "obl:tmod": "npadvmod", "obl:unmarked": "npadvmod", "nmod:unmarked": "npadvmod",
          "nmod:npmod": "npadvmod", "nmod:tmod": "npadvmod", "nmod:poss": "poss", "flat": "compound",
          "compound:prt": "prt", "det:predet": "predet", "cc:preconj": "preconj", "nsubj:outer": "nsubj",
          "csubj:outer": "csubj", "advcl:relcl": "advcl", "discourse": "intj", "obl": "npadvmod",
          "obl:agent": "npadvmod", "nmod": "nmod", "nmod:desc": "appos"}
LIGHT_HEADS = {"time", "way", "all", "reason", "day", "moment", "place"}  # as in features.LIGHT_RELATIVE_HEADS
STACK_MIN, DEP_MIN, DEP_ALWAYS, DEP_MIN_WORDS = 3, 9, 15, 10


# ------------------------------------------------------------------ reading

def read_conllu(path: Path):
    """Yield (meta, tokens) per sentence; a token is a dict with offsets into the rebuilt text.

    Multiword-token lines (1-2) give only the spacing; empty nodes (8.1) are
    skipped. ``head`` is a 0-based index, -1 for the root.
    """
    meta: dict[str, str] = {}
    tokens: list[dict] = []
    ranges: dict[int, tuple[int, bool]] = {}   # first id -> (last id, space after the range)
    doc = ""

    def finish():
        closing = {last: space for last, space in ranges.values()}
        inside = {i for first, (last, _) in ranges.items() for i in range(first, last)}
        pos = 0
        for k, t in enumerate(tokens):
            if k + 1 in inside:
                t["space"] = False
            elif k + 1 in closing:
                t["space"] = closing[k + 1]
            t["start"], t["end"] = pos, pos + len(t["form"])
            pos = t["end"] + (1 if t["space"] else 0)
        return dict(meta, doc=doc), tokens

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            if tokens:
                yield finish()
            meta, tokens, ranges = {}, [], {}
        elif line.startswith("#"):
            key, _, value = line[1:].partition("=")
            meta[key.strip()] = value.strip()
            if key.strip() == "newdoc id":
                doc = value.strip()
        else:
            c = line.split("\t")
            if len(c) != 10 or "." in c[0]:
                continue
            misc = dict(m.partition("=")[::2] for m in c[9].split("|")) if c[9] != "_" else {}
            if "-" in c[0]:
                first, last = c[0].split("-")
                ranges[int(first)] = (int(last), misc.get("SpaceAfter") != "No")
                continue
            tokens.append({"form": c[1], "lemma": c[2], "upos": c[3], "xpos": c[4],
                           "feats": "" if c[5] == "_" else c[5], "head": int(c[6]) - 1, "deprel": c[7],
                           "cxn": [x for x in misc.get("Cxn", "").split(",") if x],
                           "space": misc.get("SpaceAfter") != "No"})
    if tokens:
        yield finish()


def text_of(tokens: list[dict]) -> str:
    return "".join(t["form"] + (" " if t["space"] else "") for t in tokens).rstrip()


def children(tokens: list[dict]) -> list[list[int]]:
    out: list[list[int]] = [[] for _ in tokens]
    for k, t in enumerate(tokens):
        if t["head"] >= 0:
            out[t["head"]].append(k)
    return out


# --------------------------------------------------------- gold constructions

def gold_stacks(tokens: list[dict]) -> list[dict]:
    """Noun compounds of three or more nouns: (start, end, target).

    ``target`` is False for what readcost leaves alone on purpose: two or
    more capitalised members (a name) or a hyphen inside the compound (one
    hyphenated unit).
    """
    kids = children(tokens)
    out = []
    for k, t in enumerate(tokens):
        if t["upos"] not in NOUNS or t["deprel"] == "compound":
            continue
        members, todo = [], [k]
        while todo:
            i = todo.pop()
            members.append(i)
            todo.extend(c for c in kids[i] if tokens[c]["deprel"] == "compound" and tokens[c]["upos"] in NOUNS)
        if len(members) < STACK_MIN:
            continue
        lo, hi = min(members), max(members)
        capitals = sum(1 for i in members if tokens[i]["form"][:1].isupper() and i != 0)
        hyphen = any(tokens[i]["form"] in ("-", "–") for i in range(lo, hi + 1))
        words = all(any(ch.isalpha() for ch in tokens[i]["form"]) for i in members)
        out.append({"start": tokens[lo]["start"], "end": tokens[hi]["end"],
                    "target": capitals < 2 and not hyphen and words})
    return out


def gold_reduced_relatives(tokens: list[dict]) -> list[dict]:
    """Reduced relative clauses from the Cxn annotation: (start, end, object, target).

    ``object`` is True for rc-red-obj and its subtypes, False for other
    reduced relatives (obliques: "the way he did it", "the house we lived
    in"). ``target`` leaves out what the rule skips on purpose: a pronoun
    subject ("someone I trust") and light heads ("the first time we met").
    """
    kids = children(tokens)
    out = []
    for k, t in enumerate(tokens):
        kinds = [c for c in t["cxn"] if c.startswith("rc-red-")]
        if not kinds or t["head"] < 0:
            continue
        head = tokens[t["head"]]
        subj = [tokens[c] for c in kids[k] if tokens[c]["deprel"] in ("nsubj", "nsubj:pass")]
        is_object = any(c.startswith("rc-red-obj") for c in kinds)
        target = (is_object and bool(subj) and subj[0]["upos"] != "PRON"
                  and head["lemma"].lower() not in LIGHT_HEADS)
        out.append({"start": min(head["start"], t["start"]), "end": max(head["end"], t["end"]),
                    "verb": (t["start"], t["end"]), "object": is_object, "target": target})
    return out


def gold_relative_verbs(tokens: list[dict]) -> list[tuple[int, int]]:
    """Spans of every relative-clause predicate, reduced or not."""
    return [(t["start"], t["end"]) for t in tokens if t["deprel"] == "acl:relcl"]


def core_arcs(tokens: list[dict]) -> list[tuple[int, int, int]]:
    """(distance in words, dependent, head) of subject and object arcs, readcost's way.

    Punctuation does not count toward distance. In a copular clause UD
    attaches the subject to the predicate ("the index is a file": index <-
    file); readcost's parser attaches it to the copula, and the predicate
    noun to the copula as an attribute, so both arcs are measured to the
    copula here.
    """
    order = {k: n for n, k in enumerate(k for k, t in enumerate(tokens) if t["upos"] != "PUNCT")}
    kids = children(tokens)
    copula = {k: next((c for c in kids[k] if tokens[c]["deprel"] == "cop"), None) for k in range(len(tokens))}
    out = []
    for k, t in enumerate(tokens):
        if k not in order:
            continue
        head = t["head"]
        if t["deprel"] in CORE_UD and head >= 0:
            head = copula[head] if copula[head] is not None else head
            if head in order:
                out.append((abs(order[k] - order[head]), k, head))
        if copula[k] is not None and t["upos"] in ("NOUN", "PROPN", "PRON") and copula[k] in order:
            out.append((abs(order[k] - order[copula[k]]), k, copula[k]))
    return out


def gold_long_dependencies(tokens: list[dict], minimum: int = DEP_MIN) -> list[dict]:
    """Subject and object arcs of at least ``minimum`` words: (start, end, ends)."""
    out = []
    for dist, dep, head in core_arcs(tokens):
        if dist >= minimum:
            a, b = tokens[min(dep, head)], tokens[max(dep, head)]
            out.append({"start": a["start"], "end": b["end"], "distance": dist,
                        "ends": {a["start"], tokens[max(dep, head)]["start"]}})
    return out


def long_dependency_applies(tokens: list[dict]) -> bool:
    """The gold-side version of the conditions under which the rule runs at all.

    Ten or more words, no colon, and no word with two or more conjuncts.
    The rule also stands down when inline-list fires; that is not copied
    here, so recall is slightly understated.
    """
    words = sum(1 for t in tokens if t["upos"] != "PUNCT")
    kids = children(tokens)
    listed = any(sum(1 for c in kids[k] if tokens[c]["deprel"] == "conj") >= 2 for k in range(len(tokens)))
    return words >= DEP_MIN_WORDS and not listed and ":" not in text_of(tokens)


# ----------------------------------------------------- rules on the gold tree

def to_readcost_scheme(tokens: list[dict]) -> tuple[list[int], list[str]]:
    """Heads and labels of the UD tree in the scheme of readcost's parser, approximately.

    Four changes: the copula heads its clause and takes the subject,
    auxiliaries and markers, with the predicate as attr or acomp; a
    preposition heads its noun (prep, pobj) and attaches where the noun did;
    the clause of a free relative is a complement, not a relative clause;
    labels are renamed (obj to dobj, acl:relcl to relcl and so on).
    """
    heads = [t["head"] for t in tokens]
    deps = [t["deprel"] for t in tokens]
    kids = children(tokens)
    for k, t in enumerate(tokens):
        cop = next((c for c in kids[k] if tokens[c]["deprel"] == "cop"), None)
        if cop is None:
            continue
        heads[cop], deps[cop] = heads[k], deps[k]
        heads[k] = cop
        deps[k] = "attr" if t["upos"] in ("NOUN", "PROPN", "PRON", "NUM") else "acomp"
        for c in kids[k]:
            if c != cop and tokens[c]["deprel"] in MOVE_TO_COPULA:
                heads[c] = cop
    for k, t in enumerate(tokens):
        case = next((c for c in kids[k] if tokens[c]["deprel"] == "case" and tokens[c]["upos"] in ("ADP", "SCONJ")),
                    None)
        if case is None or heads[k] < 0 or heads[k] == case:
            continue
        heads[case], deps[case] = heads[k], "prep"
        heads[k], deps[k] = case, "pobj"
    for k, t in enumerate(tokens):
        # A free relative ("what the team has been doing"): UD makes "what" the
        # head of a relative clause; readcost's parser makes it the verb's object.
        if t["deprel"] == "acl:relcl" and tokens[t["head"]]["xpos"] in ("WP", "WDT", "WRB", "WP$"):
            deps[k] = "ccomp"
    keep = ("attr", "acomp", "prep", "pobj", "ccomp")
    return heads, [d if d in keep else LABELS.get(d, d.split(":")[0]) for d in deps]


def gold_tree_findings(analyzer, tokens: list[dict]) -> list[tuple[str, int, int]]:
    """(rule, start, end) from readcost's detectors run on the converted gold tree."""
    from spacy.tokens import Doc

    from readcost.features import NOUN_RUN_RULES, Context, detect, misparsed_verb

    heads, deps = to_readcost_scheme(tokens)
    if sum(1 for h in heads if h < 0) != 1:
        return []
    doc = Doc(analyzer.nlp.vocab, words=[t["form"] for t in tokens], spaces=[t["space"] for t in tokens],
              pos=[t["upos"] for t in tokens], tags=[t["xpos"] for t in tokens],
              morphs=[t["feats"] for t in tokens], lemmas=[t["lemma"] for t in tokens],
              heads=[k if h < 0 else h for k, h in enumerate(heads)], deps=deps,
              sent_starts=[k == 0 for k in range(len(tokens))])
    sent = doc[:]
    if len([t for t in sent if t.is_alpha]) < 4:
        return []
    rules = None
    if not any(t.pos_ in ("VERB", "AUX") for t in sent):
        if not misparsed_verb(sent):
            return []
        rules = NOUN_RUN_RULES
    ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
    return [(rule, min(t.idx for t in toks), max(t.idx + len(t.text) for t in toks))
            for rule, _sev, _msg, toks in detect(sent, ctx, rules) if toks]


# ------------------------------------------------------------------ scoring

def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


class Tally:
    """Counts for one comparison: findings, how many are right, references, how many are found."""

    def __init__(self) -> None:
        self.findings = self.right = self.references = self.found = 0

    def add(self, findings: list[tuple[int, int]], references: list[tuple[int, int]],
            correct: list[tuple[int, int]] | None = None) -> None:
        """``correct`` (default: the references) is what makes a finding right."""
        correct = references if correct is None else correct
        self.findings += len(findings)
        self.right += sum(1 for f in findings if any(overlaps(f, r) for r in correct))
        self.references += len(references)
        self.found += sum(1 for r in references if any(overlaps(f, r) for f in findings))

    @property
    def precision(self) -> float:
        return self.right / self.findings if self.findings else float("nan")

    @property
    def recall(self) -> float:
        return self.found / self.references if self.references else float("nan")

    def line(self) -> str:
        lo, hi = wilson(self.right, self.findings)
        return (f"precision {self.right}/{self.findings} = {self.precision:.0%} (95% CI {lo:.0%} to {hi:.0%}), "
                f"recall {self.found}/{self.references} = {self.recall:.0%}")


def wilson(k: int, n: int) -> tuple[float, float]:
    """95% Wilson interval for a proportion."""
    if not n:
        return float("nan"), float("nan")
    z = 1.96
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return centre - half, centre + half


def score(analyzer, sentences) -> dict:
    """Run every comparison over (meta, tokens) pairs and return the tallies."""
    t = {name: Tally() for name in (
        "stack/gold", "stack/target", "stack/tree",
        "relative/object", "relative/target", "relative/tree",
        "dependency/gold", "dependency/always", "dependency/tree")}
    extra = {"sentences": 0, "words": 0, "stack_not_nouns": 0, "stack_shorter": 0,
             "relative_reduced_other": 0, "relative_with_relativizer": 0, "relative_none": 0,
             "dependency_same_pair": 0, "has_cxn": False}
    for _meta, tokens in sentences:
        text = text_of(tokens)
        if not text.strip() or all(tok["form"] == "_" for tok in tokens):
            continue
        extra["sentences"] += 1
        extra["words"] += sum(1 for tok in tokens if tok["upos"] != "PUNCT")
        found = [f for s in detect_spans(analyzer, text) for f in s["findings"]]
        mine = {rule: [(a, b) for r, _sev, a, b in found if r == rule]
                for rule in ("stacked-nouns", "reduced-object-relative", "long-dependency")}
        tree = gold_tree_findings(analyzer, tokens)
        on_tree = {rule: [(a, b) for r, a, b in tree if r == rule] for rule in mine}

        stacks = gold_stacks(tokens)
        every = [(s["start"], s["end"]) for s in stacks]
        t["stack/gold"].add(mine["stacked-nouns"], every)
        t["stack/target"].add(mine["stacked-nouns"], [(s["start"], s["end"]) for s in stacks if s["target"]], every)
        t["stack/tree"].add(mine["stacked-nouns"], on_tree["stacked-nouns"])
        for f in mine["stacked-nouns"]:
            if any(overlaps(f, r) for r in every):
                continue
            covered = [tok for tok in tokens if overlaps(f, (tok["start"], tok["end"]))]
            if any(tok["upos"] not in NOUNS and tok["upos"] != "PUNCT" for tok in covered):
                extra["stack_not_nouns"] += 1
            else:
                extra["stack_shorter"] += 1

        relatives = gold_reduced_relatives(tokens)
        extra["has_cxn"] = extra["has_cxn"] or any(c.startswith("rc-") for tok in tokens for c in tok["cxn"])
        objects = [r["verb"] for r in relatives if r["object"]]
        t["relative/object"].add(mine["reduced-object-relative"], objects)
        t["relative/target"].add(mine["reduced-object-relative"],
                                 [r["verb"] for r in relatives if r["target"]], objects)
        t["relative/tree"].add(mine["reduced-object-relative"], on_tree["reduced-object-relative"])
        verbs = gold_relative_verbs(tokens)
        for f in mine["reduced-object-relative"]:
            if any(overlaps(f, r) for r in objects):
                continue
            if any(overlaps(f, r["verb"]) for r in relatives):
                extra["relative_reduced_other"] += 1
            elif any(overlaps(f, v) for v in verbs):
                extra["relative_with_relativizer"] += 1
            else:
                extra["relative_none"] += 1

        arcs = gold_long_dependencies(tokens)
        spans = [(a["start"], a["end"]) for a in arcs]
        applies = long_dependency_applies(tokens)
        t["dependency/gold"].add(mine["long-dependency"], [], spans)
        always = [(a["start"], a["end"]) for a in arcs if a["distance"] >= DEP_ALWAYS] if applies else []
        t["dependency/always"].add(mine["long-dependency"], always[:1], spans)
        t["dependency/tree"].add(mine["long-dependency"], on_tree["long-dependency"])
        starts = {tok["start"] for tok in tokens}
        for a, b in mine["long-dependency"]:
            last = max((s for s in starts if s < b), default=a)
            if any(arc["ends"] == {a, last} for arc in arcs):
                extra["dependency_same_pair"] += 1
    return {"tallies": t, **extra}


def report(result: dict) -> None:
    t = result["tallies"]
    print(f"{result['sentences']} sentences, {result['words']} words")

    def ci(k, n):
        lo, hi = wilson(k, n)
        return f"(95% CI {lo:.0%} to {hi:.0%})"

    s = t["stack/gold"]
    print("\nstacked-nouns")
    print(f"  against gold compounds of 3+ nouns: {s.line()}")
    print(f"    wrong findings: {result['stack_not_nouns']} cover a word that is not a noun in the gold tags; "
          f"{result['stack_shorter']} cover only nouns that gold does not join into one compound of 3")
    s = t["stack/target"]
    print(f"  recall on compounds that are not names or hyphenated: {s.found}/{s.references} = {s.recall:.0%} "
          f"{ci(s.found, s.references)}")
    s = t["stack/tree"]
    print(f"  against the same rule on the gold tree: {s.line()}")

    print("\nreduced-object-relative")
    if result["has_cxn"]:
        s = t["relative/object"]
        print(f"  against gold reduced object relatives: {s.line()}")
        print(f"    wrong findings: {result['relative_reduced_other']} are reduced relatives of another kind, "
              f"{result['relative_with_relativizer']} are relatives that gold does not mark as reduced, "
              f"{result['relative_none']} are not relative clauses in gold")
        s = t["relative/target"]
        print(f"  recall on those with a noun subject and an ordinary head: {s.found}/{s.references} = "
              f"{s.recall:.0%} {ci(s.found, s.references)}")
    else:
        on_clause, total = result["relative_with_relativizer"], t["relative/tree"].findings
        print(f"  this treebank does not mark relative-clause types; {on_clause} of {total} findings "
              f"sit on a gold relative clause {ci(on_clause, total)}")
    s = t["relative/tree"]
    print(f"  against the same rule on the gold tree: {s.line()}")

    print("\nlong-dependency")
    s = t["dependency/gold"]
    print(f"  findings where gold has a subject or object arc of {DEP_MIN}+ words in the span: "
          f"{s.right}/{s.findings} = {s.precision:.0%} {ci(s.right, s.findings)}; "
          f"{result['dependency_same_pair']} join the same two words as gold")
    s = t["dependency/always"]
    print(f"  recall on sentences with a gold arc of {DEP_ALWAYS}+ words where the rule applies: "
          f"{s.found}/{s.references} = {s.recall:.0%} {ci(s.found, s.references)}")
    s = t["dependency/tree"]
    print(f"  against the same rule on the gold tree: {s.line()}")


def main(argv: list[str]) -> int:
    from readcost import Analyzer, Config

    args = argv[1:]
    genres = None
    if args and args[0] == "--genres":
        genres, args = set(args[1].split(",")), args[2:]
    if not args:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2

    def wanted(meta: dict) -> bool:
        return genres is None or any(f"_{g}_" in meta["doc"] or meta["doc"].startswith(g) for g in genres)

    sentences = (pair for a in args for pair in read_conllu(Path(a)) if wanted(pair[0]))
    report(score(Analyzer(Config()), sentences))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
