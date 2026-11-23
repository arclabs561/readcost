"""The labels file format, agreement between raters, the legacy converter and rater sheets."""

import csv
import io
import json
import os
from pathlib import Path

import pytest

from readcost import labels
from readcost.cli import main
from readcost.labels import Label

ROOT = Path(__file__).resolve().parent.parent


def make(rater="ana", label="wrong", start=10, **kw) -> Label:
    base = dict(label=label, rater=rater, rater_kind="human", doc="docs/a.md", doc_version="git:abc123",
                start=start, end=None if start is None else start + 5, rule="stacked-nouns", present=True, cause="a name",
                prompt_version="rubric-1", date="2026-11-18")
    return Label(**(base | kw))


# ----------------------------------------------------------- the file format

def test_round_trip_keeps_every_field_and_non_ascii():
    one = make(cause="naïve café", text="abcde")
    old = Label(label="correct", rater="m", rater_kind="model", finding="01973d86d4e3bd3d")
    text = labels.dumps([one, old])
    assert text.count("\n") == 2 and "naïve café" in text
    assert labels.loads(text) == [one, old]
    assert "finding" not in json.loads(text.splitlines()[0])


@pytest.mark.parametrize("change, message", [
    (dict(label="maybe"), "label 'maybe'"),
    (dict(rater_kind="robot"), "rater_kind"),
    (dict(rater=""), "rater is empty"),
    (dict(end=None), "both"),
    (dict(start=9, end=9), "character range"),
    (dict(doc=None), "needs doc and rule"),
    (dict(present="yes"), "present"),
    (dict(text="abc"), "3 characters"),
    (dict(date="last week"), "Invalid isoformat"),
    (dict(start=None), "finding key"),
])
def test_validate_names_the_problem(change, message):
    with pytest.raises(ValueError, match=message):
        labels.validate(make(**change))


def test_loads_reports_file_and_line_and_rejects_unknown_fields():
    good = labels.dumps([make()])
    with pytest.raises(ValueError, match=r"x\.jsonl:2: unknown field ratter"):
        labels.loads(good + json.dumps({"label": "wrong", "ratter": "a"}) + "\n", "x.jsonl")
    with pytest.raises(ValueError, match=r"<labels>:1: "):
        labels.loads("not json\n")


def test_check_offsets_lays_labels_over_the_text():
    text = "The naïve café index rebuild job failed."
    start = text.index("index")
    ok = make(doc="a.md", start=start, end=start + 17, text="index rebuild job")
    moved = make(doc="a.md", start=start + 1, end=start + 18, text="index rebuild job")
    beyond = make(doc="a.md", start=100, end=105)
    other = make(doc="b.md", start=500, end=505)
    problems = labels.check_offsets([ok, moved, beyond, other], "a.md", text)
    assert len(problems) == 2 and "document has 'ndex rebuild job '" in problems[0] and "past the end" in problems[1]


# ----------------------------------------------------------- agreement

