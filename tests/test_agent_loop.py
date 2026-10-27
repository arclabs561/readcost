"""The edit-loop evaluation's mechanics, with a stub in place of the model."""

import importlib.util
from pathlib import Path

from readcost import Analyzer, Config

ROOT = Path(__file__).resolve().parent.parent
DENSE = "We tune the shard compaction retry budget by hand before each release."
PLAIN = "We tune how many times a shard retries compaction by hand before each release."


def _script():
    spec = importlib.util.spec_from_file_location("eval_agent_loop", ROOT / "scripts" / "eval_agent_loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_loop_stops_when_the_text_has_no_findings():
    m = _script()
    seen = []

    def rewrite(text, fb):
        seen.append(fb)
        return PLAIN
    trace = m.loop(Analyzer(Config()), DENSE, rewrite, "holds")
    assert [r["round"] for r in trace] == [0, 1]
    assert trace[0]["findings"] and not trace[1]["findings"]
    assert "where the finding holds" in seen[0]


def test_loop_runs_out_of_rounds_and_churn_counts_a_returning_finding():
    m = _script()
    swap = "We tune the storage-shrink job by hand before each release."  # a different finding
    texts = iter([swap, DENSE, swap])
    trace = m.loop(Analyzer(Config()), DENSE, lambda t, fb: next(texts), "plain", rounds=3)
    assert len(trace) == 4  # the original and three rewrites, never clean
    # Round 1 fixes the stack and introduces a hyphen compound; round 2 brings
    # the stack back and drops the compound; round 3 does the reverse.
    assert m.churn(trace) == {"fixed": 3, "introduced": 3, "returned": 2}


def test_plain_feedback_drops_the_precision_note_and_the_hedge():
    m = _script()
    r = Analyzer(Config()).check_text(DENSE, "markdown")
    plain, holds = m.feedback(r, "plain"), m.feedback(r, "holds")
    assert "raters accepted" in holds and "raters accepted" not in plain
    assert "where the finding holds" not in plain and "Rewrite these sentences" in plain
