"""Hook fixes from the bug hunt: one test per defect, each red before its fix."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")
PLAIN = "The index stores one list of documents for each term.\n"
HAS_GIT = subprocess.run(["git", "--version"], capture_output=True).returncode == 0


def hook(args, payload, cwd, env=None, raw=None):
    proc = subprocess.run([sys.executable, "-m", "readcost", "hook", *args],
                          input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, cwd=cwd,
                          env={**os.environ, **(env or {})})
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, out, proc.stderr


def block_mode(d: Path, extra: str = "") -> None:
    (d / "readcost.toml").write_text(f'[readcost.hooks]\nmode = "block"\n{extra}')


def git_repo(d: Path):
    def git(*a):
        subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    return git


def git_hook(d: Path, *args):
    return subprocess.run([sys.executable, "-m", "readcost", "hook", "git", "pre-commit", *args],
                          capture_output=True, text=True, cwd=d)


# pre-commit framework: passed filenames ---------------------------------------

@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_pre_commit_filenames_with_nothing_staged_checks_whole_file(tmp_path):
    # `pre-commit run --all-files` and pre-commit.ci pass every file and stage nothing.
    git = git_repo(tmp_path)
    block_mode(tmp_path)
    (tmp_path / "README.md").write_text(DENSE)
    git("add", ".")
    git("commit", "-qm", "init")
    proc = git_hook(tmp_path, "README.md")
    assert proc.returncode == 1 and "stacked-nouns" in proc.stderr


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_pre_commit_filenames_with_staged_change_checks_changed_lines(tmp_path):
    git = git_repo(tmp_path)
    block_mode(tmp_path)
    (tmp_path / "README.md").write_text(DENSE)
    git("add", ".")
    git("commit", "-qm", "init")
    (tmp_path / "README.md").write_text(DENSE + "\n" + PLAIN)
    git("add", "README.md")
    proc = git_hook(tmp_path, "README.md")
    assert proc.returncode == 0 and proc.stderr == ""


def test_pre_commit_manifest_passes_filenames():
    manifest = (ROOT / ".pre-commit-hooks.yaml").read_text()
    first = manifest.split("- id: readcost-commit-msg")[0]
    assert "pass_filenames: false" not in first and "always_run" not in first


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_pre_commit_glob_characters_in_filename(tmp_path):
    # "[WIP] plan.md" as a pathspec also matches "W plan.md".
    git = git_repo(tmp_path)
    block_mode(tmp_path)
    (tmp_path / "[WIP] plan.md").write_text(DENSE)
    (tmp_path / "W plan.md").write_text("x\n")
    git("add", ".")
    git("commit", "-qm", "init")
    (tmp_path / "[WIP] plan.md").write_text(DENSE + "\n" + PLAIN)
    (tmp_path / "W plan.md").write_text(PLAIN)
    git("add", ".")
    proc = git_hook(tmp_path)
    assert proc.returncode == 0 and proc.stderr == ""


@pytest.mark.skipif(not HAS_GIT, reason="git missing")
def test_pre_commit_loads_one_analyzer_per_run(tmp_path, monkeypatch):
    git = git_repo(tmp_path)
    block_mode(tmp_path, 'edited_lines_only = false\n')
    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text(PLAIN)
    git("add", ".")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("READCOST_CONFIG", raising=False)

    from readcost import engine
    from readcost.hooks import git as git_hooks

    made = []

    class Counting(engine.Analyzer):
        def __init__(self, *a, **kw):
            made.append(1)
            super().__init__(*a, **kw)

    monkeypatch.setattr(engine, "Analyzer", Counting)
    assert git_hooks.handle("pre-commit", []) == 0
    assert len(made) == 1


# Claude Code: Write to an existing file -----------------------------------------

def test_post_tool_use_write_judges_only_changed_lines(tmp_path):
    f = tmp_path / "README.md"
    new = DENSE + "\n" + PLAIN
    f.write_text(new)
    rc, out, err = hook(["claude-code", "post-tool-use"],
                        {"tool_name": "Write", "tool_input": {"file_path": str(f), "content": new},
                         "tool_response": {"type": "update", "filePath": str(f), "content": new,
                                           "originalFile": DENSE},
                         "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and out is None and err == ""


def test_post_tool_use_write_flags_changed_dense_lines(tmp_path):
    f = tmp_path / "README.md"
    new = PLAIN + "\n" + DENSE
    f.write_text(new)
    _, out, _ = hook(["claude-code", "post-tool-use"],
                     {"tool_name": "Write", "tool_input": {"file_path": str(f), "content": new},
                      "tool_response": {"type": "update", "originalFile": PLAIN},
                      "cwd": str(tmp_path)}, tmp_path)
    assert "stacked-nouns" in out["hookSpecificOutput"]["additionalContext"]


def test_pre_tool_use_write_to_existing_file_judges_only_changed_lines(tmp_path):
    block_mode(tmp_path)
    f = tmp_path / "README.md"
    f.write_text(DENSE)
    rc, out, err = hook(["claude-code", "pre-tool-use"],
                        {"tool_name": "Write",
                         "tool_input": {"file_path": str(f), "content": DENSE + "\n" + PLAIN},
                         "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and out is None and err == ""


def test_pre_tool_use_write_denies_new_dense_lines(tmp_path):
    block_mode(tmp_path)
    f = tmp_path / "README.md"
    f.write_text(PLAIN)
    _, out, _ = hook(["claude-code", "pre-tool-use"],
                     {"tool_name": "Write",
                      "tool_input": {"file_path": str(f), "content": PLAIN + "\n" + DENSE},
                      "cwd": str(tmp_path)}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pre_tool_use_edit_labels_positions_in_new_text(tmp_path):
    block_mode(tmp_path)
    _, out, _ = hook(["claude-code", "pre-tool-use"],
                     {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "a.md"),
                                                          "old_string": "x", "new_string": DENSE},
                      "cwd": str(tmp_path)}, tmp_path)
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "line 1 of the new text" in reason


def test_piku_pre_tool_use_edit_labels_positions_in_new_text(tmp_path):
    _, out, _ = hook(["piku", "pre-tool-use"],
                     {"tool_name": "edit_file", "tool_input": {"path": "a.md", "old_string": "x",
                                                               "new_string": DENSE},
                      "cwd": str(tmp_path)}, tmp_path)
    assert "of the new text" in out["hookSpecificOutput"]["additionalContext"]


def test_multiedit_is_ignored(tmp_path):
    f = tmp_path / "README.md"
    f.write_text(DENSE)
    rc, out, err = hook(["claude-code", "post-tool-use"],
                        {"tool_name": "MultiEdit", "tool_input": {"file_path": str(f), "edits": []},
                         "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and out is None and err == ""


# hooks.mode = "off" ----------------------------------------------------------------

def test_mode_off_stops_stop_revise(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.hooks]\nmode = "off"\nstop = "revise"\n')
    rc, out, err = hook(["claude-code", "stop"],
                        {"last_assistant_message": DENSE, "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and out is None and err == ""


def test_mode_off_stops_piku_logging(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.hooks]\nmode = "off"\n')
    (tmp_path / "README.md").write_text(DENSE)
    rc, _, err = hook(["piku", "post-tool-use"],
                      {"tool_name": "write_file", "tool_input": {"path": "README.md"},
                       "tool_response": {"is_error": False}, "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and err == ""
    assert not (tmp_path / ".piku" / "readcost.jsonl").exists()


# Stop revise length ----------------------------------------------------------------

def test_stop_revise_respects_max_chars(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.hooks]\nstop = "revise"\nmax_chars = 200\n')
    _, out, _ = hook(["claude-code", "stop"],
                     {"last_assistant_message": DENSE, "cwd": str(tmp_path)}, tmp_path)
    assert out["decision"] == "block" and len(out["reason"]) <= 200
    assert out["reason"].startswith("readcost:")


# Config lookup ----------------------------------------------------------------------

def test_config_found_from_edited_file_directory(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    block_mode(sub)
    f = sub / "README.md"
    f.write_text(DENSE)
    _, out, _ = hook(["claude-code", "post-tool-use"],
                     {"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(tmp_path)},
                     tmp_path)
    assert out["decision"] == "block"


def test_piku_config_found_from_edited_file_directory(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    block_mode(sub)
    _, out, _ = hook(["piku", "pre-tool-use"],
                     {"tool_name": "write_file", "tool_input": {"path": "sub/a.md", "content": DENSE},
                      "cwd": str(tmp_path)}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# piku PostToolUse reads the checked path -----------------------------------------------

def test_piku_post_tool_use_reads_file_under_payload_cwd(tmp_path):
    project, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    project.mkdir()
    elsewhere.mkdir()
    (project / "README.md").write_text(DENSE)
    (elsewhere / "README.md").write_text(PLAIN)
    hook(["piku", "post-tool-use"], {"tool_name": "write_file", "tool_input": {"path": "README.md"},
                                     "tool_response": {"is_error": False}, "cwd": str(project)},
         elsewhere)
    rec = json.loads((project / ".piku" / "readcost.jsonl").read_text().splitlines()[0])
    assert rec["verdict"] == "block"


# MessageDisplay ----------------------------------------------------------------------

@pytest.fixture
def display(tmp_path, monkeypatch):
    """Run message_display in-process and capture the text it would judge."""
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    from readcost.config import Config
    from readcost.hooks import claude_code

    cfg = Config()
    cfg.hooks.display = "note"
    judged = []

    class Result:
        verdict = "pass"

    def fake_analyze(cfg, *, path, text=None, fmt=None, lines=None):
        judged.append(text)
        return Result()

    monkeypatch.setattr(claude_code, "analyze", fake_analyze)
    return lambda payload: claude_code.message_display(payload, cfg), judged


def test_message_display_joins_batches_in_index_order(display):
    run, judged = display
    run({"message_id": "m1", "index": 1, "final": False, "delta": "B "})
    run({"message_id": "m1", "index": 0, "final": False, "delta": "A "})
    run({"message_id": "m1", "index": 2, "final": True, "delta": "C"})
    assert judged == ["A B C"]


def test_message_display_resets_reused_key_at_index_zero(display):
    run, judged = display
    # No message_id: an interrupted message must not leak into the next one.
    run({"session_id": "s", "index": 0, "final": False, "delta": "old "})
    run({"session_id": "s", "index": 0, "final": False, "delta": "new "})
    run({"session_id": "s", "index": 1, "final": True, "delta": "text"})
    assert judged == ["new text"]


def test_message_display_keys_on_turn_id_without_message_id(display):
    run, judged = display
    run({"session_id": "s", "turn_id": "t1", "index": 0, "final": False, "delta": "one "})
    run({"session_id": "s", "turn_id": "t2", "index": 0, "final": False, "delta": "two "})
    run({"session_id": "s", "turn_id": "t1", "index": 1, "final": True, "delta": "end"})
    assert judged == ["one end"]


def test_message_display_prunes_stale_state(display, tmp_path):
    run, _ = display
    state = tmp_path / "data" / "readcost-display"
    state.mkdir(parents=True)
    stale = state / "gone.jsonl"
    stale.write_text("{}\n")
    old = time.time() - 2 * 86400
    os.utime(stale, (old, old))
    run({"message_id": "m2", "index": 0, "final": False, "delta": "x"})
    assert not stale.exists()


def test_message_display_accumulates_across_batches(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost.hooks]\ndisplay = "note"\n')
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    base = {"message_id": "m3", "cwd": str(tmp_path)}
    hook(["claude-code", "message-display"], {**base, "index": 0, "final": False, "delta": DENSE}, tmp_path, env)
    # The final batch alone is plain; only the joined message is dense.
    rc, out, err = hook(["claude-code", "message-display"],
                        {**base, "index": 1, "final": True, "delta": PLAIN}, tmp_path, env)
    assert rc == 0 and err == "" and "readcost:" in out["displayContent"]


# Plugin and settings ------------------------------------------------------------------

def test_plugin_leaves_message_display_out_and_drops_multiedit():
    cfg = json.loads((ROOT / "integrations/claude-code-plugin/hooks/hooks.json").read_text())
    assert "MessageDisplay" not in cfg["hooks"]
    matchers = [m.get("matcher", "") for groups in cfg["hooks"].values() for m in groups]
    assert not any("MultiEdit" in m for m in matchers)


# generic adapter errors ---------------------------------------------------------------

def test_generic_malformed_request_exit_2_with_error_field(tmp_path):
    rc, out, _ = hook(["generic"], None, tmp_path, raw="not json")
    assert rc == 2 and out["error"]
    rc, out, _ = hook(["generic"], {"text": "a", "path": "b"}, tmp_path)
    assert rc == 2 and "exactly one" in out["error"]


def test_generic_environment_error_exit_3_with_error_field(tmp_path):
    (tmp_path / "readcost.toml").write_text('[readcost]\nmodel = "no_such_spacy_model"\n')
    rc, out, _ = hook(["generic"], {"text": DENSE, "config": str(tmp_path / "readcost.toml")}, tmp_path)
    assert rc == 3 and "no_such_spacy_model" in out["error"]
