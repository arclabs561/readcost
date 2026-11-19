"""Regression tests for defects found in the 2026-10-26 bug hunt and the 2026-11-17 review.

Each test names the defect it pins. They exercise the public entry points
(Config, Analyzer, the CLI and the git hook) rather than internals.
"""

import json
import subprocess
from pathlib import Path

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


from cliproc import run_cli, run_subprocess  # noqa: E402


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
    return run_cli(["hook", "git", "pre-commit"], cwd=tmp_path)


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

# inanimate-subject is opt-in; the tests of its detector turn it on.
INANIMATE_ON = Config(rules={"inanimate-subject": "info"})


def _findings(text, feature=None, **cfg):
    if feature == "inanimate-subject":  # opt-in; turn it on to test its detector
        cfg.setdefault("rules", {"inanimate-subject": "info"})
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


@pytest.mark.parametrize(("sentence", "rule"), [
    ("The region index sidecar keeps one record per segment.", "stacked-nouns"),
    ("It runs the storage-shrink job every night.", "hyphen-compound"),
])
def test_edited_lines_preserve_the_first_use_of_a_compound(sentence, rule):
    analyzer = Analyzer(Config())
    text = f"{sentence}\n\n{sentence}\n"
    first = analyzer.check_text(text, "markdown", lines=[(1, 1)])
    later = analyzer.check_text(text, "markdown", lines=[(3, 3)])
    assert [(f.feature, f.line) for f in first.findings if f.feature == rule] == [(rule, 1)]
    assert not any(f.feature == rule for f in later.findings)
    assert first.sentences == later.sentences == 1
    assert first.words == later.words


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
    # A verb above the misparse ("grows") did not stop it: two plurals in a row.
    "Formulaic text such as merge-commit subjects scores high legitimately, and the share grows "
    "with the amount of text.",
])
def test_misparsed_verb_is_not_part_of_a_noun_stack(sentence):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == []


def test_noun_stack_before_a_verb_is_still_reported():
    findings = Analyzer(Config()).check_text("We tune the shard compaction retry budget by hand.", "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == ["compaction retry budget"]


def test_plural_head_followed_by_a_verb_is_still_a_noun_stack():
    findings = Analyzer(Config()).check_text(
        "The quarterly product sales figures rose sharply after the new store opened.", "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == ["product sales figures"]


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
    findings = Analyzer(INANIMATE_ON).check_text(sentence, "markdown").findings
    assert any(f.feature == "inanimate-subject" for f in findings) is flagged


def test_quantity_without_a_counted_noun_keeps_its_own_animacy():
    # From arclabs561/deformat's README: nothing is counted, so "number" is a thing.
    text = "Reporting per page type is the point: a single ALL number hides that one category carries the result."
    findings = Analyzer(INANIMATE_ON).check_text(text, "markdown").findings
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
    # A number or symbol splits the run: the quantity is not part of the compound.
    ("The effect is larger in Brown (+1.30 x10^-2 nats) and smaller in Dundee.", []),
    ("For nouns, log integration cost +5.86 ms is significant in the model.", ["log integration cost"]),
])
def test_number_unit_modifiers_are_not_stacked_nouns(sentence, excerpts):
    findings = Analyzer(Config()).check_text(sentence, "markdown").findings
    assert [f.excerpt for f in findings if f.feature == "stacked-nouns"] == excerpts


def test_directory_walk_prunes_excluded_dirs_and_reads_nested_repos(tmp_path):
    from readcost.cli import _walk
    from readcost.config import Config

    cfg = Config()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(PLAIN)
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "README.md").write_text(PLAIN)
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "notes.md").write_text(PLAIN)
    repo = tmp_path / "repo"
    (repo / "build").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("build/\n")
    (repo / "README.md").write_text(PLAIN)
    (repo / "build" / "out.md").write_text(PLAIN)
    (repo / "new").mkdir()
    (repo / "new" / "draft.md").write_text(PLAIN)  # untracked, not ignored: still checked
    names = sorted(str(p.relative_to(tmp_path)) for p in _walk(tmp_path, True, cfg.excluded))
    assert names == ["docs/guide.md", "repo/.gitignore", "repo/README.md", "repo/new/draft.md"]
    # Without ignore files, git is not asked: build/ is read, hidden and excluded dirs still are not.
    names = sorted(str(p.relative_to(tmp_path)) for p in _walk(tmp_path, False, cfg.excluded))
    assert "repo/build/out.md" in names and not any("node_modules" in n or ".cache" in n for n in names)


