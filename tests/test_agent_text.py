"""The agent feedback factorial: its design, the variant texts, decoys, run, analysis and job, with stub models."""

import importlib.util
import itertools
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


at = _load("eval_agent_text")
ea = at.ea

DENSE = ("The worker pool shard compaction retry budget is tuned by hand before each release. "
         "Operators set the cache eviction policy threshold value in the cluster config file. ")
FILLER = ("The service writes a short log line for each request it handles. "
          "It keeps the last hour of logs on disk. ")
PARA = (DENSE + " ".join(FILLER.replace("hour", f"{n} hours").replace("short", f"short {n}")
                         for n in ("two", "three", "four", "five", "six", "seven")))


def test_the_design_is_a_resolution_v_half_fraction_with_r0_in_it():
    arms = at.ARMS
    assert len(arms) == 16 and len({a["name"] for a in arms}) == 16 and at.R0 in {a["name"] for a in arms}
    for f in at.FACTORS:
        assert sum(a[f] for a in arms) == 0
    for f, g in itertools.combinations(at.FACTORS, 2):
        assert sum(a[f] * a[g] for a in arms) == 0                  # main effects orthogonal
    for pair in itertools.combinations(itertools.combinations(at.FACTORS, 2), 2):
        (a1, b1), (a2, b2) = pair
        assert sum(a[a1] * a[b1] * a[a2] * a[b2] for a in arms) == 0 or {a1, b1} & {a2, b2}
    assert all(a["X"] == -a["H"] * a["S"] * a["F"] * a["P"] for a in arms)
    assert len(at.DECOY_ARMS) == 8 and all(a["X"] < 0 for a in at.DECOY_ARMS)


def test_r0_is_what_readcost_prints_and_each_factor_changes_its_part(analyzer):
    from readcost import report
    many = " ".join([DENSE] * 6 + [FILLER])
    for text in (PARA, many):
        result = ea.check(analyzer, text)
        assert at.feedback(result, at.LEVELS[at.R0]) == report.agent([result], feedback_link=False)
    result = ea.check(analyzer, PARA)
    r0 = at.feedback(result, at.LEVELS[at.R0])
    r0_levels = {f: at.LEVELS[at.R0][f] for f in at.FACTORS}
    inform = at.feedback(result, r0_levels | {"H": -1, "P": -1})
    assert "Rewrite these sentences" in r0 and "Rewrite these sentences" not in inform
    assert "raters accepted" in r0 and "raters accepted" not in inform
    scoped = at.feedback(result, r0_levels | {"S": 1, "F": -1})
    assert at.SCOPE.strip() in scoped.splitlines()[0] and "Fix: " + at.GENERIC_FIX in scoped
    titled = at.feedback(result, {"H": 1, "S": -1, "F": 1, "P": 1, "X": -1})
    assert "[stacked-nouns] Three or more nouns in a row (raters accepted" in titled
    assert "nouns stacked" in r0 and "nouns stacked" not in titled


def test_a_decoy_is_one_more_line_like_the_others_at_its_slot(analyzer):
    p = {"id": "d1", "text": PARA}
    d = at.decoy_for(analyzer, p)
    assert d == at.decoy_for(analyzer, p) and d["sentence"] != d["control"]
    assert PARA.count(d["sentence"]) == 1 and PARA.count(d["control"]) == 1
    result = ea.check(analyzer, PARA)
    arm = at.DECOY_ARMS[0]
    plain, with_d = at.feedback(result, arm), at.feedback(result, arm, d)
    lines = with_d.splitlines()
    assert len(lines) == len(plain.splitlines()) + 1
    n = len(result.findings)
    assert lines[0].startswith(f"readcost: {n + 1} hard-to-read constructions")
    from readcost.features import FEATURES
    assert lines[1 + d["slot"]].startswith(f"- line {d['line']} [{d['rule']}] {FEATURES[d['rule']].title}")
    assert at.rewrote(d["sentence"], PARA.replace(d["sentence"], "Gone.")) and not at.rewrote(d["sentence"], PARA)


