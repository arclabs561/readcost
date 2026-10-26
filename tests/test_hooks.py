import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds.\n")
PLAIN = "The index stores one list of documents for each term.\n"


def hook(args, payload, cwd, env=None):
    proc = subprocess.run([sys.executable, "-m", "readcost", "hook", *args],
                          input=json.dumps(payload), capture_output=True, text=True, cwd=cwd,
                          env={**os.environ, **(env or {})})
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, out, proc.stderr


def write_config(tmp: Path, body: str) -> None:
    (tmp / "readcost.toml").write_text(body)


def test_claude_post_tool_use_advises_on_dense_markdown(tmp_path):
    f = tmp_path / "README.md"
    f.write_text(DENSE)
    rc, out, _ = hook(["claude-code", "post-tool-use"],
                      {"tool_name": "Write", "tool_input": {"file_path": str(f), "content": DENSE},
                       "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUse" and "stacked-nouns" in ctx["additionalContext"]


def test_claude_post_tool_use_blocks_only_in_block_mode(tmp_path):
    write_config(tmp_path, '[readcost.hooks]\nmode = "block"\n')
    f = tmp_path / "README.md"
    f.write_text(DENSE)
    _, out, _ = hook(["claude-code", "post-tool-use"],
                     {"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(tmp_path)}, tmp_path)
    assert out["decision"] == "block" and "readcost" in out["reason"]


def test_claude_post_tool_use_silent_on_plain_or_unwatched(tmp_path):
    f = tmp_path / "README.md"
    f.write_text(PLAIN)
    rc, out, _ = hook(["claude-code", "post-tool-use"],
                      {"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and out is None
    g = tmp_path / "main.rs"
    g.write_text(DENSE)
    rc, out, _ = hook(["claude-code", "post-tool-use"],
                      {"tool_name": "Write", "tool_input": {"file_path": str(g)}, "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0 and out is None


def test_claude_edit_checks_only_edited_lines(tmp_path):
    f = tmp_path / "README.md"
    f.write_text(DENSE + "\n" + PLAIN)
    _, out, _ = hook(["claude-code", "post-tool-use"],
                     {"tool_name": "Edit", "tool_input": {"file_path": str(f), "old_string": "x",
                                                          "new_string": PLAIN.strip()},
                      "cwd": str(tmp_path)}, tmp_path)
    assert out is None


def test_claude_pre_tool_use_denies_in_block_mode(tmp_path):
    write_config(tmp_path, '[readcost.hooks]\nmode = "block"\n')
    _, out, _ = hook(["claude-code", "pre-tool-use"],
                     {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "a.md"), "content": DENSE},
                      "cwd": str(tmp_path)}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_claude_stop_revise_once(tmp_path):
    write_config(tmp_path, '[readcost.hooks]\nstop = "revise"\n')
    payload = {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": DENSE,
               "cwd": str(tmp_path)}
    _, out, _ = hook(["claude-code", "stop"], payload, tmp_path)
    assert out["decision"] == "block"
    payload["stop_hook_active"] = True
    _, out, _ = hook(["claude-code", "stop"], payload, tmp_path)
    assert out is None


def test_claude_stop_report_uses_system_message(tmp_path):
    write_config(tmp_path, '[readcost.hooks]\nstop = "report"\n')
    _, out, _ = hook(["claude-code", "stop"], {"last_assistant_message": DENSE, "cwd": str(tmp_path)}, tmp_path)
    assert set(out) == {"systemMessage"}


def test_claude_message_display_accumulates_and_notes(tmp_path):
    write_config(tmp_path, '[readcost.hooks]\ndisplay = "note"\n')
    env = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    half = len(DENSE) // 2
    base = {"message_id": "m1", "cwd": str(tmp_path)}
    _, out, _ = hook(["claude-code", "message-display"], {**base, "index": 0, "final": False, "delta": DENSE[:half]}, tmp_path, env)
    assert out is None
    _, out, _ = hook(["claude-code", "message-display"], {**base, "index": 1, "final": True, "delta": DENSE[half:]}, tmp_path, env)
    assert out["displayContent"].startswith(DENSE[half:]) and "readcost:" in out["displayContent"]


def test_piku_pre_tool_use_allows_with_context(tmp_path):
    rc, out, _ = hook(["piku", "pre-tool-use"],
                      {"hook_event_name": "PreToolUse", "tool_name": "write_file",
                       "tool_input": {"path": "README.md", "content": DENSE}, "cwd": str(tmp_path)}, tmp_path)
    assert rc == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "readcost" in out["hookSpecificOutput"]["additionalContext"]


def test_piku_post_tool_use_logs(tmp_path):
    (tmp_path / "README.md").write_text(DENSE)
    hook(["piku", "post-tool-use"], {"tool_name": "write_file", "tool_input": {"path": "README.md"},
                                     "tool_response": {"output": "ok", "is_error": False},
                                     "cwd": str(tmp_path)}, tmp_path)
    rec = json.loads((tmp_path / ".piku" / "readcost.jsonl").read_text().splitlines()[0])
    assert rec["verdict"] == "block" and rec["findings"]


def test_generic_protocol(tmp_path):
    rc, out, _ = hook(["generic"], {"text": DENSE}, tmp_path)
    assert rc == 0 and out["verdict"] == "block" and out["feedback"].startswith("readcost:")
    rc, _, _ = hook(["generic"], {"text": "a", "path": "b"}, tmp_path)
    assert rc == 2


def test_fail_open_on_garbage_input(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "readcost", "hook", "claude-code", "post-tool-use"],
                          input="not json", capture_output=True, text=True, cwd=tmp_path)
    assert proc.returncode == 0 and proc.stdout == ""


@pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, reason="git missing")
def test_git_pre_commit_changed_lines(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "readcost.toml").write_text('[readcost.hooks]\nmode = "block"\n')
    (tmp_path / "README.md").write_text(PLAIN)
    git("add", ".")
    git("commit", "-qm", "init")
    (tmp_path / "README.md").write_text(PLAIN + "\n" + DENSE)
    git("add", "README.md")
    proc = subprocess.run([sys.executable, "-m", "readcost", "hook", "git", "pre-commit"],
                          capture_output=True, text=True, cwd=tmp_path)
    assert proc.returncode == 1 and "stacked-nouns" in proc.stderr
