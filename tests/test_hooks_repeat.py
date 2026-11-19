"""hooks.repeat: an agent hook reports a finding once per session and file."""

import json
import os
import time

import pytest

from cliproc import run_cli
from readcost.config import load_config
from readcost.features import Finding
from readcost.hooks import repeats

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")
# The same noun stack as DENSE's last sentence, with the words around it moved.
REWORDED = "By hand, we tune the shard compaction retry budget.\n"
OTHER = "The cache eviction policy threshold value stays fixed.\n"


@pytest.fixture
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    monkeypatch.setenv("READCOST_HOOK_STATE", str(d))
    return d


def hook(args, payload, cwd):
    proc = run_cli(["hook", *args], json.dumps(payload), cwd, dict(os.environ))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


def project(tmp_path, mode="advise", extra=""):
    d = tmp_path / "proj"
    d.mkdir()
    (d / "readcost.toml").write_text(f'[readcost.hooks]\nmode = "{mode}"\n{extra}')
    return d


def post(d, text, session="s1", **more):
    f = d / "README.md"
    f.write_text(text)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(f), "content": text}, "cwd": str(d), **more}
    if session is not None:
        payload["session_id"] = session
    return hook(["claude-code", "post-tool-use"], payload, d)[0]


def context(out):
    return out["hookSpecificOutput"]["additionalContext"]


def test_first_report_then_silence(tmp_path, state):
    d = project(tmp_path)
    first = post(d, DENSE)
    assert "stacked-nouns" in context(first) and "earlier" not in context(first)
    assert post(d, DENSE) is None
    assert list(state.glob("*.json"))  # it remembered, under the directory given


def test_small_rewrite_keeps_the_finding_and_a_new_one_is_reported(tmp_path, state):
    d = project(tmp_path)
    post(d, DENSE)
    assert post(d, REWORDED) is None  # same rule, same flagged words
    out = post(d, REWORDED + OTHER)
    msg = context(out)
    assert "readcost: 1 hard-to-read construction" in msg and "line 2 [stacked-nouns]" in msg
    assert "(1 finding reported earlier in this session is not repeated.)" in msg


def test_block_once_then_advise_in_one_line(tmp_path, state):
    d = project(tmp_path, "block")
    first = post(d, DENSE)
    assert first["decision"] == "block"
    second = post(d, DENSE)
    assert "decision" not in second
    note = context(second)
    assert "\n" not in note and "reported earlier in this session" in note and "does not hold" in note
    # A new finding in a still-blocked text blocks again, on the new finding only.
    third = post(d, DENSE + OTHER)
    assert third["decision"] == "block" and "[stacked-nouns]" in third["reason"]
    assert "[inline-list]" not in third["reason"] and "not repeated" in third["reason"]


def test_deny_once_then_allow_and_post_tool_use_notes_it(tmp_path, state):
    d = project(tmp_path, "block")
    payload = {"session_id": "s1", "tool_name": "Write", "cwd": str(d),
               "tool_input": {"file_path": str(d / "a.md"), "content": DENSE}}
    out, _ = hook(["claude-code", "pre-tool-use"], payload, d)
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "make the same edit again" in reason
    out, _ = hook(["claude-code", "pre-tool-use"], payload, d)
    assert out is None  # the same findings: allowed
    (d / "a.md").write_text(DENSE)
    out, _ = hook(["claude-code", "post-tool-use"], {**payload, "tool_response": {}}, d)
    assert "decision" not in out and "not blocked again" in context(out)


def test_edit_and_write_share_findings(tmp_path, state):
    """An Edit's new_string and the file after it name a finding the same way."""
    d = project(tmp_path, "block")
    f = d / "a.md"
    f.write_text("Intro.\n")
    payload = {"session_id": "s1", "tool_name": "Edit", "cwd": str(d),
               "tool_input": {"file_path": str(f), "old_string": "Intro.", "new_string": DENSE.strip()}}
    out, _ = hook(["claude-code", "pre-tool-use"], payload, d)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    f.write_text(DENSE)
    out, _ = hook(["claude-code", "post-tool-use"], payload, d)
    assert "decision" not in out


def test_without_a_session_every_report_repeats(tmp_path, state):
    d = project(tmp_path, "block")
    assert post(d, DENSE, session=None)["decision"] == "block"
    assert post(d, DENSE, session=None)["decision"] == "block"
    assert not state.exists()


def test_transcript_path_stands_in_for_session_id(tmp_path, state):
    d = project(tmp_path)
    assert post(d, DENSE, session=None, transcript_path="/t/1.jsonl")
    assert post(d, DENSE, session=None, transcript_path="/t/1.jsonl") is None


