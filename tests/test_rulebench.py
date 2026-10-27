"""The per-rule benchmark in eval/rulebench/: references only, and the scorer works.

The sentences themselves are fetched by scripts/fetch_rulebench.py; the
repository keeps no third-party text, only its own rule examples.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

from readcost import Analyzer, Config

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "rulebench.py"
REFS = ROOT / "eval" / "rulebench" / "rulebench.jsonl"
OWN = "github.com/arclabs561/readcost/"


def _rulebench():
    spec = importlib.util.spec_from_file_location("rulebench", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def refs() -> list[dict]:
    return [json.loads(x) for x in REFS.read_text().splitlines() if x.strip()]


def test_references_hold_no_third_party_text():
    for item in refs():
        assert len(item["sha256"]) == 64 and item["source"].startswith("https://")
        if "text" in item:
            assert OWN in item["source"], item["source"]
            assert item["sha256"] == hashlib.sha256(" ".join(item["text"].split()).encode()).hexdigest()


def test_bench_covers_every_default_rule_with_both_labels():
    items = refs()
    defaults = {f for f in Analyzer(Config()).enabled if f != "long-sentence"}
    for rule in defaults:
        mine = [it for it in items if it["rule"] == rule]
        assert len(mine) >= 15, rule
        assert {it["expected"] for it in mine} == {"fire", "no-fire"}, rule


def test_scorer_runs_on_the_repositorys_own_items(tmp_path, capsys):
    rb = _rulebench()
    own = [it for it in refs() if "text" in it]
    bench = tmp_path / "rulebench.jsonl"
    bench.write_text("".join(json.dumps(it) + "\n" for it in own))
    scores = rb.score(rb.load(bench))
    assert sum(s["tp"] + s["fn"] + s["tn"] + s["fp"] for s in scores.values()) == len(own) > 0
    assert rb.main(["--bench", str(bench)]) == 0
    assert "| Rule |" in capsys.readouterr().out


def test_rule_and_sentence_identify_an_item():
    # One sentence can test two rules, so joins (labels, votes) must key on both.
    keys = [(it["rule"], it["sha256"]) for it in refs()]
    assert len(keys) == len(set(keys))
