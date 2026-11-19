"""The edit-arms evaluation's draw, prompts, judging and statistics, with a stub in place of the models."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Made-up documentation prose. DENSE has findings (noun stacks); PLAIN says the same more simply.
DENSE = ("The worker pool shard compaction retry budget is tuned by hand before each release. "
         "Operators set the cache eviction policy threshold value in the cluster config file. ")
FILLER = ("The service reads its settings when it starts and writes a short log line for each request it "
          "handles. It keeps the last hour of logs on disk and removes older files once a day. ")
PARA = (DENSE + FILLER * 6).strip()   # about 150 words, two or more findings
PLAIN = "We tune how often a shard retries compaction by hand before each release. " + FILLER * 6


def _script():
    spec = importlib.util.spec_from_file_location("eval_edit_arms", ROOT / "scripts" / "eval_edit_arms.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _script()


def test_the_made_up_paragraph_is_eligible(analyzer):
    assert 120 <= len(PARA.split()) <= 260
    assert len(analyzer.check_text(PARA, "markdown").findings) >= 2


def test_blocks_skip_fences_comments_and_give_offsets_into_the_file():
    text = ("# Title\n\nFirst para line one\nline two\n\n```\ninside code\n\nstill code\n```\n"
            "<!-- a comment\nspanning lines -->\nAfter the comment\r\n\n~~~py\nx\n~~~\nLast")
    got = [text[s:e] for s, e in m.blocks(text)]
    assert got == ["# Title", "First para line one\nline two", "After the comment", "Last"]


def test_shape_rules_drop_headings_lists_tables_quotes_and_indented_code():
    long = " ".join(["word"] * 130)
    assert m.shape_ok(long)
    for start in ("# ", "> ", "| ", "- ", "* ", "+ ", "<p>", "![x](y) ", "[x](y) ", "1. ", "2) ", "=== "):
        assert not m.shape_ok(start + long), start
    assert not m.shape_ok(long + "\n    indented code")
    assert not m.shape_ok(long + "\n| a | b |")
    assert not m.shape_ok(" ".join(["word"] * 119))
    assert not m.shape_ok(" ".join(["word"] * 261))


def test_eligible_needs_two_findings_and_english(analyzer):
    text = f"# Demo\n\n{PARA}\n\n{FILLER * 6}\n"
    (got,) = m.eligible(text, "README.md", analyzer)
    assert text[got["start"]:got["end"]] == PARA
    assert got["sha256"] == m.sha(PARA) and got["findings"] >= 2
    german = " ".join(["Die Datei wird beim Start gelesen und der Dienst schreibt eine Zeile."] * 12)
    assert m.eligible(german, "README.md", analyzer) == []


def test_doc_paths_follow_the_prereg_and_are_seeded():
    paths = ["docs/guide.md", "docs/README.md", "doc/x.markdown", "src/design/y.mdx", "rfcs/0001.md",
             "notes/z.md", "docs/CHANGELOG.md", "docs/img.png", "pkg/adr/0002.md", "Docs/Upper.md"]
    a = m.doc_paths(paths, "o/r")
    assert a == m.doc_paths(list(reversed(paths)), "o/r")
    assert len(a) == 2
    allowed = {"docs/guide.md", "doc/x.markdown", "src/design/y.mdx", "rfcs/0001.md", "pkg/adr/0002.md",
               "Docs/Upper.md"}
    assert set(a) <= allowed
    assert m.doc_paths(["docs/only.md"], "o/r") == ["docs/only.md"]


def test_exclusions_match_whole_repository_names():
    corpus = "see https://github.com/acme/tool and acme/tools-extra"
    assert m.named_in("acme/tool", corpus)
    assert not m.named_in("acme/too", corpus)
    assert not m.named_in("cme/tool", corpus)
    assert m.drop_reason({"full_name": "arclabs561/x"}, "", "") == "named in an evaluation corpus"
    assert m.drop_reason({"full_name": "a/b"}, "", '{"repo": "a/b"}') == "in the held-out precision candidates"
    assert m.drop_reason({"full_name": "a/b", "fork": True}, "", "") == "fork or archived"
    assert m.drop_reason({"full_name": "a/b"}, "", "") is None


def test_walk_takes_one_paragraph_per_repository_drops_repeats_and_stops(analyzer):
    other = PARA.replace("before each release", "before every release")
    files = {"o/a": ("c1", [("README.md", f"{PARA}\n\n{other}\n")]),
             "o/b": ("c2", [("README.md", f"{PARA}\n")]),          # same text as one in o/a, maybe
             "o/c": "no README",
             "o/d": ("c4", [("README.md", "short\n")]),
             "o/e": ("c5", [("docs/x.md", f"{other}\n\n{PARA}\n")])}
    repos = [{"full_name": r} for r in files]
    picked, log = m.walk(repos, files.get, analyzer, n=2)
    assert len(picked) <= 2 and len({p["repo"] for p in picked}) == len(picked)
    assert len({p["sha256"] for p in picked}) == len(picked)
    again, log2 = m.walk(list(reversed(repos)), files.get, analyzer, n=2)
    assert again == picked and log2 == log   # the order comes from the seed, not the input
    outcomes = {x["repo"]: x["outcome"] for x in log}
    assert outcomes.get("o/c", "no README") == "no README"
    assert outcomes.get("o/d", "no eligible paragraph") == "no eligible paragraph"
    for p in picked:
        commit, fs = files[p["repo"]]
        assert p["commit"] == commit
        text = dict(fs)[p["path"]]
        assert m.sha(text[p["start"]:p["end"]]) == p["sha256"]


def test_fetch_cuts_at_the_pointers_and_leaves_out_changed_files(tmp_path):
    good = f"intro\n\n{PARA}\n"
    start = good.index(PARA)
    pts = [{"id": "p1", "repo": "o/a", "commit": "c", "path": "README.md", "start": start,
            "end": start + len(PARA), "sha256": m.sha(PARA)},
           {"id": "p2", "repo": "o/b", "commit": "c", "path": "README.md", "start": 0, "end": 5,
            "sha256": m.sha("other")}]
    (tmp_path / "paragraphs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pts))

    def get(repo, commit, path):
        if repo == "o/b":
            return "changed text"
        return good
    out = m.fetch(tmp_path, tmp_path / "ref", get=get)
    assert [p["id"] for p in out] == ["p1"] and out[0]["text"] == PARA
    assert json.loads((tmp_path / "ref" / "missing.json").read_text()) == [{"id": "p2", "why": "SHA-256 differs"}]


def test_arm_prompts_differ_only_by_the_feedback_block(analyzer):
    fb = m.feedback(analyzer, PARA)
    assert fb.startswith("readcost:") and "Wrong finding" not in fb
    b, c = m.edit_prompt("B", PARA, fb), m.edit_prompt("C", PARA, fb)
    block = "A prose checker reported this about the paragraph:\n" + fb + "\n\n"
    assert b.replace(block, "") == c
    assert f"at most {m.budget(PARA)} words" in c and m.budget(PARA) == -(-len(PARA.split()) * 12 // 10)
    assert c.endswith(PARA) and b.endswith(PARA)


def test_judge_calls_cover_both_orders_and_are_shuffled_by_seed():
    units = [("p1", "e1"), ("p2", "e1")]
    calls = m.judge_calls(units, [("B", "C")], ["j1", "j2"], "s")
    assert len(calls) == 2 * 2 * 2
    assert calls == m.judge_calls(units, [("B", "C")], ["j1", "j2"], "s")
    assert calls != sorted(calls, key=lambda c: (c["id"], c["judge"], c["order"]))
    by = {(c["id"], c["judge"], c["order"]): c for c in calls}
    assert m.shown(by[("p1", "j1", 0)]) == ("B", "C") and m.shown(by[("p1", "j1", 1)]) == ("C", "B")
    prompt = m.pair_prompt("TEXT ONE", "TEXT TWO")
    assert prompt.index("TEXT ONE") < prompt.index("TEXT TWO")
    assert "checker" not in prompt and "original" not in prompt and "edit" not in prompt.lower()


def test_parse_and_map_a_judge_reply_to_an_arm():
    c0 = {"pair": "BC", "order": 0}
    c1 = {"pair": "BC", "order": 1}
    assert m.chosen_arm(c0, m.parse_easier({"easier": "1"})) == "B"
    assert m.chosen_arm(c1, m.parse_easier({"easier": "1"})) == "C"
    assert m.chosen_arm(c1, m.parse_easier({"easier": "Version 2"})) == "B"
    assert m.parse_easier({"easier": "tie"}) == "tie" and m.parse_easier({"easier": "Neither"}) == "tie"
    assert m.parse_easier({"easier": "both"}) is None and m.parse_easier(None) is None
    assert m.chosen_arm(c0, None) is None


def test_outcomes_count_only_order_consistent_wins():
    assert m.outcome("B", "B", "B", "C") == "win"
    assert m.outcome("C", "C", "B", "C") == "loss"
    assert m.outcome("B", "C", "B", "C") == "split"
    assert m.outcome("B", "tie", "B", "C") == "tie"
    assert m.outcome("tie", "tie", "B", "C") == "tie"
    assert m.outcome(None, "B", "B", "C") is None
    scores = m.unit_scores({("p", "e", "j1"): "win", ("p", "e", "j2"): "split", ("p", "e", "j3"): None})
    assert scores == {("p", "e"): 0.75}


def test_bootstrap_resamples_paragraphs_and_labels_follow_the_prereg():
    est = m.cluster_boot({("p1", "e1"): 1.0, ("p1", "e2"): 1.0, ("p2", "e1"): 1.0}, n=200)
    assert est == (1.0, 1.0, 1.0)
    vals = {(f"p{i}", e): float(i % 2) for i in range(40) for e in ("e1", "e2")}
    mean, lo, hi = m.cluster_boot(vals, n=2000)
    assert mean == 0.5 and lo < 0.5 < hi
    assert m.cluster_boot({}) is None
    assert m.label((0.60, 0.52, 0.68)) == "better"
    assert m.label((0.54, 0.51, 0.57)) == "inconclusive"     # above 0.5, below the smallest that counts
    assert m.label((0.50, 0.45, 0.549)) == "no meaningful advantage"
    assert m.label(None) == "not run"
    c = m.claims((0.6, 0.52, 0.68), None, None, (0.05, -0.02, 0.12), None, None)
    assert not c["readcost feedback beats a generic instruction"]   # the content bound fails
    c = m.claims((0.6, 0.52, 0.68), None, None, (0.0, -0.05, 0.05), None, None)
    assert c["readcost feedback beats a generic instruction"]
    assert m.changes_content([{"lost": ["x"], "changed": []}, {"lost": [], "changed": ["y"]}, None])
    assert not m.changes_content([{"lost": ["x"], "changed": []}, {"lost": [], "changed": [], "added": ["z"]}])


class FakeAsk:
    """Edits: B marks the text "Plainly", C only tags it. Judges pick the "Plainly" version, else tie.

    Every edit differs by paragraph and editor, so no two judge prompts are the same (the cache would
    answer a repeated prompt without a call).
    """

    def __init__(self, cost=0.01):
        self.calls, self.cost = [], cost

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        meta = {"requested": model, "served": model + "-x", "cost": self.cost}
        if "text" in schema["properties"]:
            assert system == m.SYSTEM
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            text = f"Plainly ({model}): {original}" if "prose checker" in prompt else f"{original} ({model})"
            return {"text": text}, meta
        if "easier" in schema["properties"]:
            assert system is None
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nGive your reason")[0]
            pick = "1" if one.startswith("Plainly") else "2" if two.startswith("Plainly") else "tie"
            return {"reason": "r", "easier": pick}, meta
        return {"lost": [], "added": [], "changed": []}, meta


def _ref(tmp_path, n=3):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(n)]
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return ref


def test_a_run_judges_every_pair_in_both_orders_and_the_report_decides(tmp_path, analyzer):
    ref = _ref(tmp_path)
    fake = FakeAsk()
    client = m.Client(ref / "replies.jsonl", ask=fake)
    status = m.run(ref, client, analyzer, editors=["e1", "e2"], judges=["j1", "j2"], workers=2)
    assert status == {"edits": True, "BC": True, "facts": True, "BA": True, "CA": True}
    # 3 paragraphs x 2 editors: 12 edits, 3 pairs x 2 orders x 2 judges x 6 units, 2 x 2 x 6 fact checks
    assert len(fake.calls) == 12 + 72 + 24 == client.calls
    res = m.analyse(m.collect(ref, client, analyzer, ["e1", "e2"], ["j1", "j2"]), analyzer,
                    ["e1", "e2"], ["j1", "j2"])
    assert res["pairs"]["BC"]["estimate"][0] == 1.0 and res["pairs"]["BC"]["label"] == "better"
    assert res["pairs"]["CA"]["counts"] == {"tie": 12}     # neither starts with "Plainly"
    assert res["claims"]["readcost feedback beats a generic instruction"]
    assert not res["claims"]["readcost adds nothing over a generic instruction"]
    text = m.render(res, status, client)
    assert "| B against C | 1.000 [1.000, 1.000] | better |" in text
    pointers = tmp_path / "pointers"
    pointers.mkdir()
    (pointers / "walk.jsonl").write_text('{"repo": "o/a", "outcome": "drawn"}\n{"repo": "o/b", "outcome": "no README"}\n')
    full = m.report(ref, tmp_path / "r.json", client=client, analyzer=analyzer, pointers=pointers,
                    editors=["e1", "e2"], judges=["j1", "j2"])
    assert "| readcost feedback beats a generic instruction | yes |" in full
    assert "walked 2 (drawn: 1, no README: 1); paragraphs fetched 3." in full
    assert json.loads((tmp_path / "r.json").read_text())["pairs"]["BC"]["label"] == "better"
    # A second run on the same cache asks nothing new.
    again = FakeAsk()
    client2 = m.Client(ref / "replies.jsonl", ask=again)
    m.run(ref, client2, analyzer, editors=["e1", "e2"], judges=["j1", "j2"])
    assert again.calls == [] and client2.calls == 108


def test_caps_stop_the_run_before_crossing_and_count_cached_replies(tmp_path, analyzer):
    ref = _ref(tmp_path, n=2)
    fake = FakeAsk(cost=0.5)
    client = m.Client(ref / "replies.jsonl", ask=fake, cost_cap=3.0)
    status = m.run(ref, client, analyzer, editors=["e1"], judges=["j1"], workers=1)
    assert status == {"edits": True, "BC": False}
    # 4 edits and 2 judgements reach $3.00; the next call, with its $0.10 reserve, would cross the cap.
    assert client.spent == pytest.approx(3.0) and len(fake.calls) == 6
    # The cap holds across runs: a new client reads what was spent.
    later = m.Client(ref / "replies.jsonl", ask=FakeAsk(), cost_cap=3.0)
    assert later.spent == pytest.approx(3.0) and later.calls == 6
    with pytest.raises(m.CapReached):
        m.Client(ref / "replies.jsonl", ask=FakeAsk(), call_cap=5)("j1", None, "new prompt", m.PAIRWISE_SCHEMA)


def test_a_failed_reply_is_asked_again_and_reported_missing_if_it_fails_twice(tmp_path, analyzer):
    ref = _ref(tmp_path, n=1)
    inner = FakeAsk()

    def flaky(model, prompt, schema, system=None):
        if model == "bad":
            inner.calls.append((model, system, prompt))
            return None, {"requested": model, "error": "HTTP 500"}
        return inner(model, prompt, schema, system=system)
    client = m.Client(ref / "replies.jsonl", ask=flaky)
    m.run(ref, client, analyzer, editors=["e1", "bad"], judges=["j1"], workers=1)
    assert sum(c[0] == "bad" for c in inner.calls) == 4    # two arms, asked twice each
    res = m.analyse(m.collect(ref, client, analyzer, ["e1", "bad"], ["j1"]), analyzer, ["e1", "bad"], ["j1"])
    assert res["missing_edits"] == 2
    assert res["pairs"]["BC"]["missing"] == 1               # the "bad" unit, for its one judge


def test_verify_compares_src_with_the_pinned_commit(monkeypatch):
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = args

        class R:
            returncode = 0
        return R()
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    assert m.verify() == 0
    assert seen["args"] == ["git", "diff", "--quiet", "a57e19e", "--", "src", "uv.lock"]


def test_readme_choice_follows_github_and_files_come_at_the_commit():
    assert m.pick_readme({"README.md": 1, "readme.txt": 1, "docs/README.md": 1}) == "README.md"
    assert m.pick_readme({"Readme.rst": 1, "README": 1}) == "Readme.rst"
    assert m.pick_readme({"src/README.md": 1, ".github/README.md": 1, "docs/readme.md": 1}) == ".github/README.md"
    assert m.pick_readme({"src/README.md": 1}) is None
    sizes = {"README.md": 10, "docs/guide.md": 20, "docs/huge.md": 2_000_000}
    fetched = []

    def get(repo, commit, path):
        fetched.append((repo, commit, path))
        return f"text of {path}"
    commit, files = m.github_files("o/r", get_tree=lambda repo: ("abc", sizes), get=get)
    assert commit == "abc" and files[0] == ("README.md", "text of README.md")
    assert {p for p, _ in files} <= {"README.md", "docs/guide.md"}
    assert all(c == "abc" for _r, c, _p in fetched)
    assert m.github_files("o/r", get_tree=lambda repo: None) == "repository unavailable"
    assert m.github_files("o/r", get_tree=lambda repo: ("abc", {"src/x.md": 1})) == "no README"
    assert m.github_files("o/r", get_tree=lambda repo: ("abc", {"README.md": 2_000_000})) == "README over 1 MB"
