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