def test_sessions_and_subagents_do_not_share_memory(tmp_path, state):
    d = project(tmp_path)
    assert post(d, DENSE, session="s1")
    assert post(d, DENSE, session="s2")
    assert post(d, DENSE, session="s1", agent_id="agent-1")
    assert post(d, DENSE, session="s1") is None
    assert post(d, DENSE, session="s1", agent_id="agent-1") is None


def test_files_do_not_share_memory(tmp_path, state):
    d = project(tmp_path)
    assert post(d, DENSE)
    g = d / "b.md"
    g.write_text(DENSE)
    out, _ = hook(["claude-code", "post-tool-use"],
                  {"session_id": "s1", "tool_name": "Write", "cwd": str(d), "tool_input": {"file_path": str(g)}}, d)
    assert out


def test_repeat_always_is_the_old_behaviour(tmp_path, state):
    d = project(tmp_path, "block", 'repeat = "always"\n')
    assert post(d, DENSE)["decision"] == "block"
    assert post(d, DENSE)["decision"] == "block"
    assert not state.exists()


@pytest.mark.parametrize("garbage", ["not json", "[1, 2]", '{"format": 99, "files": {}}',
                                     '{"format": 1, "files": []}', "\udcff"])
def test_corrupted_state_fails_open(tmp_path, state, garbage):
    d = project(tmp_path)
    state.mkdir()
    path = state / f"{repeats.session_key({'session_id': 's1'})}.json"
    path.write_text(garbage, errors="surrogateescape")
    out = post(d, DENSE)
    assert "stacked-nouns" in context(out)
    assert json.loads(path.read_text())["format"] == repeats.FORMAT  # rewritten whole
    assert post(d, DENSE) is None


def test_unwritable_state_fails_open(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setenv("READCOST_HOOK_STATE", str(blocker / "state"))  # a directory under a file
    d = project(tmp_path)
    assert "stacked-nouns" in context(post(d, DENSE))
    assert "stacked-nouns" in context(post(d, DENSE))  # no memory, so it repeats


def test_stale_state_is_ignored_and_pruned(tmp_path, state):
    d = project(tmp_path)
    post(d, DENSE)
    path = next(state.glob("*.json"))
    old = time.time() - repeats.MAX_AGE - 60
    os.utime(path, (old, old))
    other = state / "other.json"
    other.write_text("{}")
    os.utime(other, (old, old))
    assert post(d, DENSE)  # a day later the finding is new again
    assert not other.exists()


def test_piku_reports_and_denies_once(tmp_path, state):
    d = project(tmp_path, "block")
    payload = {"hook_event_name": "PreToolUse", "session_id": "p1", "tool_name": "write_file",
               "tool_input": {"path": "README.md", "content": DENSE}, "cwd": str(d)}
    out, _ = hook(["piku", "pre-tool-use"], payload, d)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    out, _ = hook(["piku", "pre-tool-use"], payload, d)
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "allow" and "not blocked again" in spec["additionalContext"]


def test_piku_advise_is_silent_on_repeats(tmp_path, state):
    d = project(tmp_path)
    payload = {"session_id": "p1", "tool_name": "write_file",
               "tool_input": {"path": "README.md", "content": DENSE}, "cwd": str(d)}
    out, _ = hook(["piku", "pre-tool-use"], payload, d)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    out, _ = hook(["piku", "pre-tool-use"], payload, d)
    assert out is None


def _finding(feature, excerpt, line=1):
    return Finding(feature=feature, severity="warn", message="", excerpt=excerpt, sentence=excerpt,
                   path="a.md", line=line)


def test_finding_identity_ignores_case_punctuation_and_line():
    a = repeats.finding_id(_finding("stacked-nouns", "Compaction retry budget", 3))
    assert a == repeats.finding_id(_finding("stacked-nouns", "compaction  retry-budget", 40))
    assert a != repeats.finding_id(_finding("hyphen-compound", "compaction retry budget"))
    assert a != repeats.finding_id(_finding("stacked-nouns", "compaction retry limit"))


def test_state_holds_no_text_or_paths(tmp_path, state):
    d = project(tmp_path)
    post(d, DENSE)
    raw = next(state.glob("*.json")).read_text()
    assert "compaction" not in raw and "README" not in raw and "s1" not in raw


def test_repeat_setting_is_checked(tmp_path):
    bad, good = tmp_path / "bad", tmp_path / "good"
    for d in (bad, good):
        d.mkdir()
        (d / ".git").mkdir()  # stop the config search here
    (bad / "readcost.toml").write_text('[readcost.hooks]\nrepeat = "never"\n')
    with pytest.raises(ValueError, match="repeat must be one of once, always"):
        load_config(start=str(bad))
    assert load_config(start=str(good)).hooks.repeat == "once"
