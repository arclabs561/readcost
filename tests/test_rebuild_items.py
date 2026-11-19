"""Rebuilding the rated items from their pointers (scripts/rebuild_items.py).

Every fixture is made up; nothing touches the network.
"""

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


rb = _mod("rebuild_items")


def test_git_blob_sha1_is_gits_object_id():
    assert rb.git_blob_sha1(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert rb.git_blob_sha1(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_body_sha256_turns_crlf_into_lf():
    assert rb.body_sha256("a\r\nb\n") == hashlib.sha256(b"a\nb\n").hexdigest()


def test_read_pointers_keeps_the_first_row_of_a_repeated_id(tmp_path):
    p = tmp_path / "sample.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in [
        {"i": 1, "path": "a"}, {"i": 2, "path": "b"}, {"i": 1, "path": "c"}]))
    assert [r["path"] for r in rb.read_pointers(p)] == ["a", "b"]


@pytest.mark.parametrize("row,kind,local", [
    ({"stratum": "md", "repo": "o/r", "path": "docs/x.md", "blob": "ab"}, "blob", "o/r/blobs/ab"),
    ({"stratum": "commit", "repo": "o/r", "path": "commit/cd", "blob": "cd"}, "commit", "o/r/commits/cd.gitmessage"),
    ({"stratum": "pr", "repo": "o/r", "path": "pr/12", "blob": "ef"}, "pr", "o/r/prs/12.md"),
    ({"stratum": "S1", "repo": "o/r", "path": "pr/notes.md", "blob": "01"}, "blob", "o/r/blobs/01"),
])
def test_source_kind_and_local_path(row, kind, local):
    assert rb.source_kind(row) == kind
    assert rb.local_path(row) == local


def test_tasks_group_items_by_stratum_and_text():
    rows = [{"i": k, "stratum": s, "repo": "o/r", "commit": "c", "path": p, "blob": "b" + p}
            for k, (s, p) in enumerate([("code-doc", "a.py"), ("code-ordinary", "a.py"), ("code-doc", "a.py")])]
    tasks = rb.tasks_for(3, rows)
    assert [(t["stratum"], [it["i"] for it in t["items"]]) for t in tasks] == [("code-doc", [0, 2]),
                                                                              ("code-ordinary", [1])]


def test_decoy_words_take_the_run_between_the_offsets():
    toks = [["The", "DET", True, 0, 3], ["cache", "NOUN", True, 4, 9], ["keeps", "VERB", True, 10, 15],
            ["rows", "NOUN", True, 16, 20], [".", "PUNCT", False, 20, 21]]
    assert rb.decoy_words(toks, 4, 20) == ["cache", "keeps", "rows"]
    assert rb.decoy_words(toks, 5, 20) is None
    assert rb.decoy_words(toks, 16, 9) is None


GOT = {"rule": "stacked-nouns", "message": "m", "excerpt": "e", "sentence": "s", "before": "b", "after": "a"}


def test_item_row_by_round():
    r1 = rb.item_row(1, {"i": 5, "decoy": ""}, GOT)
    assert r1 == {"i": 5, "kind": None, "rule": "stacked-nouns", "message": "m", "primed_excerpt": "e",
                  "blind_excerpt": "e", "sentence": "s", "before": "b", "after": "a", "in_primed": True,
                  "in_blind": True}
    assert rb.item_row(2, {"i": 5, "item": "near", "kind": "commit message"}, GOT)["kind"] == "commit message"
    ranked = rb.item_row(3, {"i": 5, "item": "ranked", "kind": "k"},
                         GOT | {"rule": None, "message": None, "excerpt": "s"})
    assert (ranked["rule"], ranked["message"], ranked["primed_excerpt"], ranked["blind_excerpt"]) == \
        (None, None, None, "s")
    assert (ranked["in_primed"], ranked["in_blind"]) == (False, True)
    assert list(r1) == list(rb.FIELDS)


def test_compare_counts_exact_items_and_differing_fields():
    ref = [{"i": 1, "rule": "x", "sentence": "a"}, {"i": 2, "rule": "x", "sentence": "b"},
           {"i": 3, "rule": "y", "sentence": "c"}]
    ours = [{"i": 1, "rule": "x", "sentence": "a"}, {"i": 2, "rule": "x", "sentence": "B"},
            {"i": 4, "rule": "y", "sentence": "d"}]
    res = rb.compare(ours, ref, fields=("i", "rule", "sentence"))
    assert res["exact"] == 1
    assert res["missing"] == [3] and res["extra"] == [4]
    assert res["fields"] == {"sentence": [2]}


def test_write_gz_is_byte_stable_and_reads_back(tmp_path):
    rows = [{"i": 1, "sentence": "café"}]
    a, b = tmp_path / "a.jsonl.gz", tmp_path / "b.jsonl.gz"
    rb.write_gz(a, rows)
    rb.write_gz(b, rows)
    assert a.read_bytes() == b.read_bytes()
    assert rb.read_gz(a) == rows
    assert gzip.decompress(a.read_bytes()).decode() == '{"i": 1, "sentence": "café"}\n'


