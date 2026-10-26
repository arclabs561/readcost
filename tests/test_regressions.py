"""Regression tests for defects found in the 2026-10-26 bug hunt.

Each test names the defect it pins. They exercise the public entry points
(Config, Analyzer, the CLI and the git hook) rather than internals.
"""

import subprocess
import sys

import pytest

from readcost.config import Config
from readcost.engine import Analyzer

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds.\n")
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
               "those sidecars and forcing source-segment rebuilds.\n")
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
