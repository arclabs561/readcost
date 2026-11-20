"""The edit localization test's draw, arm E's feedback, run, statistics and job, with stubs for the models."""

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


el = _load("eval_edit_localize")
ea = el.ea

DENSE = ("The worker pool shard compaction retry budget is tuned by hand before each release. "
         "Operators set the cache eviction policy threshold value in the cluster config file. ")
LONG = ("When the service starts it reads every setting from the file that the operator wrote, checks "
        "each value against the schema, and refuses to start if any value is missing or out of range. ")
FILLER = ("The service writes a short log line for each request it handles. "
          "It keeps the last hour of logs on disk. ")
PARA = (DENSE + LONG + FILLER * 5).strip()


def test_e_points_at_as_many_sentences_as_b_longest_first_in_bs_form(analyzer):
    fb = el.e_feedback(analyzer, PARA)
    k = len(fb["b_spans"])
    assert k >= 2 and len(fb["e_spans"]) == k
    lines = fb["E"].splitlines()
    assert lines[0] == (f"readcost: {k} hard-to-read constructions in {ea.check(analyzer, PARA).words} words. "
                        "Rewrite these sentences where the finding holds; keep the meaning and the facts.")
    assert fb["B"].splitlines()[0].split(" in ")[1] == lines[0].split(" in ")[1]
    ns = [int(x.split("] ")[1].split()[0]) for x in lines[1:]]
    assert len(ns) == k and ns == sorted(ns, reverse=True)
    lengths = sorted((s["n"] for s in fb["sentences"]), reverse=True)
    assert ns == lengths[:k]
    assert all(x.endswith("Fix: Split it into shorter sentences, if the result reads naturally.") for x in lines[1:])
    longest = max(fb["sentences"], key=lambda s: s["n"])
    assert "refuses to start" in longest["text"] and tuple(longest["span"]) in fb["e_spans"]


def test_e_uses_bs_prompt_with_its_own_feedback(analyzer):
    fb = el.e_feedback(analyzer, PARA)
    b, e, c = (el.prompt(a, PARA, fb) for a in "BEC")
    assert b == ea.edit_prompt("B", PARA, fb["B"]) and c == ea.edit_prompt("C", PARA)
    assert e == b.replace(fb["B"], fb["E"]) and "[long-sentence]" in e


def test_scope_counts_unchanged_sentences_pointed_at_and_the_rest(analyzer):
    fb = el.e_feedback(analyzer, PARA)
    assert el.scope(fb, "C", PARA) == {"rest": 1.0}
    longest = max(fb["sentences"], key=lambda s: s["n"])
    edit = PARA.replace(longest["text"], "The service checks its settings when it starts.")
    got = el.scope(fb, "E", edit)
    assert got["pointed"] < 1.0 and got["rest"] == 1.0


def test_claims_follow_the_plan():
    assert el.claims((-0.08, -0.13, -0.03)) == {"findings keep facts better": True, "pointing keeps facts as well": False}
    assert el.claims((0.01, -0.04, 0.06)) == {"findings keep facts better": False, "pointing keeps facts as well": True}
    assert el.claims((-0.03, -0.07, -0.001)) == {"findings keep facts better": False, "pointing keeps facts as well": False}
    assert el.claims(None) == {"findings keep facts better": False, "pointing keeps facts as well": False}


def test_the_walk_goes_on_after_the_784th_and_drops_repositories_of_later_tests(analyzer):
    order = [f"o/r{i}" for i in range(el.OLD_WALKED)] + ["o/later", "o/new1", "o/none", "o/new2", "o/new3"]
    opened = []

    def files_for(repo):
        opened.append(repo)
        if repo == "o/none":
            return "no README"
        return "c" * 40, [("README.md", PARA.replace("release", repo))]
    picked, log = el.walk_on(order, files_for, analyzer, set(), "see o/later here", n=2, workers=2)
    assert [p["repo"] for p in picked] == ["o/new1", "o/new2"]
    assert [x["outcome"] for x in log] == ["named in a later evaluation", "drawn", "no README", "drawn"]
    assert "o/later" not in opened and not any(r.startswith("o/r") for r in opened)