def test_git_walk_lists_an_untracked_nested_repository_by_its_own_ignore_file(tmp_path):
    from readcost.cli import _walk

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text(PLAIN)
    inner = tmp_path / "vendor-docs"
    (inner / "out").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=inner, check=True)
    (inner / ".gitignore").write_text("out/\n")
    (inner / "guide.md").write_text(PLAIN)
    (inner / "out" / "gen.md").write_text(PLAIN)
    names = sorted(str(p.relative_to(tmp_path)) for p in _walk(tmp_path))
    assert names == ["README.md", "vendor-docs/.gitignore", "vendor-docs/guide.md"]


def test_parallel_check_matches_the_sequential_check(tmp_path):
    from readcost.cli import PARALLEL_MIN_FILES

    for i in range(PARALLEL_MIN_FILES):
        (tmp_path / f"doc{i:02}.md").write_text(DENSE if i % 2 else PLAIN)
    one = run_cli(["check", "-o", "json", "--fail-on", "never", "-j", "1", "."], cwd=tmp_path)
    # A real process for the pool: its workers start from `python -m readcost`.
    two = run_subprocess(["check", "-o", "json", "--fail-on", "never", "-j", "2", "."], cwd=tmp_path)
    assert one.returncode == two.returncode == 0
    assert json.loads(one.stdout) == json.loads(two.stdout)
    assert len(json.loads(two.stdout)) == PARALLEL_MIN_FILES


def test_many_file_arguments_are_checked_in_parallel_in_order(tmp_path):
    from readcost.cli import PARALLEL_MIN_FILES

    names = [f"doc{i:02}.md" for i in range(PARALLEL_MIN_FILES)]
    for i, n in enumerate(names):
        (tmp_path / n).write_text(DENSE if i % 2 else PLAIN)
    args = ["check", "-o", "json", "--fail-on", "never"]
    one = run_cli([*args, "-j", "1", *reversed(names)], cwd=tmp_path)
    two = run_subprocess([*args, "-j", "2", *reversed(names)], cwd=tmp_path)
    assert json.loads(one.stdout) == json.loads(two.stdout)
    assert [r["path"] for r in json.loads(two.stdout)] == list(reversed(names))


# --- 2026-11-17 review ---------------------------------------------------------

SWALLOWED = "The index shard compaction job reruns merge planning every hour."


def test_sentence_whose_verb_was_parsed_as_a_noun_still_gets_the_noun_rules():
    # The small model tags "reruns" as a noun, so the sentence has no verb.
    # It used to be skipped with no note: the densest stacks went unreported.
    r = Analyzer(Config()).check_text(SWALLOWED + "\n", "markdown")
    assert r.sentences == 1
    assert [(f.feature, f.excerpt) for f in r.findings] == [("stacked-nouns", "index shard compaction job")]


def test_verbless_fragment_without_a_full_stop_is_still_skipped():
    r = Analyzer(Config()).check_text(SWALLOWED.rstrip(".") + "\n", "markdown")
    assert r.sentences == 0 and not r.findings


def test_generic_hook_reads_open_line_ranges_like_the_cli():
    from readcost.hooks.generic import review

    text = PLAIN + "\n" + DENSE  # DENSE starts on line 3
    assert review(text, lines="3-")["findings"]
    assert not review(text, lines="-1")["findings"]
    with pytest.raises(ValueError, match="runs low to high"):
        review(text, lines="9-5")


def test_generic_hook_rejects_a_bad_line_range_with_exit_2():
    proc = run_cli(["hook", "generic"], json.dumps({"text": PLAIN, "lines": "-x"}))
    assert proc.returncode == 2
    assert "lines: '-x' is not a line or range" in json.loads(proc.stdout)["error"]


