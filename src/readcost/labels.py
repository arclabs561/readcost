"""Labels on findings: a JSONL format, agreement between raters, and blind sheets.

A label is one rater's judgment of one finding. The finding is named by the
document, the version of the document, the character offsets of the flagged
words and the rule, so a label can be laid over the text again without
running readcost. docs/labels.md describes the format and the study it is
for.

Nothing here needs the parser: reading, writing, agreement and the legacy
converter work on files alone. ``sample`` and ``sheet_rows`` take findings
that ``readcost check`` produced.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Iterable

LABELS = ("correct", "defensible", "wrong")
RATER_KINDS = ("human", "model")
LEGACY = {"c": "correct", "d": "defensible", "w": "wrong"}
# The rubric the model raters saw (scripts/second_rater.py), so that people
# and models judge by the same words.
RUBRIC_VERSION = "rubric-1"
RUBRIC = """Each row is a finding from a prose linter: it says that a sentence contains a construction
that may slow readers down. Judge each finding on its own, as an experienced technical editor would.

label:
- correct: the construction is really there and it is a real reading cost an editor would fix.
- defensible: the construction is there and an editor might reasonably flag it, but fixing it is
  optional or the author's choice is fine.
- wrong: the construction is not really there (misparse, wrong definition), or it is there but costs
  the reader nothing (a fixed phrase, a term of art, an idiom, an ordinary verb).

present: yes if the construction the rule names is actually in the sentence, judged by the rule's
definition and apart from whether it costs the reader; else no.

cause: a few words on why (under 8)."""
DEFINITIONS = {
    "stacked-nouns": 'three or more nouns in a row used as one noun phrase ("source segment rebuilds")',
    "long-dependency": "related words (subject and verb, verb and object) far apart in the sentence",
    "inanimate-subject": 'a thing as subject of a verb that normally needs a person ("the file decides")',
    "reduced-object-relative": 'an object relative clause without "that" ("the format the reader expects")',
    "hyphen-compound": 'an ad hoc hyphenated noun-noun compound used as a modifier ("storage-shrink use case")',
    "inline-list": "four or more coordinated items, or slash-joined items, inside one sentence",
    "center-embedding": "a clause nested inside another clause that is itself in the middle of a larger clause "
                        '("the reporter who the senator who John met attacked")',
    "undefined-acronym": "an acronym used before, or without, being spelled out in the document",
}
OPEN, CLOSE = "[[", "]]"  # around the flagged words in a sheet's sentence
SHEET_COLUMNS = ("item", "rule", "definition", "sentence", "span", "label", "present", "cause")
KEY_FIELDS = ("item", "doc", "doc_version", "start", "end", "rule", "text")


@dataclass(frozen=True)
class Label:
    """One rater's judgment of one finding; one line of a labels file."""

    label: str                       # correct | defensible | wrong
    rater: str                       # who: a person's handle or a model id
    rater_kind: str                  # human | model
    doc: str | None = None           # document id: a path or URL
    doc_version: str | None = None   # "git:<commit>" or "sha256:<hash of the file's bytes>"
    start: int | None = None         # character offsets of the flagged words in the document
    end: int | None = None
    rule: str | None = None
    present: bool | None = None      # is the construction there at all
    cause: str = ""
    prompt_version: str = ""         # the rubric or prompt the rater saw
    date: str | None = None          # ISO date the label was made
    text: str = ""                   # document[start:end], to check the offsets against
    finding: str = ""                # key of an older label file, for labels without a span

    def item(self) -> tuple:
        """What was judged; labels with the same item are about the same finding."""
        if self.start is None:
            return ("finding", self.finding)
        return (self.doc, self.doc_version, self.start, self.end, self.rule)


def validate(label: Label) -> None:
    """Raise ValueError when a label does not follow the format."""
    if label.label not in LABELS:
        raise ValueError(f"label {label.label!r} is not one of {', '.join(LABELS)}")
    if label.rater_kind not in RATER_KINDS:
        raise ValueError(f"rater_kind {label.rater_kind!r} is not one of {', '.join(RATER_KINDS)}")
    if not label.rater:
        raise ValueError("rater is empty")
    if label.present is not None and not isinstance(label.present, bool):
        raise ValueError(f"present {label.present!r} is not true, false or null")
    if (label.start is None) != (label.end is None):
        raise ValueError("start and end must both be set or both be null")
    if label.start is None:
        if not label.finding:
            raise ValueError("a label needs start and end, or the finding key of an older label file")
        return
    if not (isinstance(label.start, int) and isinstance(label.end, int) and 0 <= label.start < label.end):
        raise ValueError(f"start {label.start!r} and end {label.end!r} are not a character range")
    if not label.doc or not label.rule:
        raise ValueError("a label with offsets needs doc and rule")
    if label.text and len(label.text) != label.end - label.start:
        raise ValueError(f"text has {len(label.text)} characters; start and end span {label.end - label.start}")
    if label.date:
        datetime.date.fromisoformat(label.date[:10])


