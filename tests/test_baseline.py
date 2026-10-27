"""Baseline mode: only findings missing from a recorded baseline count."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from readcost.baseline import Baseline, finding_key
from readcost.config import load_config
from readcost.features import Finding

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")
NEW_DENSE = ("The planner rejects the cache eviction policy override flag when the "
             "write-ahead-log replay checkpoint interval lags behind.\n")
HAS_GIT = subprocess.run(["git", "--version"], check=False, capture_output=True).returncode == 0


def run(args, stdin=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin,
                          check=False, capture_output=True, text=True, cwd=cwd)


def finding(sentence="We tune the shard compaction retry budget by hand.", line=3,
            path="README.md", feature="stacked-nouns"):
    return Finding(feature=feature, severity="warn", message="m", excerpt="x", sentence=sentence,
                   path=path, line=line)


def record(tmp_path, text=DENSE, name="README.md"):
    (tmp_path / name).write_text(text)
    proc = run(["baseline", name], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    return tmp_path / ".readcost-baseline.json"


def check_json(tmp_path, *args):
    proc = run(["check", "-o", "json", "--fail-on", "advise", *args], cwd=tmp_path)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


# --- the key -----------------------------------------------------------------

def test_key_ignores_line_numbers_and_reflowed_whitespace(tmp_path):
    a = finding(line=3)
    b = finding(sentence="We tune the shard compaction\n  retry budget by hand.", line=40)
    assert finding_key(a, tmp_path) == finding_key(b, tmp_path)
    assert finding_key(a, tmp_path) != finding_key(finding(sentence="We tune it by hand today."), tmp_path)
    assert finding_key(a, tmp_path) != finding_key(finding(feature="long-dependency"), tmp_path)


def test_key_path_is_relative_to_the_baseline_with_forward_slashes(tmp_path):
    (tmp_path / "docs").mkdir()
    key = finding_key(finding(path=str(tmp_path / "docs" / "a.md")), tmp_path)
    assert key[0] == "docs/a.md"


def test_duplicates_are_counted():
    three = [finding() for _ in range(3)]
    key = finding_key(three[0], Path.cwd())
    base = Baseline({key[0]: {key[1:]: 2}}, Path.cwd())
    kept, suppressed = base.suppress(three, base.budget(key[0]))
    assert (len(kept), suppressed) == (1, 2)
    # The budget is a copy: suppressing did not use up the stored counts.
    assert base.budget(key[0])[key[1:]] == 2


# --- the baseline file -------------------------------------------------------

def test_baseline_file_is_sorted_versioned_one_entry_per_line_and_has_no_text(tmp_path):
    path = record(tmp_path)
    raw = path.read_text()
    data = json.loads(raw)
    assert data["version"] == 1 and data["findings"]
    entries = [(e["path"], e["feature"], e["sentence_hash"]) for e in data["findings"]]
    assert entries == sorted(entries)
    assert all(set(e) == {"path", "feature", "sentence_hash", "count"} for e in data["findings"])
    plain = json.loads(run(["check", "-o", "json", "--fail-on", "never", "README.md"], cwd=tmp_path).stdout)
    assert sum(e["count"] for e in data["findings"]) == len(plain[0]["findings"])
    lines = raw.splitlines()
    assert len(lines) == len(data["findings"]) + 4  # {, "version", "findings": [, one per entry, ]}
    assert "compaction" not in raw and "shard" not in raw
    assert run(["baseline", "README.md"], cwd=tmp_path).returncode == 0
    assert path.read_text() == raw  # stable: rewriting it changes nothing


# --- check --baseline --------------------------------------------------------

def test_line_shift_keeps_old_findings_baselined(tmp_path):
    base = record(tmp_path)
    (tmp_path / "README.md").write_text("# Title\n\nThe index stores one list per term.\n\n\n" + DENSE)
    code, data, _ = check_json(tmp_path, "--baseline", str(base), "README.md")
    assert data[0]["findings"] == [] and data[0]["baselined"] > 0
    assert code == 0


def test_new_finding_is_reported_and_old_ones_are_not(tmp_path):
    base = record(tmp_path)
    (tmp_path / "README.md").write_text(DENSE + "\n" + NEW_DENSE)
    _, data, _ = check_json(tmp_path, "--baseline", str(base), "README.md")
    assert data[0]["findings"]
    assert all(f["sentence"].startswith("The planner") for f in data[0]["findings"])
    assert data[0]["baselined"] == len(json.loads(run(
        ["check", "-o", "json", "--fail-on", "never", "-"], DENSE, tmp_path).stdout)[0]["findings"])


def test_verdict_uses_only_new_findings(tmp_path):
    base = record(tmp_path)
    code, data, _ = check_json(tmp_path, "README.md")
    assert code == 1 and data[0]["verdict"] == "block"
    code, data, _ = check_json(tmp_path, "--baseline", str(base), "README.md")
    assert code == 0 and data[0]["verdict"] == "pass"


def test_duplicate_sentence_beyond_the_baseline_count_is_new(tmp_path):
    base = record(tmp_path, "The report says it does not own indexing, segment selection, "
                            "compaction, or reader visibility.\n")
    (tmp_path / "README.md").write_text(
        "The report says it does not own indexing, segment selection, compaction, or reader visibility.\n\n"
        "The report says it does not own indexing, segment selection, compaction, or reader visibility.\n")
    _, data, _ = check_json(tmp_path, "--baseline", str(base), "README.md")
    old = json.loads(base.read_text())["findings"]
    assert data[0]["baselined"] == sum(e["count"] for e in old)
    assert len(data[0]["findings"]) == data[0]["baselined"]
    assert all(f["line"] == 3 for f in data[0]["findings"])


def test_text_summary_says_how_many_were_baselined(tmp_path):
    base = record(tmp_path)
    out = run(["check", "--baseline", str(base), "README.md"], cwd=tmp_path).stdout
    assert "in baseline" in out.splitlines()[-1]


def test_baseline_exit_codes(tmp_path):
    (tmp_path / "README.md").write_text(DENSE)
    assert run(["baseline", "README.md", "-o", "b.json"], cwd=tmp_path).returncode == 0
    assert (tmp_path / "b.json").is_file()
    assert run(["check", "--baseline", "b.json", "README.md"], cwd=tmp_path).returncode == 0
    assert run(["check", "--baseline", "missing.json", "README.md"], cwd=tmp_path).returncode == 2
    (tmp_path / "bad.json").write_text('{"version": 99, "findings": []}\n')
    proc = run(["check", "--baseline", "bad.json", "README.md"], cwd=tmp_path)
    assert proc.returncode == 2 and "version" in proc.stderr
    assert run(["baseline", "missing.md"], cwd=tmp_path).returncode == 2


def test_baseline_records_findings_below_min_severity(tmp_path):
    # The verdict counts every finding, so the baseline has to hold every finding.
    (tmp_path / "readcost.toml").write_text('min_severity = "error"\n')
    base = record(tmp_path)
    code, data, _ = check_json(tmp_path, "--baseline", str(base), "README.md")
    assert code == 0 and data[0]["verdict"] == "pass"


# --- config ------------------------------------------------------------------

def test_config_baseline_is_relative_to_the_config_file(tmp_path, monkeypatch):
    (tmp_path / "sub").mkdir()
    (tmp_path / "readcost.toml").write_text('baseline = "sub/base.json"\n')
    elsewhere = tmp_path / "sub"
    monkeypatch.chdir(elsewhere)
    cfg = load_config(str(tmp_path / "readcost.toml"))
    assert Path(cfg.baseline) == (tmp_path / "sub" / "base.json").resolve()


def test_config_baseline_applies_to_check(tmp_path):
    record(tmp_path)
    (tmp_path / "readcost.toml").write_text('baseline = ".readcost-baseline.json"\n')
    (tmp_path / "docs").mkdir()
    code, data, _ = check_json(tmp_path / "docs", str(tmp_path / "README.md"))
    assert code == 0 and data[0]["baselined"] > 0


# --- hooks -------------------------------------------------------------------

@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_git_pre_commit_honours_config_baseline(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    record(tmp_path)
    (tmp_path / "readcost.toml").write_text(
        'baseline = ".readcost-baseline.json"\n[hooks]\nmode = "block"\n')
    git("add", ".")
    git("commit", "-qm", "init")
    hook = [sys.executable, "-m", "readcost", "hook", "git", "pre-commit", "README.md"]
    assert subprocess.run(hook, check=False, capture_output=True, text=True, cwd=tmp_path).returncode == 0
    (tmp_path / "README.md").write_text(DENSE + "\n" + NEW_DENSE)
    git("add", "README.md")
    proc = subprocess.run(hook[:-1], check=False, capture_output=True, text=True, cwd=tmp_path)
    assert proc.returncode == 1 and "README.md:3:" in proc.stderr and "README.md:1:" not in proc.stderr


def test_claude_code_post_tool_use_honours_config_baseline(tmp_path):
    record(tmp_path)
    (tmp_path / "readcost.toml").write_text('baseline = ".readcost-baseline.json"\n')
    payload = {"tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / "README.md"), "content": DENSE}}
    proc = subprocess.run([sys.executable, "-m", "readcost", "hook", "claude-code", "post-tool-use"],
                          input=json.dumps(payload), check=False, capture_output=True, text=True, cwd=tmp_path,
                          env={**os.environ, "READCOST_HOOK_DEBUG": "1"})
    assert proc.returncode == 0 and proc.stdout == "", proc.stdout + proc.stderr
    (tmp_path / "README.md").write_text(DENSE + "\n" + NEW_DENSE)
    proc = subprocess.run([sys.executable, "-m", "readcost", "hook", "claude-code", "post-tool-use"],
                          input=json.dumps(payload), check=False, capture_output=True, text=True, cwd=tmp_path)
    assert "line 3" in proc.stdout and "line 1 " not in proc.stdout