def test_fleiss_matches_the_textbook_example():
    # Fleiss 1971 as given on Wikipedia: 10 items, 14 raters, 5 categories.
    table = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
             [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    f = labels.fleiss(table)
    assert round(f["kappa"], 3) == 0.210
    assert round(f["observed"], 3) == 0.378 and round(f["chance"], 3) == 0.213
    assert [round(p, 3) for p in f["frequencies"]] == [0.143, 0.2, 0.279, 0.15, 0.229]


def test_fleiss_uses_category_frequencies_for_skewed_labels():
    # 18 of 20 items unanimous "wrong", two split 2 to 1: raw agreement is
    # high, and a chance level fixed at 0.5 would report 0.87.
    table = [[0, 3]] * 18 + [[1, 2], [2, 1]]
    f = labels.fleiss(table)
    assert round(f["observed"], 3) == 0.933 and round(f["chance"], 3) == 0.905
    assert round(f["kappa"], 3) == 0.298


def test_fleiss_edge_cases():
    assert labels.fleiss([[3, 0], [3, 0]])["kappa"] is None  # one category: undefined
    with pytest.raises(ValueError, match="same number of ratings"):
        labels.fleiss([[3, 0], [2, 0]])
    with pytest.raises(ValueError, match="no items"):
        labels.fleiss([])


def test_cohen_kappa():
    a = ["w"] * 20 + ["c"] * 5 + ["w"] * 10 + ["c"] * 15
    b = ["w"] * 20 + ["w"] * 5 + ["c"] * 10 + ["c"] * 15
    assert round(labels.cohen(a, b), 3) == 0.4  # observed 0.7, chance 0.5
    assert labels.cohen(["w", "c"], ["w", "c"]) == 1.0
    assert labels.cohen(["w", "w"], ["w", "w"]) is None
    with pytest.raises(ValueError):
        labels.cohen(["w"], ["w", "c"])


def test_majority_needs_more_than_half():
    assert labels.majority(["wrong", "wrong", "correct"]) == "wrong"
    assert labels.majority(["wrong", "correct"]) is None
    assert labels.majority(["wrong", "correct", "defensible"]) is None
    assert labels.majority([]) is None


def test_agreement_over_three_raters():
    votes = {10: "www", 20: "wwc", 30: "ccd", 40: "ddw", 50: "www"}
    found = [make(rater, {"w": "wrong", "c": "correct", "d": "defensible"}[v], start,
                  present=v != "w")
             for start, row in votes.items() for rater, v in zip(("ana", "bo", "cy"), row)]
    found.append(make("ana", "wrong", 60))  # only one rater: left out
    rep = labels.agreement(found)
    assert rep["raters"] == ["ana", "bo", "cy"] and rep["items"] == 5 and rep["items_not_shared"] == 1
    assert rep["majority"] == {"correct": 1, "defensible": 1, "wrong": 3}
    assert set(rep["pairwise"]) == {"ana | bo", "ana | cy", "bo | cy"}
    assert rep["per_rater"]["cy"] == {"wrong": 3, "correct": 1, "defensible": 1}
    assert abs(sum(rep["frequencies"].values()) - 1) < 1e-9
    merged = labels.agreement(found, accepted=True)
    assert merged["categories"] == ["accepted", "wrong"]
    assert merged["majority"] == {"accepted": 2, "wrong": 3}
    assert merged["fleiss"]["kappa"] > rep["fleiss"]["kappa"]
    present = labels.agreement(found, field="present")
    assert present["categories"] == ["False", "True"] and present["items"] == 5


def test_agreement_with_one_rater_reports_no_kappa():
    rep = labels.agreement([make()])
    assert rep["items"] == 1 and "fleiss" not in rep


def test_a_later_label_replaces_an_earlier_one_by_the_same_rater():
    found = [make("ana", "wrong"), make("ana", "correct"), make("bo", "correct")]
    assert labels.agreement(found)["majority"] == {"correct": 1}


# ----------------------------------------------------------- older label files

LENIENT = {"meta-llama--llama-4-maverick", "minimax--minimax-m3"}


def test_converted_repository_labels_reproduce_the_published_kappa():
    found = [x for p in sorted((ROOT / "eval" / "labels").glob("*.json"))
             if p.name != "raters.json" for x in labels.convert_legacy(p)]
    assert len(found) == 2100 and {x.rater_kind for x in found} == {"model"}
    assert all(x.start is None and x.doc is None and x.rule is None and x.finding for x in found)
    assert labels.loads(labels.dumps(found)) == found
    ten = labels.agreement(found)
    assert ten["items"] == 210 and round(ten["fleiss"]["kappa"], 2) == 0.23       # docs/evaluation.md, "Ten raters"
    eight = labels.agreement([x for x in found if x.rater not in LENIENT])
    assert round(eight["fleiss"]["kappa"], 3) == 0.401
    assert round(eight["fleiss"]["chance"], 3) == 0.719 and round(eight["fleiss"]["observed"], 3) == 0.832
    # scripts/rater_agreement.py over all ten: 26 accepted by more than half, 2 of them called correct.
    assert ten["majority"]["correct"] == 2
    assert labels.agreement(found, accepted=True)["majority"] == {"accepted": 26, "no majority": 14, "wrong": 170}
    assert round(eight["pairwise"]["claude-opus | codex-gpt-6.1-sol"], 2) == 0.41  # "Second rater"


def test_convert_fills_document_and_rule_from_the_sample(tmp_path):
    rows = [{"id": "essays/a", "feature": "stacked-nouns", "sentence": "One two three four."},
            {"id": "docs/b", "feature": "inline-list", "sentence": "A, b, c and d."}]
    (tmp_path / "sample.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    keys = [labels.legacy_key(r["id"], r["feature"], r["sentence"]) for r in rows]
    (tmp_path / "some-model.json").write_text(json.dumps({"rater": "a model", "labels": {
        keys[0]: {"label": "c", "present": True, "cause": "real stack"},
        keys[1]: {"label": "w", "present": False, "cause": ""},
        "ffffffffffffffff": {"label": "d", "present": True, "cause": "not in the sample"}}}))
    out = tmp_path / "out.jsonl"
    assert main(["label", "convert", str(tmp_path / "some-model.json"), "--sample", str(tmp_path / "sample.jsonl"),
                 "--date", "2026-10-26", "-o", str(out)]) == 0
    a, b, c = labels.read(out)
    assert (a.doc, a.rule, a.label, a.rater, a.date) == ("essays/a", "stacked-nouns", "correct", "some-model", "2026-10-26")
    assert (b.doc, b.rule, b.label, b.present) == ("docs/b", "inline-list", "wrong", False)
    assert c.doc is None and c.rule is None and c.label == "defensible"
    assert a.start is None and a.finding == keys[0]


# ----------------------------------------------------------- sheets

DOC = """# Notes

Every write ends up forcing source segment rebuilds, which nobody in the team wanted.

It does not own indexing or compaction, and the format the reader expects is odd.

The *storage-shrink* use case, which the [index team](https://example.com) built
for `foo()` &amp; friends, came first.

=SUM(A1) is the formula the reader expects in every report.

The index, built once from all documents and rebuilt only on compaction, serves queries.

It supports standard/Sugeno/Yager negations, OWA, power means, and uninorms.
"""


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    d = tmp_path_factory.mktemp("sheet")
    (d / "a.md").write_text(DOC, encoding="utf-8")
    assert main(["label", "export", str(d / "a.md"), "-o", str(d / "sheet.csv"), "-n", "50", "--seed", "3"]) == 0
    return d


def test_export_writes_a_blind_sheet_and_a_key(exported):
    text = (exported / "sheet.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    keys = [json.loads(line) for line in (exported / "sheet.key.jsonl").read_text().splitlines()]
    assert len(rows) == len(keys) >= 5 and [r["item"] for r in rows] == [k["item"] for k in keys]
    assert tuple(rows[0]) == labels.SHEET_COLUMNS
    assert "a.md" not in text  # the sheet does not say where a sentence is from
    for row, key in zip(rows, keys):
        assert key["doc"].endswith("a.md") and key["doc_version"].startswith("sha256:")
        assert DOC[key["start"]:key["end"]] == key["text"]
        assert row["label"] == row["present"] == row["cause"] == ""
        assert row["definition"] == labels.definition(row["rule"]) and row["rule"] == key["rule"]
        inner = row["sentence"].split("[[")[1].split("]]")[0]
        assert inner == row["span"] == " ".join(key["text"].split())
    stack = next(r for r in rows if r["span"] == "source segment rebuilds")
    assert stack["sentence"] == ("Every write ends up forcing [[source segment rebuilds]], "
                                 "which nobody in the team wanted.")
    assert labels.content_version(DOC.encode()) == keys[0]["doc_version"]


def test_sheet_keeps_source_markup_and_cannot_start_a_formula(exported):
    rows = list(csv.DictReader(io.StringIO((exported / "sheet.csv").read_text(encoding="utf-8"))))
    wrapped = next(r for r in rows if r["rule"] == "hyphen-compound")
    assert wrapped["sentence"].startswith("The *[[storage-shrink* use case]], which the [index team]")
    assert not any(v and v[0] in "=+-@" for r in rows for v in r.values())
    assert any(r["sentence"].startswith(" =SUM(A1)") for r in rows)


def test_same_seed_gives_the_same_sheet_and_n_limits_it(exported, tmp_path):
    again = tmp_path / "again.csv"
    assert main(["label", "export", str(exported / "a.md"), "-o", str(again), "-n", "50", "--seed", "3"]) == 0
    assert again.read_text() == (exported / "sheet.csv").read_text()
    small = tmp_path / "small.jsonl"
    assert main(["label", "export", str(exported / "a.md"), "-o", str(small), "-n", "2", "--commit", "abc123"]) == 0
    rows = [json.loads(line) for line in small.read_text().splitlines()]
    assert len(rows) == 2 and len({r["rule"] for r in rows}) == 2  # rules take turns
    assert json.loads((tmp_path / "small.key.jsonl").read_text().splitlines()[0])["doc_version"] == "git:abc123"


def fill(sheet: Path, out: Path, answers) -> None:
    rows = list(csv.DictReader(io.StringIO(sheet.read_text(encoding="utf-8"))))
    for row, (label, present, cause) in zip(rows, answers):
        row["label"], row["present"], row["cause"] = label, present, cause
    buf = io.StringIO()
    writer = csv.DictWriter(buf, labels.SHEET_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    out.write_text("﻿" + buf.getvalue().replace("\n", "\r\n"), encoding="utf-8")  # as a spreadsheet saves it


def test_import_reads_filled_sheets_and_agreement_runs_on_them(exported, tmp_path, capsys):
    n = len((exported / "sheet.key.jsonl").read_text().splitlines())
    out = tmp_path / "labels.jsonl"
    key = str(exported / "sheet.key.jsonl")
    answers = {
        "ana": [("wrong", "no", "a term")] * n,
        "bo": [("W", "No", "")] * (n - 1) + [("c", "yes", "real cost")],
        "cy": [("Defensible", "Y", "optional")] + [("wrong", "false", "")] * (n - 1),
    }
    for rater, rows in answers.items():
        filled = tmp_path / f"{rater}.csv"
        fill(exported / "sheet.csv", filled, rows)
        assert main(["label", "import", str(filled), "--rater", rater, "--key", key, "--date", "2026-11-18",
                     "-o", str(out)]) == 0
    found = labels.read(out)
    assert len(found) == 3 * n and {x.rater_kind for x in found} == {"human"}
    assert {x.prompt_version for x in found} == {"rubric-1"} and {x.date for x in found} == {"2026-11-18"}
    assert not labels.check_offsets(found, found[0].doc, DOC)
    bo = [x for x in found if x.rater == "bo"]
    assert [x.label for x in bo] == ["wrong"] * (n - 1) + ["correct"] and bo[-1].present is True and bo[0].present is False
    capsys.readouterr()
    assert main(["label", "agreement", str(out)]) == 0
    shown = capsys.readouterr().out
    assert f"3 raters, {n} items labelled by all of them" in shown and "Fleiss' kappa" in shown
    assert "ana | bo" in shown and "majority vote" in shown
    assert main(["label", "agreement", str(out), "-o", "json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["label"]["majority"]["wrong"] == n and rep["label"]["items"] == n


def test_import_reports_rows_it_cannot_read(exported, tmp_path, capsys):
    n = len((exported / "sheet.key.jsonl").read_text().splitlines())
    filled = tmp_path / "half.csv"
    fill(exported / "sheet.csv", filled, [("wrong", "", "")] + [("", "", "")] + [("perhaps", "yes", "")]
         + [("c", "sometimes", "")] + [("d", "yes", "")] * (n - 4))
    (tmp_path / "half.key.jsonl").write_text(
        "".join((exported / "sheet.key.jsonl").read_text().splitlines(keepends=True)[:-1]))
    out = tmp_path / "labels.jsonl"
    assert main(["label", "import", str(filled), "--rater", "ana", "-o", str(out)]) == 0
    err = capsys.readouterr().err
    assert "row 3" in err and "no label" in err and "'perhaps'" in err and "'sometimes'" in err
    assert "not in the key file" in err
    found = labels.read(out)
    assert len(found) == n - 4 and found[0].present is None


def test_jsonl_sheet_round_trip():
    keys = [{"item": "abc", "doc": "a.md", "doc_version": "git:1", "start": 3, "end": 8, "rule": "inline-list",
             "text": "abcde"}]
    sheet = json.dumps({"item": "abc", "label": "defensible", "present": True, "cause": "short items"}) + "\n"
    found, problems = labels.read_sheet(sheet, keys, rater="m1", rater_kind="model", prompt_version="p2",
                                        date="2026-11-18")
    assert not problems
    assert found == [Label(label="defensible", rater="m1", rater_kind="model", doc="a.md", doc_version="git:1",
                           start=3, end=8, rule="inline-list", present=True, cause="short items",
                           prompt_version="p2", date="2026-11-18", text="abcde")]


def test_export_without_findings_is_a_usage_error(tmp_path, capsys):
    (tmp_path / "plain.md").write_text("The cat sat on the mat.\n")
    assert main(["label", "export", str(tmp_path / "plain.md"), "-o", str(tmp_path / "s.csv")]) == 2
    assert "no findings" in capsys.readouterr().err


def test_definition_covers_every_rule():
    from readcost.features import FEATURES

    assert all(labels.definition(rule) and labels.definition(rule) != rule for rule in FEATURES)
    assert labels.definition("stacked-nouns").startswith("three or more nouns")

@pytest.mark.skipif(os.name != "posix", reason="requires POSIX filesystem bytes")
def test_label_export_and_import_round_trip_undecodable_filename(tmp_path):
    source = tmp_path / os.fsdecode(b"notes-\xff.md")
    source.write_text(DOC, encoding="utf-8")
    sheet, out = tmp_path / "sheet.jsonl", tmp_path / "ratings.jsonl"
    assert main(["label", "export", str(tmp_path), "-o", str(sheet), "-n", "1"]) == 0
    row = json.loads(sheet.read_text(encoding="utf-8"))
    row["label"] = "correct"
    sheet.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert main(["label", "import", str(sheet), "--rater", "test", "-o", str(out)]) == 0
    [label] = labels.read(out)
    assert os.fsencode(label.doc) == os.fsencode(source)
    assert source.read_text(encoding="utf-8")[label.start:label.end] == label.text
