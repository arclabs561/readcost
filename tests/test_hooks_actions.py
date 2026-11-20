"""hooks.track: per-rule counts of how often findings the agent hooks reported were acted on."""

import json
import os
import time

import pytest
from cliproc import run_cli

from readcost.config import load_config
from readcost.features import Finding
from readcost.hooks import actions, repeats

# As in test_hooks_repeat: dense enough to be reported, with a noun stack in its last sentence.
HEAD = ("It does not own indexing, segment selection, compaction, or reader visibility. "
        "The example prints the first snapshot-search cost with persisted region-index sidecars "
        "present versus after deleting those sidecars and forcing source-segment rebuilds. ")
DENSE = HEAD + "We tune the shard compaction retry budget by hand.\n"
FIXED = HEAD + "We tune by hand how often a shard retries compaction.\n"
PLAIN = "The service writes a short log line for each request it handles.\n"


@pytest.fixture
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    monkeypatch.setenv("READCOST_HOOK_STATE", str(d))
    return d


def hook(args, payload, cwd):
    proc = run_cli(["hook", *args], json.dumps(payload), cwd, dict(os.environ))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def project(tmp_path, extra=""):
    d = tmp_path / "proj"
    d.mkdir()
    (d / "readcost.toml").write_text(f'[readcost.hooks]\nmode = "advise"\n{extra}')
    return d


def post(d, text, session="s1"):
    f = d / "README.md"
    f.write_text(text)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(f), "content": text}, "cwd": str(d)}
    if session is not None:
        payload["session_id"] = session
    return hook(["claude-code", "post-tool-use"], payload, d)


def stats(d):
    proc = run_cli(["stats", "-o", "json"], "", d, dict(os.environ))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["rules"]


def test_a_finding_the_next_edit_removes_counts_as_acted_on(tmp_path, state):
    d = project(tmp_path)
    assert "stacked-nouns" in post(d, DENSE + PLAIN)["hookSpecificOutput"]["additionalContext"]
    assert stats(d)["stacked-nouns"] == {"reported": 1, "resolved": 0, "reintroduced": 0, "acted": 0,
                                         "ignored": 1, "action_rate": 0.0}
    post(d, FIXED + PLAIN)
    assert stats(d)["stacked-nouns"]["acted"] == 1 and stats(d)["stacked-nouns"]["action_rate"] == 1.0
    post(d, DENSE + PLAIN)                       # the stack comes back: reported before, so not repeated
    row = stats(d)["stacked-nouns"]
    assert row["reintroduced"] == 1 and row["acted"] == 0 and row["reported"] == 1
    # Only hashes and counters are written: no text and no paths.
    for p in state.iterdir():
        body = p.read_text() if p.suffix == ".json" else ""
        assert "shard" not in body and "README" not in body and str(d) not in body


def test_an_edit_that_keeps_the_flagged_words_is_not_acted_on(tmp_path, state):
    d = project(tmp_path)
    post(d, DENSE + PLAIN)
    post(d, HEAD + "By hand, we tune the shard compaction retry budget.\n" + PLAIN)
    assert stats(d)["stacked-nouns"]["acted"] == 0


def test_no_session_or_track_off_writes_nothing(tmp_path, state):
    d = project(tmp_path)
    post(d, DENSE + PLAIN, session=None)
    assert stats(d) == {}
    e = tmp_path / "other"
    e.mkdir()
    (e / "readcost.toml").write_text('[readcost.hooks]\nmode = "advise"\ntrack = false\n')
    post(e, DENSE + PLAIN)
    assert stats(e) == {} and not (state / actions.STATS).exists()


def test_the_ledger_records_each_finding_once_and_classifies_by_words(tmp_path, state):
    cfg = load_config(start=str(tmp_path))
    f = Finding(feature="stacked-nouns", severity="warn", message="m", excerpt="shard compaction retry budget",
                sentence="We tune the shard compaction retry budget.", path="p.md", line=1)
    led = actions.Ledger({"session_id": "x"}, cfg, "p.md", str(tmp_path))
    led.record([f, f])
    actions.Ledger({"session_id": "x"}, cfg, "p.md", str(tmp_path)).record([f])
    assert actions.stats()["stacked-nouns"]["reported"] == 1
    actions.Ledger({"session_id": "x"}, cfg, "p.md", str(tmp_path)).observe("Shard compaction, retry budget!")
    assert actions.stats()["stacked-nouns"]["resolved"] == 0   # same words, punctuation aside
    actions.Ledger({"session_id": "x"}, cfg, "p.md", str(tmp_path)).observe("Nothing left here.")
    assert actions.stats()["stacked-nouns"]["resolved"] == 1
    # Another file of the same session is a different ledger entry.
    actions.Ledger({"session_id": "x"}, cfg, "q.md", str(tmp_path)).observe("Nothing here either.")
    assert actions.stats()["stacked-nouns"]["resolved"] == 1


def test_prune_drops_old_session_ledgers_but_keeps_the_counters(tmp_path, state):
    cfg = load_config(start=str(tmp_path))
    f = Finding(feature="inline-list", severity="info", message="m", excerpt="a, b, c and d", sentence="s",
                path="p.md", line=1)
    actions.Ledger({"session_id": "old"}, cfg, "p.md", str(tmp_path)).record([f])
    ledgers = [p for p in state.iterdir() if p.name.endswith(".actions.json")]
    assert len(ledgers) == 1 and repeats._OURS.fullmatch(ledgers[0].name)
    past = time.time() - repeats.MAX_AGE - 10
    for p in state.iterdir():
        os.utime(p, (past, past))
    repeats._prune(state)
    left = {p.name for p in state.iterdir()}
    assert actions.STATS in left and not any(n.endswith(".actions.json") for n in left)
    assert actions.stats()["inline-list"]["reported"] == 1


def test_stats_text_and_reset(tmp_path, state):
    d = project(tmp_path)
    proc = run_cli(["stats"], "", d, dict(os.environ))
    assert proc.returncode == 0 and "no hook findings tracked yet" in proc.stdout
    post(d, DENSE + PLAIN)
    proc = run_cli(["stats"], "", d, dict(os.environ))
    assert "stacked-nouns" in proc.stdout and "0 of " in proc.stdout and "findings acted on" in proc.stdout
    proc = run_cli(["stats", "--reset"], "", d, dict(os.environ))
    assert "deleted" in proc.stdout and stats(d) == {}


def test_a_piku_write_is_recorded_before_and_checked_after(tmp_path, state):
    d = project(tmp_path)
    f = d / "README.md"
    pre = {"tool_name": "write_file", "tool_input": {"path": "README.md", "content": DENSE + PLAIN},
           "cwd": str(d), "session_id": "p1"}
    hook(["piku", "pre-tool-use"], pre, d)
    assert stats(d)["stacked-nouns"]["reported"] == 1
    f.write_text(FIXED + PLAIN)
    hook(["piku", "post-tool-use"], {**pre, "tool_input": {"path": "README.md", "content": FIXED + PLAIN}}, d)
    assert stats(d)["stacked-nouns"]["acted"] == 1
