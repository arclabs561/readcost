"""Regression tests for defects found in the 2026-10-26 bug hunt.

Each test names the defect it pins. They exercise the public entry points
(Config, Analyzer, the CLI and the git hook) rather than internals.
"""

import subprocess
import sys

import pytest

from readcost.config import Config
from readcost.engine import Analyzer
from readcost.extract import extract_markdown

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")
PLAIN = "The index stores one list of documents for each term.\n"
HAS_GIT = subprocess.run(["git", "--version"], capture_output=True).returncode == 0


def run_cli(args, stdin=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin,
                          capture_output=True, text=True, cwd=cwd)


@pytest.mark.parametrize("path", [
    "node_modules/pkg/README.md", "vendor/lib/README.md", "target/doc/index.md",
    ".git/COMMIT_EDITMSG", "./node_modules/pkg/README.md", ".venv/lib/notes.md",
])
def test_default_excludes_apply_at_the_top_level(path):
    assert not Config().wants(path)


def test_default_excludes_keep_ordinary_docs():
    assert Config().wants("docs/guide.md") and Config().wants("README.md")


def test_edit_to_a_later_line_of_a_wrapped_sentence_is_checked():
    wrapped = ("The example prints the first snapshot-search cost with\n"
               "persisted region-index sidecars present versus after deleting\n"
               "those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")
    analyzer = Analyzer(Config())
    whole = analyzer.check_text(wrapped, "markdown")
    assert whole.findings, "fixture must produce findings when checked whole"
    only_line_2 = analyzer.check_text(wrapped, "markdown", lines=[(2, 2)])
    assert only_line_2.findings


def test_finding_line_is_the_first_line_of_its_excerpt():
    text = "Each restart triggers source\nsegment rebuilds that slow the first query.\n"
    findings = Analyzer(Config()).check_text(text, "markdown").findings
    stacked = [f for f in findings if f.feature == "stacked-nouns"]
    assert stacked and stacked[0].line == 1


def test_min_severity_does_not_loosen_the_verdict():
    full = Analyzer(Config()).check_text(DENSE, "markdown")
    filtered = Analyzer(Config(min_severity="error")).check_text(DENSE, "markdown")
    assert filtered.verdict == full.verdict


def test_crash_exits_2_not_the_findings_code(tmp_path):
    jsonl = tmp_path / "eval.jsonl"
    jsonl.write_text('{"response": "fine"}\nnull\n')
    proc = run_cli(["check", "--fail-on", "never", str(jsonl)], cwd=tmp_path)
    assert proc.returncode == 2, proc.stderr
    profile = tmp_path / "profile.json"
    profile.write_text("{}")
    proc = run_cli(["check", "--fail-on", "never", "--profile", str(profile), "-"], PLAIN, tmp_path)
    assert proc.returncode == 2, proc.stderr


def _repo(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "readcost.toml").write_text('[readcost.hooks]\nmode = "block"\n')
    return git


def _pre_commit(tmp_path):
    return subprocess.run([sys.executable, "-m", "readcost", "hook", "git", "pre-commit"],
                          capture_output=True, text=True, cwd=tmp_path)


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
@pytest.mark.parametrize("setting", [("color.ui", "always"), ("diff.external", "cat")])
def test_git_pre_commit_ignores_diff_color_and_external_tools(tmp_path, setting):
    git = _repo(tmp_path)
    (tmp_path / "README.md").write_text(PLAIN)
    git("add", ".")
    git("commit", "-qm", "init")
    git("config", *setting)
    (tmp_path / "README.md").write_text(PLAIN + "\n" + DENSE)
    git("add", "README.md")
    proc = _pre_commit(tmp_path)
    assert proc.returncode == 1 and "stacked-nouns" in proc.stderr


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_git_pre_commit_checks_renamed_files(tmp_path):
    git = _repo(tmp_path)
    body = "".join(f"Line {i} of the plain guide stays simple.\n" for i in range(20))
    (tmp_path / "README.md").write_text(body)
    git("add", ".")
    git("commit", "-qm", "init")
    git("mv", "README.md", "GUIDE.md")
    (tmp_path / "GUIDE.md").write_text(body + DENSE)
    git("add", "GUIDE.md")
    proc = _pre_commit(tmp_path)
    assert proc.returncode == 1 and "stacked-nouns" in proc.stderr


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_git_pre_commit_survives_a_non_utf8_staged_file(tmp_path):
    git = _repo(tmp_path)
    (tmp_path / "README.md").write_text(PLAIN)
    git("add", ".")
    git("commit", "-qm", "init")
    (tmp_path / "README.md").write_text(PLAIN + "\n" + DENSE)
    (tmp_path / "notes.txt").write_bytes("caf\xe9 au lait\n".encode("latin-1"))
    git("add", "README.md", "notes.txt")
    proc = _pre_commit(tmp_path)
    assert proc.returncode == 1 and "stacked-nouns" in proc.stderr