class FakeAsk:
    """Edits: "Scoped" when the scope line is there, else "Open". C (no checker block) only tags.
    Judges prefer a "Scoped" edit to C and tie otherwise; fact checks list a lost fact in "Open" edits."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        meta = {"served": model}
        if "text" in schema["properties"]:
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            if "prose checker" not in prompt:
                return {"text": f"{original} ({model})"}, meta
            tag = "Scoped" if at.SCOPE.strip() in prompt else "Open"
            return {"text": f"{tag} ({model}) [{ea.sha(prompt)[:8]}]: {original}"}, meta
        if "easier" in schema["properties"]:
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nGive your reason")[0]
            a, b = one.startswith("Scoped"), two.startswith("Scoped")
            return {"reason": "r", "easier": "tie" if a == b else "1" if a else "2"}, meta
        revision = prompt.split("Revision:\n", 1)[1]
        return {"lost": ["x"] if revision.startswith("Open") else [], "added": [], "changed": []}, meta


def _ref(tmp_path, n):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(n)]
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return ref, rows


def _anchors(client, rows, editors):
    for p in rows:
        for ed in editors:
            client(ed, ea.SYSTEM, at.anchor_prompt(p["text"]), ea.TEXT_SCHEMA)


def test_a_run_finds_the_scope_effect_and_no_other(tmp_path, analyzer, monkeypatch):
    monkeypatch.setattr(at, "N_MAIN", 3)
    monkeypatch.setattr(at, "N_DECOY", 1)
    ref, rows = _ref(tmp_path, 4)
    eds, js = ["e1", "e2"], ["j1", "j2"]
    seed = ea.Client(ref / "replies.jsonl", ask=FakeAsk(), count_cost=False)
    _anchors(seed, rows, eds)
    fake = FakeAsk()
    client = ea.Client(ref / "replies.jsonl", ask=fake, count_cost=False)
    assert at.run(ref, client, analyzer, eds, js, workers=2) == {"edits": True, "facts": True, "read": True}
    edits = [c for c in fake.calls if c[1] == ea.SYSTEM]
    assert len(edits) == (3 * 16 + 1 * 8) * 2
    assert len(fake.calls) == len(edits) + 3 * 16 * 2 * 2 + 3 * 16 * 2 * 2 * 2
    res = at.analyse(at.collect(ref, client, analyzer, eds, js), eds, js)
    eff = res["effects"]
    assert eff["change"]["S"][0] == -1.0 and eff["read"]["S"][0] == 0.5 and eff["utility"]["S"][0] == 1.5
    assert all(eff["change"][f][0] == 0 and eff["read"][f][0] == 0 for f in "HFPX")
    assert res["matters"]["change"]["S"] and not res["matters"]["change"]["H"]
    assert res["seed"] == "HSFPX" and res["stage_2"]   # S's utility effect is positive; the rest keep R0's level and not res["whole_text"]
    assert res["deference"]["index"][0] == 0.0 and res["main_set"] == 3 and res["decoy_set"] == 1
    text = at.render(res, {"edits": True, "facts": True, "read": True}, {"calls": client.calls, "new": 0})
    assert "| S: scope line | -1.000 [-1.000, -1.000] | yes |" in text and "| HsFPX (R0) |" in text
    again = FakeAsk()
    at.run(ref, ea.Client(ref / "replies.jsonl", ask=again, count_cost=False), analyzer, eds, js)
    assert again.calls == []


class FakeBackends:
    def __init__(self):
        self.loaded, self.asks = [], FakeAsk()

    def __call__(self, model, logs):
        self.loaded.append(model)
        outer = self

        class B:
            ask = outer.asks

            def stop(self):
                pass
        return B()


def _job_setup(tmp_path, analyzer, monkeypatch, with_anchors=True):
    job = _load("agent_text_job")
    monkeypatch.setattr(job.at, "N_MAIN", 2)
    monkeypatch.setattr(job.at, "N_DECOY", 1)
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(3)]
    seed = tmp_path / "seed.jsonl"
    seed.write_text("")
    if with_anchors:
        _anchors(ea.Client(seed, ask=FakeAsk(), count_cost=False), rows, job.at.EDITORS)

    def fetch(pointers, ref):
        ref.mkdir(parents=True, exist_ok=True)
        keep = rows if pointers.name == "a" else []
        (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in keep))
        (ref / "missing.json").write_text("[]")
    return job, seed, fetch, (tmp_path / "a", tmp_path / "b")


def test_the_job_checks_the_anchors_loads_each_model_once_and_reports(tmp_path, analyzer, monkeypatch):
    job, seed, fetch, ptrs = _job_setup(tmp_path, analyzer, monkeypatch)
    backends, uploads, asked = FakeBackends(), [], []
    ref = tmp_path / "ref"
    rc = job.main(["--run-id", "t-1", "--hours", "2", "--ref", str(ref), "--workers", "4"],
                  backends={"server": backends}, uploader=lambda r, i, t: uploads.append(i), fetch=fetch,
                  verify=lambda: 0, analyzer=analyzer, env={},
                  downloader=lambda f, t, d: asked.append(f) or seed, pointers=ptrs)
    assert rc == 0 and asked == ["edit-localize/main-1"]
    assert backends.loaded == job.at.EDITORS + job.at.JUDGES
    log = json.loads((ref / "run.json").read_text())
    assert log["anchors_in_cache"] == {"found": 4, "of": 4} and log["sets"] == {"main": 2, "decoy": 1}
    assert not any("prose checker" not in p for _m, s, p in backends.asks.calls if s == ea.SYSTEM)
    md = (ref / "agent-text.md").read_text()
    assert "| S: scope line |" in md and "no decision rule applies" not in md
    assert len(uploads) == 5


def test_the_job_stops_without_the_anchors_and_refuses_more_hours(tmp_path, analyzer, monkeypatch):
    import pytest
    job, seed, fetch, ptrs = _job_setup(tmp_path, analyzer, monkeypatch, with_anchors=False)
    backends = FakeBackends()
    ref = tmp_path / "ref"
    rc = job.main(["--run-id", "t", "--hours", "1", "--ref", str(ref), "--no-upload"], backends={"server": backends},
                  fetch=fetch, verify=lambda: 0, analyzer=analyzer, env={}, downloader=lambda f, t, d: seed,
                  pointers=ptrs)
    assert rc == 1 and backends.loaded == []
    with pytest.raises(SystemExit):
        job.main(["--run-id", "x", "--hours", "3", "--ref", str(tmp_path / "r2")])


def test_verify_checks_the_digest_of_0_4_0(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n")
    (tmp_path / "uv.lock").write_text("")
    assert at.verify(tmp_path) == 1
