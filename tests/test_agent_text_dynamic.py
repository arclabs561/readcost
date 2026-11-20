"""Stage 3: fix texts that use the finding's words, the cascade, successive halving, calibration and job."""

import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dy = _load("eval_agent_text_dynamic")
at, ea = dy.at, dy.ea

DENSE = ("The worker pool shard compaction retry budget is tuned by hand before each release. "
         "Operators set the cache eviction policy threshold value in the cluster config file. ")
PARA = DENSE + " ".join(f"The service writes a short {n} log line for each request it handles. "
                        f"It keeps the last {n} hours of logs on disk." for n in ("two", "three", "four"))


def test_the_seed_is_readcosts_output_and_a_candidate_changes_only_its_rule(analyzer):
    from readcost import report
    result = ea.check(analyzer, PARA)
    seed = dy.render(result)
    assert seed == report.agent([result], feedback_link=False)
    c1 = dy.render(result, "stacked-nouns", "c1")
    changed = [(a, b) for a, b in zip(seed.splitlines(), c1.splitlines()) if a != b]
    assert changed and all("[stacked-nouns]" in a and "Fix: Unpack '" in b for a, b in changed)
    assert "raters accepted" in seed and "raters accepted" not in dy.render(result, "note", "c1")
    assert dy.render(result, "note", "c1") == at.feedback(result, dy.NOTE_OFF)


def test_a_long_quote_falls_back_to_the_form_without_one():
    class F:
        feature, message, excerpt, sentence, suggestion = ("stacked-nouns", "3 nouns stacked: 'a b c'", "a b c",
                                                           "x.", "static")
    assert dy.candidate_fix(F, "c1") == "Unpack 'a b c': say how its nouns relate, with a preposition or a verb."
    F.message = "9 nouns stacked: '" + " ".join(["w"] * 9) + "'"
    assert dy.candidate_fix(F, "c1").startswith("Unpack the run of nouns")

    class L:
        feature, message, excerpt, sentence, suggestion = ("long-dependency", "'note' and 'read' are 16 words apart",
                                                           "", "A note is read.", "static")
    assert dy.candidate_fix(L, "c1").startswith("Bring 'note' and 'read' together")


def test_answer_probabilities_come_from_the_answer_token_and_are_renormalized():
    toks = [{"token": '{"', "logprob": 0}, {"token": "easier", "logprob": 0}, {"token": '":', "logprob": 0},
            {"token": ' "', "logprob": 0},
            {"token": "1", "logprob": math.log(0.6), "top_logprobs": [
                {"token": "1", "logprob": math.log(0.6)}, {"token": "2", "logprob": math.log(0.2)},
                {"token": "tie", "logprob": math.log(0.1)}, {"token": "x", "logprob": math.log(0.1)}]}]
    p = dy.answer_probs(toks)
    assert abs(p["1"] - 0.6 / 0.9) < 1e-9 and abs(sum(p.values()) - 1) < 1e-9
    merged = [{"token": '{"easier": ', "logprob": 0},
              {"token": '"2', "logprob": math.log(0.7), "top_logprobs": [
                  {"token": '"2', "logprob": math.log(0.7)}, {"token": '"t', "logprob": math.log(0.3)}]}]
    q = dy.answer_probs(merged)
    assert abs(q["2"] - 0.7) < 1e-9 and abs(q["tie"] - 0.3) < 1e-9 and dy.answer_probs([]) is None