def test_why_not_fetched():
    assert rb.why_not_fetched("fatal: could not read Username for 'https://github.com'") == \
        "repository gone (deleted or private)"
    assert rb.why_not_fetched("error: Server does not allow request for unadvertised object 0a") == \
        "commit no longer on GitHub (history rewritten)"


class FakeSearch:
    """Answers the issue search with fixed items; the REST fallback finds nothing."""

    def __init__(self, items):
        self.items, self.urls = items, []

    def get(self, url, spaced=True):
        self.urls.append(url)
        if "/search/issues" in url:
            return {"items": self.items}
        raise FileNotFoundError("HTTP 404")


def test_fetch_prs_checks_each_body_against_its_pointer(tmp_path):
    same, edited = "Fixes the cache.\r\nNo other change.\r\n", "Fixes the cache."
    rows = [{"i": 1, "stratum": "pr", "repo": "o/r", "path": "pr/7", "blob": rb.body_sha256(same)},
            {"i": 2, "stratum": "pr", "repo": "o/r", "path": "pr/8", "blob": rb.body_sha256("old text")},
            {"i": 3, "stratum": "pr", "repo": "o/r", "path": "pr/9", "blob": "00"}]
    search = FakeSearch([{"number": 7, "body": same}, {"number": 8, "body": edited}])
    bad = rb.fetch_prs(tmp_path, "o/r", rows, search)
    assert bad == {2: "pull request body changed since the draw", 3: "pull request not found"}
    assert (tmp_path / "files/o/r/prs/7.md").read_bytes() == same.replace("\r\n", "\n").encode()
    assert not (tmp_path / "files/o/r/prs/8.md").exists()
    assert "created%3A2026-11-01..2026-11-19" in search.urls[0]


TEXT = """# Notes

The configuration file parser error recovery path skips the rest of the line. It
then reads the next key, which keeps one bad entry from hiding the others.
Each entry names a key and a value, and the parser checks both before it stores them.
A short line ends the list.
"""


@pytest.mark.parametrize("rnd", [2, 3])
def test_rebuild_task_regenerates_items_from_offsets(tmp_path, rnd):
    """A finding, a decoy and (round 3) a ranked sentence come back with the draw's fields."""
    from readcost.extract import extract

    files = tmp_path / "files"
    (files / "o/r/blobs").mkdir(parents=True)
    (files / "o/r/blobs/b").write_text(TEXT)
    stratum = "md" if rnd == 2 else "explanation"
    an = rb._analyzer(rnd, stratum)
    import breadth_precision as bp
    res = an.check_text(TEXT, None, "docs/notes.md", lines=bp.ALL_LINES)
    f = next(f for f in res.findings if f.feature == "stacked-nouns" and f.start is not None)
    seg = next(iter(extract(TEXT, "docs/notes.md", None, comments=an.cfg.comments)))
    sent = list(an.nlp(seg.text).sents)[-2]
    ss, se = seg.span(sent.start_char, sent.end_char)
    toks = [t for t in sent if t.is_alpha]
    a, b = seg.span(toks[1].idx, toks[1].idx + len(toks[1].text)), seg.span(toks[2].idx, toks[2].idx + len(toks[2].text))
    base = {"repo": "o/r", "commit": "c", "path": "docs/notes.md", "blob": "b", "stratum": stratum}
    items = [base | {"i": 1, "item": "finding", "rule": "stacked-nouns", "start": f.start, "end": f.end,
                     "sentence_start": f.sentence_start, "sentence_end": f.sentence_end},
             base | {"i": 2, "item": "decoy", "rule": "inline-list", "start": a[0], "end": b[1],
                     "sentence_start": ss, "sentence_end": se}]
    if rnd == 3:
        items.append(base | {"i": 3, "item": "ranked", "rule": "", "start": ss, "end": se,
                             "sentence_start": ss, "sentence_end": se})
    task = rb.tasks_for(rnd, items)[0] | {"files": str(files)}
    got = {g["i"]: g for g in rb.rebuild_task(task)}
    assert not any("error" in g for g in got.values()), got
    assert (got[1]["message"], got[1]["excerpt"], got[1]["sentence"]) == (f.message, f.excerpt, f.sentence)
    assert got[1]["before"] == "# Notes"
    assert got[2]["message"] == "4 items listed in one sentence"
    assert got[2]["excerpt"] == TEXT[a[0]:b[1]] == f"{toks[1].text} {toks[2].text}"
    assert got[2]["sentence"].startswith("Each entry names")
    if rnd == 3:
        assert got[3]["excerpt"] == got[3]["sentence"] == got[2]["sentence"]
        assert got[3]["rule"] is None


def test_rebuild_task_reports_offsets_readcost_does_not_give(tmp_path):
    files = tmp_path / "files"
    (files / "o/r/blobs").mkdir(parents=True)
    (files / "o/r/blobs/b").write_text(TEXT)
    item = {"i": 9, "item": "finding", "rule": "stacked-nouns", "repo": "o/r", "commit": "c", "path": "a.md",
            "blob": "b", "stratum": "md", "start": 0, "end": 3, "sentence_start": 0, "sentence_end": 7}
    got = rb.rebuild_task(rb.tasks_for(2, [item])[0] | {"files": str(files)})
    assert got == [{"i": 9, "error": "readcost gave no finding at these offsets"}]