class FakeAsk:
    """B edits start "Plainly"; E edits start "Kept"; C only tags. Judges pick "Plainly". Every judge
    lists a lost fact in E's edits, none elsewhere."""

    def __init__(self):
        self.calls = []

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        meta = {"requested": model, "served": model}
        if "text" in schema["properties"]:
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            if "[long-sentence]" in prompt:
                return {"text": f"Kept ({model}): {original}"}, meta
            if "prose checker" in prompt:
                return {"text": f"Plainly ({model}): {original}"}, meta
            return {"text": f"{original} ({model})"}, meta
        if "easier" in schema["properties"]:
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nGive your reason")[0]
            a, b = one.startswith("Plainly"), two.startswith("Plainly")
            return {"reason": "r", "easier": "tie" if a == b else "1" if a else "2"}, meta
        revision = prompt.split("Revision:\n", 1)[1]
        return {"lost": ["a fact"] if revision.startswith("Kept") else [], "added": [], "changed": []}, meta


def _rows(n_old, n_new):
    return ([{"id": f"o{i}", "text": PARA.replace("release", f"release o{i}"), "new": False} for i in range(n_old)]
            + [{"id": f"n{i}", "text": PARA.replace("release", f"release n{i}"), "new": True} for i in range(n_new)])


def _seed_old(path, analyzer, rows, editors, judges):
    """The edit test's B and C edits and fact checks of the old paragraphs, as main-1b left them."""
    client = ea.Client(path, ask=FakeAsk(), count_cost=False)
    for p in rows:
        if p["new"]:
            continue
        fb = el.e_feedback(analyzer, p["text"])
        for ed in editors:
            for arm in "BC":
                t = client(ed, ea.SYSTEM, el.prompt(arm, p["text"], fb), ea.TEXT_SCHEMA)["text"]
                for j in judges:
                    client(j, None, ea.fact_prompt(p["text"], t), ea.fact_schema())
    return client.calls


def test_a_run_asks_e_everywhere_and_b_and_c_only_on_new_paragraphs(tmp_path, analyzer):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = _rows(2, 1)
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    eds, js = ["e1", "e2"], ["j1", "j2", "j3"]
    seeded = _seed_old(ref / "replies.jsonl", analyzer, rows, eds, js)
    fake = FakeAsk()
    client = ea.Client(ref / "replies.jsonl", ask=fake, count_cost=False)
    assert el.run(ref, client, analyzer, eds, js, workers=2) == {"edits": True, "facts": True, "EB": True}
    edits = [c for c in fake.calls if c[1] == ea.SYSTEM]
    # E for 3 paragraphs x 2 editors; B and C for the new paragraph x 2 editors.
    assert len(edits) == 6 + 4
    facts = [c for c in fake.calls if "Revision:\n" in c[2]]
    assert len(facts) == (6 + 4) * 3
    assert len(fake.calls) == 10 + 30 + 3 * 2 * 3 * 2 and client.calls == seeded + len(fake.calls)
    res = el.analyse(el.collect(ref, client, analyzer, eds, js), analyzer, eds, js)
    assert res["B_minus_E"][0] == -1.0 and res["content"]["E"]["share"][0] == 1.0
    assert res["B_minus_C_new"] == (0.0, 0.0, 0.0) and res["E_minus_C"][0] == 1.0
    assert res["claims"] == {"findings keep facts better": True, "pointing keeps facts as well": False}
    assert res["EB"]["estimate"][0] == 0.0 and res["EB"]["counts"] == {"loss": 18}
    assert res["scope"]["C"]["rest"][0] == 1.0  # the tag follows the last sentence, which stays whole
    text = el.render(res, {"edits": True, "facts": True, "EB": True}, {"calls": client.calls, "new": 0, "cached": 0})
    assert "| **B minus E, all paragraphs (primary)** | -100.0 [-100.0, -100.0] |" in text
    assert "| readcost's findings keep facts better than pointing at the longest sentences | yes |" in text
    again = FakeAsk()
    el.run(ref, ea.Client(ref / "replies.jsonl", ask=again, count_cost=False), analyzer, eds, js)
    assert again.calls == []