def loads(text: str, source: str = "<labels>") -> list[Label]:
    """Labels from JSONL text. Unknown keys are an error, so a misspelt field does not pass."""
    names = {f.name for f in fields(Label)}
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("not a JSON object")
            unknown = sorted(set(row) - names)
            if unknown:
                raise ValueError(f"unknown field {', '.join(unknown)}")
            label = Label(**row)
            validate(label)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{source}:{n}: {exc}") from None
        out.append(label)
    return out


def json_line(row: dict, *, sort_keys: bool = False) -> str:
    """Keep Unicode prose readable and escape surrogate-encoded filesystem bytes in JSON."""
    text = json.dumps(row, ensure_ascii=False, sort_keys=sort_keys)
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def dumps(labels: Iterable[Label]) -> str:
    """JSONL, one label per line, without the optional fields that are empty."""
    lines = []
    for label in labels:
        validate(label)
        row = asdict(label)
        for key in ("text", "finding"):
            if not row[key]:
                del row[key]
        lines.append(json_line(row, sort_keys=True))
    return "".join(line + "\n" for line in lines)


def read(path) -> list[Label]:
    return loads(Path(path).read_text(encoding="utf-8"), str(path))


def write(path, labels: Iterable[Label]) -> None:
    Path(path).write_text(dumps(labels), encoding="utf-8")


def check_offsets(labels: Iterable[Label], doc: str, text: str) -> list[str]:
    """Problems laying the labels for ``doc`` over ``text``: ranges outside it, or text that differs."""
    problems = []
    for label in labels:
        if label.doc != doc or label.start is None:
            continue
        if label.end > len(text):
            problems.append(f"{doc}:{label.start}-{label.end}: past the end of the document")
        elif label.text and text[label.start:label.end] != label.text:
            problems.append(f"{doc}:{label.start}-{label.end}: document has "
                            f"{text[label.start:label.end]!r}, label has {label.text!r}")
    return problems


def content_version(data: bytes) -> str:
    """The ``doc_version`` for a file's bytes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------- agreement

def fleiss(table: list[list[int]]) -> dict:
    """Fleiss' kappa for ``table[i][j]``, the number of raters who put item i in category j.

    Every item needs the same number of ratings, two or more. Chance
    agreement comes from the category frequencies over all ratings, so a
    skewed label set lowers kappa as it should. Returns kappa, the observed
    and chance agreement, and those frequencies. Kappa is None when every
    rating is in one category, where it is undefined.
    """
    if not table:
        raise ValueError("no items")
    n = sum(table[0])
    if n < 2 or any(sum(row) != n for row in table):
        raise ValueError("every item needs the same number of ratings, at least two")
    items = len(table)
    freq = [sum(row[j] for row in table) / (items * n) for j in range(len(table[0]))]
    observed = sum((sum(c * c for c in row) - n) / (n * (n - 1)) for row in table) / items
    chance = sum(p * p for p in freq)
    kappa = None if chance >= 1 else (observed - chance) / (1 - chance)
    return {"kappa": kappa, "observed": observed, "chance": chance, "frequencies": freq,
            "items": items, "raters": n}


def cohen(a: list, b: list) -> float | None:
    """Cohen's kappa for two raters' labels of the same items, in the same order."""
    if len(a) != len(b) or not a:
        raise ValueError("two raters need the same items, at least one")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    chance = sum(ca[c] * cb[c] for c in ca) / (n * n)
    return None if chance >= 1 else (observed - chance) / (1 - chance)


def majority(votes: Iterable[str]) -> str | None:
    """The label more than half of the votes give, or None."""
    counts = Counter(votes)
    total = sum(counts.values())
    top, n = counts.most_common(1)[0] if counts else (None, 0)
    return top if n > total / 2 else None


def by_item(labels: Iterable[Label]) -> dict[tuple, dict[str, Label]]:
    """item -> rater -> label. A rater's later label for an item replaces the earlier one."""
    out: dict[tuple, dict[str, Label]] = {}
    for label in labels:
        out.setdefault(label.item(), {})[label.rater] = label
    return out


