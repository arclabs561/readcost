"""Stage 2's search: the candidate texts, the plan of prompts, the run, the choice and the job, with stub models."""

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


at = _load("eval_agent_text")
ea = at.ea

DENSE = ("The worker pool shard compaction retry budget is tuned by hand before each release. "
         "Operators set the cache eviction policy threshold value in the cluster config file. ")
PARA = DENSE + " ".join(f"The service writes a short {n} log line for each request it handles. "
                        f"It keeps the last {n} hours of logs on disk." for n in ("two", "three", "four"))
MARK = "the threshold at which the cache evicts"   # only in stacked-nouns v1


def test_the_seed_is_the_factorials_hsfpx_and_a_candidate_changes_only_its_rule(analyzer):
    result = ea.check(analyzer, PARA)
    seed = at.candidate_text(result, "seed", "v0")
    assert seed == at.feedback(result, {"H": 1, "S": -1, "F": 1, "P": -1, "X": 1})   # HsFpX, not an arm of the fraction
    v1 = at.candidate_text(result, "stacked-nouns", "v1")
    changed = [(a, b) for a, b in zip(seed.splitlines(), v1.splitlines()) if a != b]
    assert changed and all("[stacked-nouns]" in a and MARK in b for a, b in changed)
    scoped = at.candidate_text(result, "scope", "v2")
    assert scoped.splitlines()[0] == seed.splitlines()[0] + at.SCOPE_CANDIDATES[2]
    assert at.fix_for("inline-list", "We split it because it is long.", "Use a list.").startswith("Use a list. Split")


def test_the_plan_judges_a_rules_candidates_only_where_the_rule_appears(tmp_path, analyzer):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = [{"id": "a", "text": PARA}, {"id": "b", "text": "Short text with no findings at all here today."}]
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    pl = at.search_plan(analyzer, ref)
    assert {k[0] for k in pl["prompts"]} == {"a"}
    assert pl["units"]["scope"] == {"a"} and "long-dependency" not in pl["units"]
    assert ("a", "stacked-nouns", "v3") in pl["prompts"] and ("a", "seed", "v0") in pl["prompts"]


class FakeAsk:
    """Edits made with MARK in the prompt start "Good" and win against C with no lost fact; others tie and lose one."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        if "text" in schema["properties"]:
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            if "prose checker" not in prompt:
                return {"text": f"{original} ({model})"}, {}
            tag = "Good" if MARK in prompt else "Plain"
            return {"text": f"{tag} [{ea.sha(prompt)[:8]}] ({model}): {original}"}, {}
        if "easier" in schema["properties"]:
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nGive your reason")[0]
            a, b = one.startswith("Good"), two.startswith("Good")
            return {"reason": "r", "easier": "tie" if a == b else "1" if a else "2"}, {}
        revision = prompt.split("Revision:\n", 1)[1]
        return {"lost": [] if revision.startswith("Good") else ["x"], "added": [], "changed": []}, {}


def _setup(tmp_path, editors):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(3)]
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    seed = ea.Client(ref / "replies.jsonl", ask=FakeAsk(), count_cost=False)
    for p in rows:
        for ed in editors:
            seed(ed, ea.SYSTEM, at.anchor_prompt(p["text"]), ea.TEXT_SCHEMA)
    return ref, rows


def test_the_search_picks_the_candidate_that_helps_and_keeps_the_seed_elsewhere(tmp_path, analyzer):
    eds, js = ["e1", "e2"], ["j1", "j2"]
    ref, _rows = _setup(tmp_path, eds)
    client = ea.Client(ref / "replies.jsonl", ask=FakeAsk(), count_cost=False)
    assert at.run_search(ref, client, analyzer, eds, js, workers=2) == {"edits": True, "facts": True, "read": True}
    pl = at.search_plan(analyzer, ref)
    res = at.analyse_search(pl, client, eds, js)
    assert res["choice"]["stacked-nouns"] == "v1"
    assert all(c == "v0" for sp, c in res["choice"].items() if sp != "stacked-nouns")
    sn = res["species"]["stacked-nouns"]
    assert sn["v1"]["utility"][0] == 1.0 and sn["v0"]["utility"][0] == -0.5 and sn["v1"]["gain_over_seed"] == 1.5
    rs = at.r_star(res["choice"])
    assert MARK in rs["fixes"]["stacked-nouns"] and rs["scope"] == "" and rs["precision"] is False
    md = at.render_search(res, {"edits": True}, {"calls": client.calls, "new": 0})
    assert "| stacked-nouns | v1 |" in md and MARK in md


def test_the_search_job_starts_from_the_factorial_and_writes_r_star(tmp_path, analyzer):
    job = _load("agent_text_search_job")
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(2)]
    seedf = tmp_path / "seed.jsonl"
    seedf.write_text("")
    c = ea.Client(seedf, ask=FakeAsk(), count_cost=False)
    for p in rows:
        for ed in job.at.EDITORS:
            c(ed, ea.SYSTEM, at.anchor_prompt(p["text"]), ea.TEXT_SCHEMA)

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
    rc = job.main(["--run-id", "s-1", "--hours", "1.75", "--ref", str(ref), "--no-upload", "--workers", "4"],
                  backends={"server": backend}, fetch=fetch, verify=lambda: 0, analyzer=analyzer, env={},
                  downloader=lambda f, t, d: asked.append(f) or seedf, pointers=(tmp_path / "a", tmp_path / "b"))
    assert rc == 0 and asked == ["agent-text/main-1"] and loaded == job.at.EDITORS + job.at.JUDGES
    out = json.loads((ref / "search.json").read_text())
    assert out["complete"] and MARK in out["r_star"]["fixes"]["stacked-nouns"]
    assert json.loads((ref / "run.json").read_text())["anchors_in_cache"] == {"found": 4, "of": 4}