def test_phrasal_verb_that_takes_things_is_not_an_inanimate_subject():
    a = Analyzer(INANIMATE_ON)
    feats = lambda t: [f.feature for f in a.check_text(t, "markdown").findings]  # noqa: E731
    assert "inanimate-subject" not in feats("Large inputs blow up the memory usage of the parser.")
    # A figurative phrasal verb with a thing as subject is still reported.
    assert "inanimate-subject" in feats("The parser spits out errors for every file it cannot read.")


def test_suspended_hyphen_is_not_a_noun_in_a_stack():
    text = "Labeling 10% of items cut prevalence error four- to sevenfold but did not improve classification.\n"
    assert not [f for f in Analyzer(Config()).check_text(text, "markdown").findings if f.feature == "stacked-nouns"]


def test_long_dependency_below_the_z_threshold_does_not_print_z():
    # Reported for the 18-word gap alone (z = 1.0); "(z = 1.0)" read as a reason not to report it.
    text = ("The index, built once from all documents and rebuilt only on compaction after every "
            "flush of the write buffer, serves queries.\n")
    fs = [f for f in Analyzer(Config()).check_text(text, "markdown").findings if f.feature == "long-dependency"]
    assert [f.message for f in fs] == ["'index' and 'serves' are 18 words apart"]


def test_file_that_is_not_utf8_keeps_its_bytes_and_gets_a_note(tmp_path):
    p = tmp_path / "latin1.md"
    p.write_bytes("Café owners use the storage-shrink job before each release.\n".encode("latin-1"))
    r = Analyzer(Config()).check_file(str(p))
    assert "�" in r.source and any("not valid UTF-8" in n for n in r.notes)
    out = run_cli(["check", "-o", "json", "--fail-on", "never", str(p)])
    assert any("not valid UTF-8" in n for n in json.loads(out.stdout)[0]["notes"])


@pytest.mark.parametrize("text", [
    # The real verb "fixes" heads the run: only two nouns come before it.
    "A beta-binomial version with one correlation parameter fixes most of this.",
    # Notes without articles are a list, not a clause with a swallowed verb.
    "Experiments: Pew post-election survey (approval, binary), census age-income regression, "
    "AlphaFold odds ratio; alpha = 0.1, 1,000 batch trials.",
])
def test_misparsed_verb_path_leaves_verbs_and_terse_notes_alone(text):
    assert not Analyzer(Config()).check_text(text + "\n", "markdown").findings


def test_person_name_at_the_start_of_a_sentence_is_not_a_noun_stack():
    a = Analyzer(Config())
    assert not a.check_text("Guido van Rossum wrote the first version in 1989.\n", "markdown").findings
    # A coined stack that starts a sentence is still reported.
    feats = [f.feature for f in a.check_text("Cache eviction policy tuning takes a week of work.\n", "markdown").findings]
    assert "stacked-nouns" in feats


def test_inline_list_is_off_in_doc_comments_unless_asked_for():
    # docs/evaluation.md, "Precision across formats": 1 of 28 inline-list
    # findings in doc comments was accepted, against 5 of 16 in Markdown.
    sentence = "The parser handles tables, footnotes, front matter, math and raw HTML in every document it reads."
    py = f'def f():\n    """{sentence}"""\n'
    md = sentence + "\n"
    def rules(cfg, text, fmt, path):
        return [f.feature for f in Analyzer(cfg).check_text(text, fmt, path).findings]

    assert "inline-list" in rules(Config(), md, "markdown", "a.md")
    assert "inline-list" not in rules(Config(), py, None, "a.py")
    assert "inline-list" in rules(Config(rules={"inline-list": "info"}), py, None, "a.py")
    assert "inline-list" in rules(Config(overrides=[{"include": ["*.py"], "rules": {"inline-list": "warn"}}]),
                                  py, None, "a.py")


# An inline footnote, "^[text]", becomes a paragraph with no line map at the end
# of markdown-it's tokens, and readcost 0.3.0 raised TypeError on it. A regex
# such as ^[a-z] in a doc comment parses as one. The fixtures are made up and
# have the shapes of the three files the kinds-precision draw dropped.

def footnote_body(segs, words):
    return next(s for s in segs if s.text == words)