def _merge(value: str, accepted: bool) -> str:
    return ("accepted" if value != "wrong" else "wrong") if accepted else value


def agreement(labels: Iterable[Label], *, accepted: bool = False, field: str = "label") -> dict:
    """Agreement among the raters on the items all of them labelled.

    ``accepted`` merges correct and defensible, which is how the evaluation
    counts a finding as right. ``field`` is "label" or "present". Returns
    Fleiss' kappa with its parts, Cohen's kappa per pair of raters, each
    rater's counts, and the majority vote counts.
    """
    items = by_item(labels)
    raters = sorted({r for votes in items.values() for r in votes})

    def value(label: Label):
        if field == "present":
            return label.present
        return _merge(label.label, accepted)

    shared = [votes for votes in items.values()
              if len(votes) == len(raters) and all(value(v) is not None for v in votes.values())]
    out: dict = {"raters": raters, "items": len(shared), "items_not_shared": len(items) - len(shared)}
    if len(raters) < 2 or not shared:
        return out
    cats = sorted({value(v) for votes in shared for v in votes.values()}, key=str)
    table = [[sum(value(v) == c for v in votes.values()) for c in cats] for votes in shared]
    f = fleiss(table)
    out["categories"] = [str(c) for c in cats]
    out["fleiss"] = {k: f[k] for k in ("kappa", "observed", "chance")}
    out["frequencies"] = dict(zip(out["categories"], f["frequencies"]))
    out["pairwise"] = {f"{a} | {b}": cohen([value(v[a]) for v in shared], [value(v[b]) for v in shared])
                       for i, a in enumerate(raters) for b in raters[i + 1:]}
    out["per_rater"] = {r: dict(Counter(str(value(v[r])) for v in shared)) for r in raters}
    votes = Counter(str(majority(value(v) for v in item.values())) for item in shared)
    out["majority"] = {("no majority" if k == "None" else k): n for k, n in sorted(votes.items())}
    return out


# --------------------------------------------------------------- older label files

def convert_legacy(path, *, sample: dict[str, dict] | None = None, date: str | None = None,
                   prompt_version: str = RUBRIC_VERSION) -> list[Label]:
    """Labels from an ``eval/labels/NAME.json`` file of readcost 0.3 and earlier.

    Those files key each label by a hash of (text id, rule, sentence) and
    hold the label, ``present`` and ``cause``. The hash cannot be undone, so
    without more the result has no document, rule or offsets, only the hash
    as ``finding``. ``sample`` maps a hash to the sampled finding (see
    ``legacy_sample``) and fills the document id and the rule. Offsets are
    not in either file.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for key, row in data["labels"].items():
        found = (sample or {}).get(key, {})
        out.append(Label(label=LEGACY[row["label"]], rater=path.stem, rater_kind="model",
                         doc=found.get("id"), rule=found.get("feature"), present=row.get("present"),
                         cause=row.get("cause", ""), prompt_version=prompt_version, date=date, finding=key))
    return out


def legacy_key(text_id: str, rule: str, sentence: str) -> str:
    """The key of an older label file (scripts/eval_report.py)."""
    return hashlib.sha256(f"{text_id}\t{rule}\t{sentence}".encode()).hexdigest()[:16]


def legacy_sample(path) -> dict[str, dict]:
    """Key -> finding for a ``sample.jsonl`` of the evaluation corpus (rows with id, feature, sentence)."""
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return {legacy_key(r["id"], r["feature"], r["sentence"]): r for r in rows}


# --------------------------------------------------------------- sheets for raters

def definition(rule: str) -> str:
    """The rule in the words the raters' rubric uses; the rule's title for a rule the rubric lacks."""
    if rule in DEFINITIONS:
        return DEFINITIONS[rule]
    from .features import FEATURES

    f = FEATURES.get(rule)
    if not f:
        return rule
    return f.title[:1].lower() + f.title[1:] + (f' ("{f.bad}")' if f.bad else "")


def sample(findings: list, n: int, seed: int = 0) -> list:
    """Up to ``n`` findings that have offsets, the same number per rule as far as the rules allow.

    Rules take turns, so a rare rule is not crowded out by a common one.
    The result is shuffled; the same seed gives the same sample.
    """
    rng = random.Random(seed)
    by_rule: dict[str, list] = {}
    for f in findings:
        if f.start is not None:
            by_rule.setdefault(f.feature, []).append(f)
    for group in by_rule.values():
        rng.shuffle(group)
    picked = []
    while len(picked) < n and any(by_rule.values()):
        for rule in sorted(by_rule):
            if by_rule[rule] and len(picked) < n:
                picked.append(by_rule[rule].pop())
    rng.shuffle(picked)
    return picked


def _item_id(doc: str, version: str, start: int, end: int, rule: str) -> str:
    return hashlib.sha256(f"{doc}\t{version}\t{start}\t{end}\t{rule}".encode("utf-8", "surrogateescape")).hexdigest()[:12]


def marked_sentence(source: str, f) -> str:
    """The finding's sentence as it is in the source, on one line, with [[ ]] around the flagged words."""
    lo = f.sentence_start if f.sentence_start is not None else f.start
    hi = f.sentence_end if f.sentence_end is not None else f.end
    lo, hi = min(lo, f.start), max(hi, f.end)
    text = source[lo:f.start] + OPEN + source[f.start:f.end] + CLOSE + source[f.end:hi]
    return " ".join(text.split())