# --------------------------------------------------------------- batch B

def _findings(text, feature=None, **cfg):
    found = Analyzer(Config(**cfg)).check_text(text, "markdown").findings
    return [f for f in found if feature is None or f.feature == feature]


def test_allow_listed_terms_stay_whole_inside_longer_compounds():
    assert not _findings("The write-ahead log file grows with every committed write.\n",
                         "hyphen-compound")
    assert not _findings("The key-value store cache keeps the hot entries in memory.\n",
                         "stacked-nouns")


def test_one_noun_phrase_is_reported_once():
    # stacked-nouns and hyphen-compound both judge noun phrases; one phrase
    # must not score under both. Other detectors measure other things.
    found = [f for f in _findings("The test recreates the old region-index, storage-shrink cache layout.\n")
             if f.feature in ("stacked-nouns", "hyphen-compound")]
    assert len(found) == 1, found


def test_relative_pronoun_subject_takes_its_antecedents_animacy():
    assert not _findings("The engineer that owns the build reviews every change on Friday.\n",
                         "inanimate-subject")


def test_very_long_noun_runs_do_not_overflow_the_stack():
    text = "The " + " ".join(["data"] * 4000) + " grows quickly every day.\n"
    Analyzer(Config()).check_text(text, "markdown")


def test_doc_comment_lines_that_look_like_code_are_kept():
    from readcost.extract import extract_source

    src = ("/// Returns the offset of the current record so that callers can seek;\n"
           "/// the buffer is flushed\n"
           "/// for every write before the call returns.\n"
           "fn offset() -> u64 { 0 }\n")
    text = " ".join(s.text for s in extract_source(src, "lib.rs"))
    assert "callers can seek" in text and "for every write" in text


def test_claude_edit_hook_checks_the_file_when_the_edit_cannot_be_located():
    from readcost.hooks.claude_code import _edited_ranges

    payload = {"tool_name": "Edit", "tool_input": {"new_string": "text the formatter reflowed"}}
    assert _edited_ranges(payload, "Different text on disk.\n") is None