def test_inline_footnote_is_read_on_the_line_that_holds_it():
    from readcost.extract import extract

    src = ("# Names\n\nThe first line of this paragraph is plain.\n"
           "Names must match ^[a lowercase letter and then more letters] or the\n"
           "service rejects them at once.\n")
    segs = extract(src, "names.md")
    assert segs[0].text == "The first line of this paragraph is plain. Names must match or the service rejects them at once."
    assert segs[0].span(segs[0].text.index("or the"), segs[0].text.index("or the") + 6) == \
        (src.index("or the"), src.index("or the") + 6)
    note = footnote_body(segs, "a lowercase letter and then more letters")
    assert note.line_at(0) == 4
    assert note.span(0, len(note.text)) == (src.index("a lowercase"), src.index("letters]") + 7)


@pytest.mark.parametrize("src,line", [
    ("- One item.\n- Another item, with a note ^[the note here has five words] in it.\n", 2),
    ("> A quote.\n>\n> The second paragraph ^[the note here has five words] goes on.\n", 3),
    ("# A heading ^[the note here has five words]\n\nSome text follows the heading here.\n", 1),
    ("| a | b |\n|---|---|\n| x | cell ^[the note here has five words] |\n", 3),
    ("Outer ^[the note here has five words ^[and an inner note in it]] text.\n", 1),
])
def test_inline_footnote_in_any_container_gets_a_line(src, line):
    from readcost.extract import extract

    segs = extract(src, "x.md")
    assert any(s.text.startswith("the note here has five words") and s.line_at(0) == line for s in segs)


@pytest.mark.parametrize("path,src,line", [
    ("castprefix.py", ('def tamper(value):\n    """Put a cast before the value.\n\n'
                       "    The rule is anchored with '^[a word or a digit]+', so it only sees a keyword\n"
                       '    at the start of the value.\n    """\n    return value\n'), 4),
    ("space_pb.ts", ("/**\n * The slug of the space must match\n"
                     " * ^[a lowercase letter or digit]([a-z0-9-]{0,34}[a-z0-9])?$.\n */\nexport const slug = 1;\n"), 3),
])
def test_inline_footnote_in_a_doc_comment(path, src, line):
    from readcost.extract import extract

    segs = extract(src, path)
    note = next(s for s in segs if s.text.startswith("a "))
    assert note.line_at(0) == line


def test_extraction_error_is_a_note_on_that_file_and_the_run_goes_on(tmp_path, monkeypatch):
    import readcost.engine

    real = readcost.engine.extract

    def extract(text, path, *a, **kw):
        if path.endswith("bad.md"):
            raise TypeError("'NoneType' object is not subscriptable")
        return real(text, path, *a, **kw)

    monkeypatch.setattr(readcost.engine, "extract", extract)
    (tmp_path / "bad.md").write_text(PLAIN)
    (tmp_path / "good.md").write_text(DENSE)
    r = run_cli(["check", "-o", "json", "bad.md", "good.md"], cwd=tmp_path)
    data = {Path(d["path"]).name: d for d in json.loads(r.stdout)}
    assert "Traceback" not in r.stderr and "internal error" not in r.stderr
    assert data["bad.md"]["words"] == 0 and "TypeError" in data["bad.md"]["notes"][0]
    assert data["good.md"]["verdict"] == "block"
    assert "bad.md: not checked: TypeError" in r.stderr
    assert r.returncode == 2  # a file readcost could not check is not a pass


def test_other_error_on_one_file_is_reported_and_the_rest_are_checked(tmp_path, monkeypatch):
    real = Analyzer.analyze

    def analyze(self, segments, path, *a, **kw):
        if path.endswith("bad.md"):
            raise KeyError("boom")
        return real(self, segments, path, *a, **kw)

    monkeypatch.setattr(Analyzer, "analyze", analyze)
    (tmp_path / "bad.md").write_text(PLAIN)
    (tmp_path / "good.md").write_text(DENSE)
    r = run_cli(["check", "-o", "json", "bad.md", "good.md"], cwd=tmp_path)
    assert "bad.md: internal error: KeyError" in r.stderr
    assert [Path(d["path"]).name for d in json.loads(r.stdout)] == ["good.md"]
    assert r.returncode == 2