def sheet_rows(findings: list, sources: dict[str, str], versions: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """(sheet rows, key rows) for findings with offsets.

    A sheet row is what a rater sees: the rule, its definition, the
    sentence with the flagged words marked, and empty label columns. It
    does not name the document. A key row says where the item is.
    """
    rows, keys = [], []
    for f in findings:
        source, version = sources[f.path], versions[f.path]
        item = _item_id(f.path, version, f.start, f.end, f.feature)
        flagged = source[f.start:f.end]
        rows.append({"item": item, "rule": f.feature, "definition": definition(f.feature),
                     "sentence": marked_sentence(source, f), "span": " ".join(flagged.split()),
                     "label": "", "present": "", "cause": ""})
        keys.append({"item": item, "doc": f.path, "doc_version": version, "start": f.start, "end": f.end,
                     "rule": f.feature, "text": flagged})
    return rows, keys


def _cell(value: str) -> str:
    """A cell a spreadsheet will not run as a formula."""
    return " " + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def dump_sheet(rows: list[dict], fmt: str = "csv") -> str:
    if fmt == "jsonl":
        return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    out = io.StringIO()
    writer = csv.DictWriter(out, SHEET_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({k: _cell(str(r[k])) for k in SHEET_COLUMNS} for r in rows)
    return out.getvalue()


def load_sheet(text: str) -> list[dict]:
    """Rows of a filled sheet, CSV or JSONL (told apart by the first character)."""
    text = text.lstrip("﻿")  # spreadsheets add a byte order mark
    if text.lstrip().startswith("{"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return list(csv.DictReader(io.StringIO(text, newline="")))


_YES = {"yes": True, "y": True, "true": True, "1": True, "no": False, "n": False, "false": False, "0": False}


def read_sheet(text: str, keys: list[dict], *, rater: str, rater_kind: str = "human",
               prompt_version: str = RUBRIC_VERSION, date: str | None = None) -> tuple[list[Label], list[str]]:
    """Labels from a filled sheet, and the rows that could not be read.

    A label may be written out or as its first letter, in any case.
    ``present`` takes yes or no (also y, n, true, false, 1, 0, or a JSON
    boolean). A row with no label is reported and skipped, so a half-done
    sheet can be read.
    """
    by_key = {k["item"]: k for k in keys}
    short = {name[0]: name for name in LABELS} | {name: name for name in LABELS}
    date = date or datetime.date.today().isoformat()
    labels, problems = [], []
    for n, row in enumerate(load_sheet(text), 2):
        item = str(row.get("item", "")).strip()
        where = f"row {n} (item {item or '?'})"
        key = by_key.get(item)
        if key is None:
            problems.append(f"{where}: not in the key file")
            continue
        value = str(row.get("label") or "").strip().lower()
        if not value:
            problems.append(f"{where}: no label")
            continue
        if value not in short:
            problems.append(f"{where}: label {value!r} is not one of {', '.join(LABELS)}")
            continue
        raw = row.get("present")
        present = raw if isinstance(raw, bool) else _YES.get(str(raw or "").strip().lower())
        if present is None and str(raw or "").strip():
            problems.append(f"{where}: present {raw!r} is not yes or no")
            continue
        labels.append(Label(label=short[value], rater=rater, rater_kind=rater_kind, doc=key["doc"],
                            doc_version=key["doc_version"], start=key["start"], end=key["end"],
                            rule=key["rule"], present=present, cause=str(row.get("cause") or "").strip(),
                            prompt_version=prompt_version, date=date, text=key.get("text", "")))
    return labels, problems
