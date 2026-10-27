"""Commit messages: extraction of prose lines and their own verdict thresholds."""

from readcost import Analyzer, Config
from readcost.engine import COMMIT_ADVISE_COST_INDEX
from readcost.extract import extract_commit

BENCH = """runtime: speed up memmove for unaligned sources

The fast path now handles unaligned sources with wider loads.

name                      old speed     new speed     delta
MemmoveUnalignedSrc/1024  32.0GB/s ± 0% 45.9GB/s ± 2% +43.53%  (p=0.000 n=10)

cd _gen
sed -i 's/ssacore\\./ssa./g' *.rules

Change-Id: I0123456789abcdef
"""


def test_commit_extraction_keeps_prose_and_drops_tables_and_commands():
    text = " ".join(s.text.strip() for s in extract_commit(BENCH, "COMMIT_EDITMSG"))
    assert "fast path now handles unaligned sources" in text
    assert "speed up memmove for unaligned sources" in text
    assert "runtime:" not in text  # scope prefix
    assert "GB/s" not in text and "sed -i" not in text and "Change-Id" not in text


def test_commit_subject_scope_is_not_a_slash_list():
    r = Analyzer(Config()).check_text(
        "net/http/internal/http3: fix the accounting of bytes written by the body writer\n", "commit")
    assert not [f for f in r.findings if f.feature == "inline-list"]


def test_package_path_in_prose_is_not_a_slash_list():
    r = Analyzer(Config()).check_text(
        "With this change the tests in the cmd/compile/internal/ssagen package run faster on my laptop.", "markdown")
    assert not [f for f in r.findings if f.feature == "inline-list"]


DENSE = ("The shard compaction retry budget is fixed. The region index sidecar cache is rebuilt. "
         "The snapshot search cost model is wrong. The source segment rebuild path is slow. "
         "We read the index file once per run and keep it in memory for later use. "
         "The old code read it again for every request, which was slow on large trees. "
         "Now the server starts a little later but answers each request much faster.")


def test_commit_messages_use_their_own_thresholds():
    a = Analyzer(Config())
    prose = a.check_text(DENSE, "markdown")
    commit = a.check_text("Fix the build\n\n" + DENSE, "commit")
    assert prose.cost_index >= Config().advise_cost_index and prose.verdict != "pass"
    assert Config().advise_cost_index <= commit.cost_index < COMMIT_ADVISE_COST_INDEX
    assert commit.verdict == "pass"