class FakeAsk:
    """Edits made with stacked-nouns c1 start "Good" and are preferred with probability 0.9; others tie.
    C edits (no checker block) start "Bare" and lose a fact; every other edit keeps its facts."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        if "text" in schema["properties"]:
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            if "prose checker" not in prompt:
                return {"text": f"Bare ({model}): {original}"}, {}
            tag = "Good" if "Fix: Unpack '" in prompt else "Plain"
            return {"text": f"{tag} [{ea.sha(prompt)[:8]}] ({model}): {original}"}, {}
        if "easier" in schema["properties"]:
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nAnswer")[0]
            a, b = one.startswith("Good"), two.startswith("Good")
            if a == b:
                return {"easier": "tie"}, {"probs": {"1": 0.45, "2": 0.45, "tie": 0.1}}
            p = {"1": 0.9, "2": 0.05, "tie": 0.05} if a else {"1": 0.05, "2": 0.9, "tie": 0.05}
            return {"easier": "1" if a else "2"}, {"probs": p}
        if "score" in schema["properties"]:
            return {"score": 6 if prompt.split("Paragraph:\n", 1)[1].startswith("Good") else 4}, {}
        revision = prompt.split("Revision:\n", 1)[1]
        return {"lost": ["x"] if revision.startswith("Bare") else [], "added": [], "changed": []}, {}


def _ref(tmp_path, n):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = [{"id": f"p{i:02d}", "text": PARA.replace("release", f"release {i}")} for i in range(n)]
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return ref, rows


def test_halving_keeps_the_candidate_that_helps_and_the_audit_set_confirms_it(tmp_path, analyzer, monkeypatch):
    monkeypatch.setattr(dy, "AUDIT_N", 2)
    monkeypatch.setattr(dy, "CALIB_N", 2)
    ref, rows = _ref(tmp_path, 8)
    eds, js = ["e1", "e2"], ["j1", "j2"]
    client = ea.Client(ref / "replies.jsonl", ask=FakeAsk(), count_cost=False)
    for p in rows:   # the C anchors, cached as in the real run
        for ed in eds:
            client(ed, ea.SYSTEM, at.anchor_prompt(p["text"]), ea.TEXT_SCHEMA)
    status = dy.run(ref, client, analyzer, eds, js, workers=2)
    assert status == {"edits": True, "calib": True, "facts": True, "screen": True, "confirm": True}
    pl = dy.plan(analyzer, ref)
    assert len(pl["audit"]) == 2 and len(pl["groups"]["note"]["screen"]) == 2
    res = dy.analyse(client, analyzer, pl, eds, js)
    sn = res["species"]["stacked-nouns"]
    assert sn["go_on"] == ["c1"] and sn["winner"] == "c1"
    assert abs(sn["confirm"]["c1"][0] - 0.85) < 1e-9 and abs(sn["audit"]["c1"][0] - 0.85) < 1e-9   # 2(0.9 + 0.05/2) - 1
    assert sn["screen"]["c2"] == (0.0, 0.0, 0.0)
    assert res["species"]["note"]["winner"] is None
    cal = res["calibration"]["j1"]
    assert cal["pass"] and cal["facts_gap"] == 1.0 and cal["null_rate"] == 0.0 and cal["split_rate"] == 0.0
    text = dy.report(res, status, {"calls": client.calls, "new": 0})
    assert "| stacked-nouns | c1 |" in text and "Winners: stacked-nouns c1." in text
    again = FakeAsk()
    dy.run(ref, ea.Client(ref / "replies.jsonl", ask=again, count_cost=False), analyzer, eds, js)
    assert again.calls == []


def test_an_edit_that_changes_content_is_scored_by_facts_alone(tmp_path, analyzer, monkeypatch):
    monkeypatch.setattr(dy, "AUDIT_N", 0)
    ref, rows = _ref(tmp_path, 1)
    client = ea.Client(ref / "replies.jsonl", ask=FakeAsk(), count_cost=False)
    pl = dy.plan(analyzer, ref)
    pid = rows[0]["id"]
    text = pl["texts"][pid]
    for k in [(pid, "seed", "v0"), (pid, "stacked-nouns", "c1")]:
        client("e1", ea.SYSTEM, pl["prompts"][k], ea.TEXT_SCHEMA)
    s_edit = at.edit_text(client, "e1", pl["prompts"][(pid, "seed", "v0")])
    c_edit = at.edit_text(client, "e1", pl["prompts"][(pid, "stacked-nouns", "c1")])
    lost = ea.Client(tmp_path / "x.jsonl", ask=lambda *a, **k: ({"lost": ["y"], "added": [], "changed": []}, {}))
    for j in ("j1", "j2"):
        row = lost(j, None, ea.fact_prompt(text, s_edit), ea.fact_schema())
        client.ok[client.key(j, None, ea.fact_prompt(text, s_edit))] = {"data": row, "meta": {}}
        client(j, None, ea.fact_prompt(text, c_edit), ea.fact_schema())
    u = dy.unit(client, pl, pid, "e1", "stacked-nouns", "c1", ["j1", "j2"])
    assert u["delta"] == 1.0 and u["judged"] is False
    assert dy.needs_reading(client, pl, pid, "e1", "stacked-nouns", "c1", ["j1", "j2"]) is None


def test_shrinkage_pulls_a_noisy_gain_to_zero():
    assert dy.shrink((0.05, -0.05, 0.15)) == 0.0
    assert 0 < dy.shrink((0.3, 0.2, 0.4)) < 0.3 and dy.shrink(None) is None


def test_the_job_checks_the_cache_loads_eight_models_and_reports(tmp_path, analyzer, monkeypatch):
    job = _load("agent_text_dynamic_job")
    monkeypatch.setattr(job.dy, "AUDIT_N", 1)
    monkeypatch.setattr(job.dy, "CALIB_N", 1)
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(4)]
    seedf = tmp_path / "seed.jsonl"
    seedf.write_text("")
    c = ea.Client(seedf, ask=FakeAsk(), count_cost=False)
    for p in rows:
        result = ea.check(analyzer, p["text"])
        for ed in job.dy.EDITORS:
            c(ed, ea.SYSTEM, at.anchor_prompt(p["text"]), ea.TEXT_SCHEMA)
            c(ed, ea.SYSTEM, at.prompt(p["text"], dy.render(result)), ea.TEXT_SCHEMA)
            c(ed, ea.SYSTEM, at.prompt(p["text"], dy.render(result, "note", "c1")), ea.TEXT_SCHEMA)

    def fetch(pointers, ref):
        ref.mkdir(parents=True, exist_ok=True)
        (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (rows if pointers.name == "a" else [])))
        (ref / "missing.json").write_text("[]")
    loaded, asked = [], []

    def backend(model, logs):
        loaded.append(model)

        class B:
            ask = FakeAsk()

            def stop(self):
                pass
        return B()
    ref = tmp_path / "ref"
    rc = job.main(["--run-id", "d-1", "--hours", "1.5", "--ref", str(ref), "--no-upload", "--workers", "4"],
                  backends={"server": backend}, fetch=fetch, verify=lambda: 0, analyzer=analyzer, env={},
                  downloader=lambda f, t, d: asked.append(f) or seedf, pointers=(tmp_path / "a", tmp_path / "b"))
    assert rc == 0 and asked == ["agent-text-search/main-1"]
    assert loaded == job.dy.EDITORS + job.dy.JUDGES * 3
    log = json.loads((ref / "run.json").read_text())
    assert log["expected_in_cache"]["found"] == log["expected_in_cache"]["of"] > 0
    out = json.loads((ref / "dynamic.json").read_text())
    assert out["complete"] and out["results"]["species"]["stacked-nouns"]["winner"] == "c1"
    assert "Winners: stacked-nouns c1." in (ref / "dynamic.md").read_text()


def test_the_job_stops_without_the_expected_cache(tmp_path, analyzer):
    job = _load("agent_text_dynamic_job")
    rows = [{"id": "p0", "text": PARA}]
    seedf = tmp_path / "seed.jsonl"
    seedf.write_text("")

    def fetch(pointers, ref):
        ref.mkdir(parents=True, exist_ok=True)
        (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (rows if pointers.name == "a" else [])))
        (ref / "missing.json").write_text("[]")
    loaded = []
    rc = job.main(["--run-id", "d", "--hours", "1", "--ref", str(tmp_path / "ref"), "--no-upload"],
                  backends={"server": lambda m, logs: loaded.append(m)}, fetch=fetch, verify=lambda: 0,
                  analyzer=analyzer, env={}, downloader=lambda f, t, d: seedf,
                  pointers=(tmp_path / "a", tmp_path / "b"))
    assert rc == 1 and loaded == []
