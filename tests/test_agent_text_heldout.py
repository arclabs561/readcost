"""Stage 2's held-out test: its arms, decision rule and job, with stub models."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ho = _load("eval_agent_text_heldout")
at, ea = ho.at, ho.ea

DENSE = ("The worker pool shard compaction retry budget is tuned by hand before each release. "
         "Operators set the cache eviction policy threshold value in the cluster config file. ")
PARA = DENSE + " ".join(f"The service writes a short {n} log line for each request it handles. "
                        f"It keeps the last {n} hours of logs on disk." for n in ("two", "three", "four"))
MARK = "the threshold at which the cache evicts"
RS = {"fixes": {**at.base_fixes(), "stacked-nouns": at.FIX_CANDIDATES["stacked-nouns"][0]}, "scope": "",
      "precision": False}


def test_r0_is_readcosts_output_and_rs_is_the_search_choice(analyzer):
    from readcost import report
    pr = ho.prompts_for(analyzer, {"id": "a", "text": PARA}, RS)
    result = ea.check(analyzer, PARA)
    assert pr["R0"] == at.prompt(PARA, report.agent([result], feedback_link=False))
    assert MARK in pr["RS"] and "raters accepted" not in pr["RS"] and pr["C"] == at.anchor_prompt(PARA)


def test_the_decision_follows_the_plan():
    assert ho.decide((0.55, 0.52, 0.58), (0.0, -0.02, 0.02))["replace"]
    assert ho.decide((0.48, 0.45, 0.51), (-0.05, -0.08, -0.01))["replace"]        # reads as well, fewer changes
    assert not ho.decide((0.48, 0.45, 0.51), (0.0, -0.02, 0.02))["replace"]       # no advantage either way
    assert not ho.decide((0.6, 0.55, 0.65), (0.02, -0.01, 0.05))["replace"]       # changes content more
    assert not ho.decide(None, None)["replace"]


class FakeAsk:
    """RS edits start "Good" and win, with no lost fact; others tie and lose one. Model "bad" never parses."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        if model == "bad":
            return None, {"error": "no JSON object"}
        if "text" in schema["properties"]:
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            tag = "Good" if MARK in prompt else ("Plain" if "prose checker" in prompt else "Bare")
            return {"text": f"{tag} ({model}): {original}"}, {}
        if "easier" in schema["properties"]:
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nGive your reason")[0]
            a, b = one.startswith("Good"), two.startswith("Good")
            return {"reason": "r", "easier": "tie" if a == b else "1" if a else "2"}, {}
        revision = prompt.split("Revision:\n", 1)[1]
        return {"lost": [] if revision.startswith("Good") else ["x"], "added": [], "changed": []}, {}


def test_the_job_falls_back_for_a_judge_that_does_not_parse_and_decides(tmp_path, analyzer, monkeypatch):
    job = _load("agent_text_heldout_job")
    monkeypatch.setattr(job.ho, "JUDGES", [job.ho.JUDGES[0], "microsoft/phi-4"])
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(3)]

    def fetch(pointers, ref):
        ref.mkdir(parents=True, exist_ok=True)
        (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (ref / "missing.json").write_text("[]")
    fake, loaded = FakeAsk(), []

    def backend(model, logs):
        loaded.append(model)

        class B:
            def ask(self, m, prompt, schema, system=None):
                return fake("bad" if m == "microsoft/phi-4" else m, prompt, schema, system)

            def stop(self):
                pass
        return B()
    rsf = tmp_path / "rs.json"
    rsf.write_text(json.dumps(RS))
    ptr = tmp_path / "ptr"
    ptr.mkdir()
    ref = tmp_path / "ref"
    rc = job.main(["--run-id", "h-1", "--hours", "1.25", "--ref", str(ref), "--pointers", str(ptr), "--r-star", str(rsf),
                   "--no-upload", "--workers", "4"], backends={"server": backend}, fetch=fetch, verify=lambda: 0,
                  analyzer=analyzer, env={}, revision=lambda m, t: "0" * 40)
    assert rc == 0
    log = json.loads((ref / "run.json").read_text())
    assert loaded == job.ho.EDITORS + [job.ho.JUDGES[0], "microsoft/phi-4", job.ho.FALLBACK]
    assert log["judges_used"] == [job.ho.JUDGES[0], job.ho.FALLBACK] and log["fallbacks"][0]["failed_share"] == 1.0
    out = json.loads((ref / "heldout.json").read_text())
    assert out["complete"] and out["results"]["decision"]["replace"]
    assert out["results"]["pairs"]["RSR0"]["estimate"][0] == 1.0
    assert "| **R* replaces today's text** | **yes** |" in (ref / "heldout.md").read_text()