def test_display_state_is_private_to_the_user(tmp_path, monkeypatch):
    import os
    import stat

    from readcost.hooks import claude_code

    for var in ("CLAUDE_PLUGIN_DATA", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    d = claude_code._state_dir()
    assert str(d).startswith(str(tmp_path))
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o700


# --------------------------------------------------------------- self-application

def test_config_files_contribute_only_their_comments():
    from readcost.extract import detect_format, extract

    yml = "# Flags the slow prose.\nname: readcost\ndescription: \"Flag prose constructions that slow readers\"\n"
    assert detect_format("ci.yml") == "source"
    text = " ".join(s.text for s in extract(yml, "ci.yml"))
    assert "description" not in text and "Flag prose constructions" not in text


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_directory_check_skips_gitignored_files(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("build/\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "notes.md").write_text(DENSE)
    (tmp_path / "README.md").write_text(PLAIN)
    out = run_cli(["check", "--fail-on", "never", "."], cwd=tmp_path).stdout
    assert "README.md" in out and "build/notes.md" not in out


# --------------------------------------------------------------- terminology

def test_a_repeated_compound_is_reported_once_per_document():
    text = ("The region index sidecar keeps one record per segment.\n\n"
            "Each query reads the region index sidecar before it scans.\n\n"
            "A missing region index sidecar is rebuilt on open.\n")
    stacked = [f for f in _findings(text, "stacked-nouns") if "region index sidecar" in f.excerpt]
    assert len(stacked) == 1 and stacked[0].line == 1


def test_identifier_subjects_are_not_inanimate_subject_findings():
    assert not _findings("The `parse()` function decides which branch to take next.\n",
                         "inanimate-subject")
    assert not _findings("`parse()` decides which branch the reader takes next.\n",
                         "inanimate-subject")


def test_citations_are_not_noun_stacks():
    assert not _findings("The rewrite keeps rationale clauses, as Chen et al recommend for comments.\n",
                         "stacked-nouns")


# --------------------------------------------------------------- short units

def test_one_finding_in_a_short_text_does_not_make_it_advise():
    # About 20 words with one stacked compound: per-1k density alone would say
    # "advise" (index ~50); short texts are judged by absolute points instead.
    text = "Run the parser once. It keeps the source line numbers that each finding reports later.\n"
    result = Analyzer(Config()).check_text(text, "markdown")
    assert result.words < 40 and len(result.findings) == 1
    assert result.verdict == "pass"


def test_several_findings_in_a_short_text_still_advise():
    text = ("The region index sidecar cache rebuild path forces source segment rebuilds "
            "during store restart measurement runs.\n")
    result = Analyzer(Config()).check_text(text, "markdown")
    assert result.words < 40 and result.points >= 2
    assert result.verdict in ("advise", "block")


# Sentences from public READMEs (arclabs561/sporse, subsume, tranz) and this
# repo's docs, where the tagger read the main verb as a plural noun.
@pytest.mark.parametrize("sentence", [
    "`serde_roundtrip.rs` verifies built-index serialization with the `serde` feature.",
    "This self-contained example prints containment and overlap scores for a small hierarchy.",
    "The manifest records model family, training config, split sizes, SHA-256 digests, byte sizes, "
    "and evaluation metrics when `--eval` is used.",
    "reduced-object-relative skips pronoun subjects and light heads;",
])
def test_misparsed_verb_is_not_part_of_a_noun_stack(sentence):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == []


def test_noun_stack_before_a_verb_is_still_reported():
    findings = Analyzer(Config()).check_text("We tune the shard compaction retry budget by hand.", "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == ["compaction retry budget"]


# From public READMEs (arclabs561/piku, precinct, netbraid): a noun at the
# root plus a verb is the main clause, not an object relative.
@pytest.mark.parametrize("sentence", [
    "The help output begins with:",
    "The point ANN backend is vicinity (HNSW).",
    "The optional Zeek adapter projects `conn.log` rows into that same input type.",
])
def test_main_clause_after_a_root_noun_is_not_an_object_relative(sentence):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert [f.feature for f in findings if f.feature == "reduced-object-relative"] == []


def test_object_relative_without_that_is_still_reported():
    text = "It compresses a posting list, the storage-shrink use case these ID-set codecs exist for."
    findings = Analyzer(Config()).check_text(text, "markdown").findings
    assert [f.feature for f in findings if f.feature == "reduced-object-relative"] == ["reduced-object-relative"]


def test_a_row_of_links_is_navigation_not_prose():
    # From arclabs561/muxer's README: "API docs" was read as part of a noun stack.
    nav = "[Quickstart guide](docs/QUICKSTART.md) | [API docs](https://docs.rs/muxer) | [Changelog](CHANGELOG.md)\n"
    assert extract_markdown(nav, "a.md") == []
    prose = "See the [quickstart guide](docs/QUICKSTART.md) and the [API docs](https://docs.rs/muxer) first.\n"
    assert len(extract_markdown(prose, "a.md")) == 1


@pytest.mark.parametrize("sentence,flagged", [
    # From this repo's README: a majority of people is people.
    ("Of the 75 that are still reported, a majority of eight raters judged 20% correct.", False),
    ("Half of the users decided to keep the old layout.", False),
    # What is counted decides, so a quantity of things still counts as a thing.
    ("A majority of the files decide their own encoding.", True),
    ("The output of the engineers decides the schedule.", True),
])
def test_quantity_subject_takes_the_animacy_of_what_it_counts(sentence, flagged):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert any(f.feature == "inanimate-subject" for f in findings) is flagged


def test_quantity_without_a_counted_noun_keeps_its_own_animacy():
    # From arclabs561/deformat's README: nothing is counted, so "number" is a thing.
    text = "Reporting per page type is the point: a single ALL number hides that one category carries the result."
    findings = Analyzer(Config()).check_text(text, "markdown").findings
    assert [f.feature for f in findings if f.feature == "inanimate-subject"] == ["inanimate-subject"]


@pytest.mark.parametrize("sentence", [
    # Shaped like rollup lines in large projects' pull request descriptions,
    # where owner/repo#N was read as the coined compound "data-store" or "rust-lang".
    "example-org/data-store#4821 (Skip the network step in offline builds)",
    "Adds two tests in `tests/parse` for the two cases reported in example-org/data-store#5123.",
    "This fixes gh-12345 and #678 in the parser module today.",
])
def test_issue_references_are_single_words(sentence):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "hyphen-compound"] == []


def test_a_coined_compound_next_to_an_issue_reference_is_still_reported():
    findings = Analyzer(Config()).check_text("This fixes gh-12345, which the storage-shrink job broke.", "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "hyphen-compound"] == ["storage-shrink job"]


@pytest.mark.parametrize("sentence,excerpts", [
    # A number joined to its unit is a modifier, not a noun in a stack (shapes from PEPs).
    ("Each release has a 17-month development period followed by a beta phase.", []),
    ("The council holds a two-week nomination period before each election.", []),
    # The rest of a real stack is still reported.
    ("We tune the two-week compaction retry budget by hand.", ["compaction retry budget"]),
])
def test_number_unit_modifiers_are_not_stacked_nouns(sentence, excerpts):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == excerpts
