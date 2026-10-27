"""Rule levels, per-path overrides and file selection, modelled on ty's configuration."""

import subprocess
import sys

import pytest

from readcost.config import load_config

DENSE = "We tune the shard compaction retry budget by hand.\n"  # one stacked-nouns finding (warn)


def run(args, cwd, stdin=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin, cwd=cwd,
                          capture_output=True, text=True, check=False)


def concise(cwd, *args, stdin=DENSE):
    out = run(["check", "-o", "concise", "--fail-on", "never", *args, "-"], cwd, stdin).stdout
    return [line for line in out.splitlines() if line.startswith("<stdin>:1")]


def test_rules_table_sets_severity_and_ignore_turns_off(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.rules]\nstacked-nouns = "error"\n')
    assert concise(tmp_path)[0].startswith("<stdin>:1:19: error: [stacked-nouns]")
    (tmp_path / "readcost.toml").write_text('[readcost.rules]\nstacked-nouns = "ignore"\n')
    assert concise(tmp_path) == []


def test_level_turns_on_an_opt_in_rule(tmp_path):
    long = "This sentence keeps going " + "and going " * 20 + "until it ends.\n"
    assert not [x for x in concise(tmp_path, stdin=long) if "long-sentence" in x]
    assert [x for x in concise(tmp_path, "--info", "long-sentence", stdin=long) if "long-sentence" in x]


def test_flags_override_the_config_file(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.rules]\nstacked-nouns = "error"\n')
    assert concise(tmp_path, "--ignore", "stacked-nouns") == []
    assert concise(tmp_path, "--warn", "all")[0].startswith("<stdin>:1:19: warn:")


def test_overrides_apply_by_path_in_order(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "readcost.toml").write_text(
        '[readcost.rules]\nstacked-nouns = "error"\n'
        '[[readcost.overrides]]\ninclude = ["docs/*"]\nexclude = ["docs/keep.md"]\n'
        'rules = { stacked-nouns = "ignore" }\n')
    cfg = load_config(str(tmp_path / "readcost.toml"))
    assert cfg.rule_levels("README.md")["stacked-nouns"] == "error"
    assert cfg.rule_levels("docs/a.md")["stacked-nouns"] == "ignore"
    assert cfg.rule_levels("docs/keep.md")["stacked-nouns"] == "error"


def test_unknown_rule_or_level_is_an_error(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.rules]\nstacked-noun = "error"\n')
    proc = run(["check", "-"], tmp_path, DENSE)
    assert proc.returncode == 2 and "unknown rule 'stacked-noun'" in proc.stderr
    (tmp_path / "readcost.toml").write_text('[readcost.rules]\nstacked-nouns = "loud"\n')
    proc = run(["check", "-"], tmp_path, DENSE)
    assert proc.returncode == 2 and "must be one of info, warn, error, ignore" in proc.stderr
    assert run(["check", "--warn", "nope", "-"], tmp_path, DENSE).returncode == 2


def test_deprecated_keys_still_work_and_warn(tmp_path):
    (tmp_path / "readcost.toml").write_text(
        '[readcost]\ndisable = ["stacked-nouns"]\n[readcost.hooks]\npaths = ["*.txt"]\n')
    proc = run(["check", "-o", "concise", "--fail-on", "never", "-"], tmp_path, DENSE)
    assert "stacked-nouns" not in proc.stdout
    assert "disable is deprecated" in proc.stderr and "hooks.paths is deprecated" in proc.stderr
    assert load_config(str(tmp_path / "readcost.toml")).src.include == ["*.txt"]


def make_tree(root):
    (root / "docs").mkdir()
    (root / "vendor").mkdir()
    for p in ("docs/a.md", "vendor/b.md", "notes.md"):
        (root / p).write_text(DENSE)


@pytest.mark.parametrize("args,expected", [
    ([], {"docs/a.md", "notes.md"}),                       # vendor is in the default exclude
    (["--exclude", "docs/*"], {"notes.md"}),               # extends the excludes
])
def test_exclude_flag_extends_the_defaults(tmp_path, args, expected):
    make_tree(tmp_path)
    out = run(["check", "-o", "concise", "--fail-on", "never", *args, "."], tmp_path).stdout
    files = {line.split(":")[0] for line in out.splitlines() if ": warn:" in line}
    assert files == expected


def test_force_exclude_applies_to_named_files(tmp_path):
    make_tree(tmp_path)
    named = run(["check", "-o", "concise", "--fail-on", "never", "vendor/b.md"], tmp_path).stdout
    assert "vendor/b.md:1" in named
    forced = run(["check", "-o", "concise", "--fail-on", "never", "--force-exclude", "vendor/b.md"], tmp_path).stdout
    assert "vendor/b.md" not in forced


def test_ignore_files_are_respected_unless_turned_off(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    make_tree(tmp_path)
    (tmp_path / ".gitignore").write_text("notes.md\n")
    out = run(["check", "-o", "concise", "--fail-on", "never", "."], tmp_path).stdout
    assert "notes.md:1" not in out
    out = run(["check", "-o", "concise", "--fail-on", "never", "--no-respect-ignore-files", "."], tmp_path).stdout
    assert "notes.md:1" in out


def test_exit_zero(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.rules]\nall = "error"\n')
    assert run(["check", "--fail-on", "advise", "-"], tmp_path, DENSE).returncode == 1
    assert run(["check", "--fail-on", "advise", "--exit-zero", "-"], tmp_path, DENSE).returncode == 0
