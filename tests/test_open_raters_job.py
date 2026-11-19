"""The open-raters job on made-up items, with the model call mocked."""

import gzip
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("open_raters_job", SCRIPTS / "open_raters_job.py")
job = importlib.util.module_from_spec(spec)
sys.modules["open_raters_job"] = job  # dataclasses look the module up
spec.loader.exec_module(job)


def row(i, rule="stacked-nouns", primed=True, kind="Markdown documentation"):
    return {"i": i, "kind": kind, "rule": rule if primed else None, "message": "3 nouns stacked: 'a b c'" if primed
            else None, "primed_excerpt": "a b c" if primed else None, "sentence": f"Sentence {i} has a b c.",
            "before": "Before.", "after": "After.", "in_primed": primed, "blind_excerpt": f"Sentence {i} has a b c."
            if not primed else "a b c", "in_blind": True}


def make_store(tmp_path: Path) -> Path:
    rounds = {1: [row(101) | {"kind": None}, row(102) | {"kind": None}],
              2: [row(201), row(202, rule="inline-list")],
              3: [row(301), row(302, primed=False)]}
    for rnd, rows in rounds.items():
        with gzip.open(tmp_path / f"round{rnd}.jsonl.gz", "wt", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        (tmp_path / f"round{rnd}-RUBRIC.txt").write_text(f"primed rubric {rnd}\n")
        (tmp_path / f"round{rnd}-RUBRIC_BLIND.txt").write_text(f"blind rubric {rnd}\n")
    return tmp_path


def good_reply(req):
    entry = {"i": req.item, "label": "d", "cause": "made up"}
    if req.proto == "primed":
        entry = {"i": req.item, "label": "d", "present": True, "cause": "made up"}
    return job.Reply(json.dumps({"labels": [entry]}), "stop", 100, 80, 20)


def test_item_view_has_the_batch_fields_and_unprimed_has_no_rule():
    r = row(5)
    assert list(job.item_view(r, 1, "primed")) == ["i", "rule", "message", "excerpt", "sentence", "before", "after"]
    assert list(job.item_view(r, 2, "primed"))[:2] == ["i", "kind"]
    blind = job.item_view(r | {"blind_excerpt": "other words"}, 3, "unprimed")
    assert "rule" not in blind and "message" not in blind
    assert blind["excerpt"] == "other words" and blind["kind"] == "Markdown documentation"
    assert list(job.item_view(r, 1, "unprimed")) == ["i", "excerpt", "sentence", "before", "after"]


def test_messages_put_the_rubric_verbatim_and_a_batch_of_one():
    m = job.messages("RUBRIC TEXT\n", {"i": 7, "excerpt": "é"})
    assert m[0] == {"role": "system", "content": "RUBRIC TEXT\n"}
    assert json.loads(m[1]["content"]) == [{"i": 7, "excerpt": "é"}]
    assert "é" in m[1]["content"]  # ensure_ascii=False, as the batch files were written


def test_schema_fixes_the_id_and_the_fields():
    s = job.reply_schema(42, "primed")
    entry = s["properties"]["labels"]["items"]
    assert entry["properties"]["i"]["enum"] == [42]
    assert entry["required"] == ["i", "label", "present", "cause"]
    assert s["properties"]["labels"]["maxItems"] == 1
    assert "present" not in job.reply_schema(42, "unprimed")["properties"]["labels"]["items"]["properties"]


def test_parse_reply_accepts_only_the_rubric_format():
    ok = json.dumps({"labels": [{"i": 3, "label": "c", "present": False, "cause": "x"}]})
    assert job.parse_reply(ok, 3, "primed") == {"id": 3, "label": "c", "construction_present": False, "cause": "x"}
    assert job.parse_reply(ok, 4, "primed") is None  # wrong id
    assert job.parse_reply("{not json", 3, "primed") is None
    assert job.parse_reply(json.dumps({"labels": []}), 3, "primed") is None
    assert job.parse_reply(json.dumps({"labels": [{"i": 3, "label": "x", "cause": ""}]}), 3, "unprimed") is None
    assert job.parse_reply(json.dumps({"labels": [{"i": 3, "label": "w", "cause": ""}]}), 3, "unprimed") == \
        {"id": 3, "label": "w", "cause": ""}
    assert job.parse_reply(json.dumps({"labels": [{"i": 3, "label": "w", "cause": ""}]}), 3, "primed") is None


def test_requests_cover_every_item_and_sample_in_prefix_order(tmp_path):
    store = make_store(tmp_path)
    items, rubrics = job.read_items(store), job.read_rubrics(store, root=tmp_path)
    reqs = job.build_requests(items, rubrics)
    # primed: 2 + 2 + 1 items; unprimed: 2 + 2 + 2 items; four samples each
    assert len(reqs) == (5 + 6) * 4
    assert [r.key() for r in reqs] == sorted((r.key() for r in reqs),
                                            key=lambda k: (k[0], job.PROTOCOLS.index(k[1]), k[2],
                                                           [s[0] for s in job.SAMPLES].index(k[3])))
    assert not any(r.item == 302 and r.proto == "primed" for r in reqs)  # a ranked sentence is unprimed only
    first = reqs[0]
    assert first.messages[0]["content"] == "primed rubric 1\n"
    assert {(r.sample, r.temperature, r.seed) for r in reqs if r.item == 101 and r.proto == "primed"} == \
        {("s1", 0.7, 1), ("s2", 0.7, 2), ("s3", 0.7, 3), ("greedy", 0.0, None)}


def test_pilot_order_is_fixed(tmp_path):
    items = job.read_items(make_store(tmp_path))
    a, b = job.pilot_keys(items, 3), job.pilot_keys(items, 3)
    assert a == b and len(a) == 3
    assert job.pilot_keys(items, 100) == {(rnd, r["i"]) for rnd, rows in items.items() for r in rows}


def test_run_retries_once_with_a_new_seed_and_writes_label_files(tmp_path):
    store = make_store(tmp_path)
    items, rubrics = job.read_items(store), job.read_rubrics(store, root=tmp_path)
    reqs = job.build_requests(items, rubrics)
    calls = []

    def fake(batch):
        calls.append([(r.key(), r.seed, r.attempt) for r in batch])
        out = []
        for r in batch:
            if r.item == 201 and r.sample == "s1":       # bad on the first try, good on the retry
                out.append(good_reply(r) if r.attempt == 2 else job.Reply("oops", "stop", 100, 0, 3))
            elif r.item == 202 and r.sample == "s2":     # cut off both times
                out.append(job.Reply('{"labels": [{"i"', "length", 100, 0, 160))
            else:
                out.append(good_reply(r))
        return out

    res = job.run_requests("qwen", reqs, fake)
    assert len(calls) == 2
    retried = {k: (seed, attempt) for k, seed, attempt in calls[1]}
    assert retried[(2, "primed", 201, "s1")] == (1 + job.RETRY_SEED_OFFSET, 2)
    assert res.failures == Counter({(2, "primed"): 1, (2, "unprimed"): 1})
    assert res.retried == 4  # 201 s1 and 202 s2, primed and unprimed
    assert res.tokens["requests"] == len(reqs) + 4

    out = tmp_path / "run"
    job.write_outputs(out, res, reqs)
    lab = json.loads((out / "eval/breadth/labels/open-qwen-primed-s2.json").read_text())
    assert [x["id"] for x in lab] == [201]  # 202 failed twice: no label
    assert lab[0] == {"id": 201, "label": "d", "construction_present": True, "cause": "made up"}
    blind = json.loads((out / "eval/kinds/labels/open-qwen-unprimed-greedy.json").read_text())
    assert {x["id"] for x in blind} == {301, 302} and "construction_present" not in blind[0]
    raw = [json.loads(x) for x in (out / "eval/breadth/raw/open-qwen-primed-s1.jsonl").read_text().splitlines()]
    assert {(x["id"], x["attempt"], x["parsed"]) for x in raw} == {(201, 2, True), (202, 1, True)}

    log = job.model_log(res, job.MODELS["qwen"], {"revision_resolved": "abc"}, 60.0)
    rates = job.parse_rates(log, Counter((r.rnd, r.proto) for r in reqs))
    assert rates["round2 primed"] == 7 / 8 and rates["round1 primed"] == 1.0


def test_rubric_falls_back_to_the_checkout(tmp_path):
    (tmp_path / "store").mkdir()
    store = make_store(tmp_path / "store")
    (store / "round2-RUBRIC.txt").unlink()
    (tmp_path / "eval/breadth").mkdir(parents=True)
    (tmp_path / "eval/breadth/RUBRIC.txt").write_text("from the checkout\n")
    assert job.read_rubrics(store, root=tmp_path)[(2, "primed")] == "from the checkout\n"


def test_projected_cost():
    logs = [{"load_seconds": 360.0, "requests_per_second": 23164 / 600}] * 4  # 6 min load, 10 min generation
    assert abs(job.projected_cost(logs) - 4 * (16 / 60) * 5.0 * 1.25) < 1e-9
    assert job.projected_cost([{"load_seconds": 1, "requests_per_second": None}]) is None


def test_items_digest_ignores_gzip_headers(tmp_path):
    rows = [row(1), row(2)]
    assert job.items_digest(rows) == job.items_digest([dict(r) for r in rows])
    assert job.items_digest(rows) != job.items_digest(rows[:1])


def test_models_are_pinned_and_panel_has_four_families():
    assert len(job.PANEL) == 4 and "olmo" not in job.PANEL
    for key, m in job.MODELS.items():
        assert len(m["revision"]) == 40, key
        assert "anthropic" not in m["repo"].lower()


def test_main_stops_without_rubrics(tmp_path, capsys, monkeypatch):
    store = make_store(tmp_path)
    (store / "round2-RUBRIC_BLIND.txt").unlink()
    monkeypatch.setattr(job, "ROOT", tmp_path)  # so no rubric is found in the checkout either
    assert job.main(["--items", str(store), "--out", str(tmp_path / "out"), "--run-id", "t"]) == 2
    assert "round2 unprimed" in capsys.readouterr().err