def test_without_every_judges_fact_checks_no_claim_is_decided(tmp_path, analyzer):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = _rows(1, 1)
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    eds, js = ["e1"], ["j1", "j2", "j3"]
    _seed_old(ref / "replies.jsonl", analyzer, rows, eds, js)
    client = ea.Client(ref / "replies.jsonl", ask=FakeAsk(), count_cost=False)
    el.run(ref, client, analyzer, eds, js, workers=2, call_judges=["j1", "j2"])
    res = el.analyse(el.collect(ref, client, analyzer, eds, js), analyzer, eds, js, judges_done=["j1", "j2"])
    assert res["claims"] is None and res["B_minus_E"][0] == -1.0
    text = el.render(res, {}, {})
    assert "no claim is decided" in text and "| not decided |" in text


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


def test_the_job_starts_from_main_1b_loads_each_model_once_and_uploads(tmp_path, analyzer):
    job = _load("edit_localize_job")
    editors, judges = job.ea.open_models()
    rows = _rows(2, 2)
    seed = tmp_path / "seed.jsonl"
    seeded = _seed_old(seed, analyzer, rows, editors, judges)

    def fetch(pointers, ref):
        ref.mkdir(parents=True, exist_ok=True)
        keep = [r for r in rows if r["new"] == (pointers.name == "new")]
        (ref / "texts.jsonl").write_text("".join(json.dumps({k: v for k, v in r.items() if k != "new"}) + "\n"
                                                 for r in keep))
        (ref / "missing.json").write_text("[]")
    asked, uploads = [], []

    def downloader(folder, token, dest):
        asked.append(folder)
        return seed
    backends = FakeBackends()
    new = tmp_path / "new"
    new.mkdir()
    (new / "walk.jsonl").write_text('{"repo": "o/a", "outcome": "drawn"}\n')
    ref = tmp_path / "ref"
    rc = job.main(["--run-id", "t-1", "--hours", "2.5", "--ref", str(ref), "--old", str(tmp_path / "old"),
                   "--new", str(new), "--workers", "4"], backends={"server": backends},
                  uploader=lambda r, run_id, token: uploads.append(run_id), fetch=fetch, verify=lambda: 0,
                  analyzer=analyzer, env={}, downloader=downloader)
    assert rc == 0 and asked == ["edit-arms/main-1b"]
    assert backends.loaded == editors + judges
    log = json.loads((ref / "run.json").read_text())
    assert log["cache_at_start"] == seeded and log["started_from"][0]["replies"] == seeded
    assert log["old_edits_in_cache"] == {"found": 2 * 3 * 2, "of": 12}
    # No B or C edit of an old paragraph is asked again.
    old_texts = {r["text"] for r in rows if not r["new"]}
    asked_edits = [p for _m, s, p in backends.asks.calls if s == job.ea.SYSTEM]
    assert not any(p.rsplit("Paragraph:\n", 1)[1] in old_texts and "[long-sentence]" not in p for p in asked_edits)
    md = (ref / "edit-localize.md").read_text()
    assert "| readcost's findings keep facts better than pointing at the longest sentences | yes |" in md
    assert "Continued draw: walked 1 more repositories (drawn: 1)" in md
    assert len(uploads) == 7 and set(uploads) == {"t-1"}


def test_the_job_refuses_more_hours_than_the_plan(tmp_path):
    import pytest
    job = _load("edit_localize_job")
    with pytest.raises(SystemExit):
        job.main(["--run-id", "x", "--hours", "3", "--ref", str(tmp_path / "r")])


def test_the_job_stops_before_loading_a_model_if_main_1b_does_not_match(tmp_path, analyzer):
    job = _load("edit_localize_job")
    rows = _rows(2, 1)
    seed = tmp_path / "seed.jsonl"
    seed.write_text("")

    def fetch(pointers, ref):
        ref.mkdir(parents=True, exist_ok=True)
        keep = [r for r in rows if r["new"] == (pointers.name == "new")]
        (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in keep))
        (ref / "missing.json").write_text("[]")
    backends = FakeBackends()
    ref = tmp_path / "ref"
    rc = job.main(["--run-id", "t", "--hours", "1", "--ref", str(ref), "--old", str(tmp_path / "old"),
                   "--new", str(tmp_path / "new"), "--no-upload"], backends={"server": backends}, fetch=fetch,
                  verify=lambda: 0, analyzer=analyzer, env={}, downloader=lambda f, t, d: seed)
    assert rc == 1 and backends.loaded == []
    assert "of the edit test's B and C edits are in the cache" in json.loads((ref / "run.json").read_text())["stopped"]
