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


def _finding(feature, line, message, suggestion, path="p.md"):
    from readcost.features import Finding
    return Finding(feature=feature, severity="warn", message=message, excerpt="x", sentence="x", path=path,
                   line=line, suggestion=suggestion)


def test_questions_reproduce_the_wording_of_pull_request_102():
    from readcost.engine import Result
    prec = m.heldout_precision()
    assert prec["raters"] == 12 and prec["rules"]["stacked-nouns"] == {"labelled": 100, "correct": 0, "accepted": 36}
    r = Result(path="p.md", words=150, findings=[
        _finding("stacked-nouns", 3, "3 nouns stacked: 'cache eviction policy'", "Keep at most two nouns together."),
        _finding("long-dependency", 1, "subject and verb 14 words apart", "Move the verb nearer its subject."),
        _finding("made-up-rule", 5, "something", "Do it."),
    ])
    # As src/readcost/report.py's agent() prints it on feat/agent-questions at 6769c81, given this Result.
    assert m.questions([r], prec) == (
        "readcost: 3 sentences in 150 words that may be hard to follow. These are questions, not errors: in a "
        "held-out test, model raters said an editor would fix few such findings. Change a sentence only if it "
        "reads badly to you, keep its meaning and facts, and leave the rest.\n"
        "- line 1 [long-dependency] subject and verb 14 words apart. Is it hard to follow here? Raters said an "
        "editor would fix 5 of 91 such findings, and called 23 more optional. If it is, move the verb nearer its "
        "subject.\n"
        "- line 3 [stacked-nouns] 3 nouns stacked: 'cache eviction policy'. Is it hard to follow here? Raters said "
        "an editor would fix 0 of 100 such findings, and called 36 more optional. If it is, keep at most two "
        "nouns together.\n"
        "- line 5 [made-up-rule] something. Is it hard to follow here? If it is, do it.")
    one = Result(path="p.md", words=9, findings=r.findings[:1])
    assert m.questions([one], prec).startswith("readcost: 1 sentence in 9 words that may be hard to follow.")
    assert m.questions([Result(path="p.md")], prec) == ""
    capped = m.questions([r], prec, max_items=1, max_chars=400)
    assert len(capped) == 400 and capped.endswith("...")
    assert "- ...and 2 more" in m.questions([r], prec, max_items=1)
    other = Result(path="q.md", words=5, findings=[_finding("stacked-nouns", 2, "m", "S.", path="q.md")])
    assert "- q.md:2 [stacked-nouns]" in m.questions([r, other], prec)
    # Rules with fewer than 5 labelled findings get no note.
    assert m._precision_102({"rules": {"x": {"labelled": 4, "correct": 1, "accepted": 2}}}, "x") is None


def test_the_precision_copy_is_checked_against_its_hash(tmp_path):
    changed = tmp_path / "rule_precision.json"
    changed.write_bytes(m.PRECISION_FILE.read_bytes().replace(b'"correct": 4', b'"correct": 5', 1))
    with pytest.raises(SystemExit):
        m.heldout_precision(changed)
    assert len(m.QUESTIONS_COMMIT) == 40


def test_arm_d_has_bs_prompt_and_bs_findings_with_the_feedback_as_questions(analyzer):
    fb = m.feedbacks(analyzer, PARA, m.heldout_precision())
    assert fb["B"] == m.feedback(analyzer, PARA)
    d, b = m.edit_prompt("D", PARA, fb["D"]), m.edit_prompt("B", PARA, fb["B"])
    assert d == b.replace(fb["B"], fb["D"])
    assert "Is it hard to follow here?" in fb["D"] and "Fix:" not in fb["D"]
    # The same findings, in the same order, at the same lines.
    import re

    def tags(text):
        return re.findall(r"^- (line \d+ \[[a-z-]+\])", text, re.MULTILINE)
    assert tags(fb["D"]) == tags(fb["B"]) and len(tags(fb["B"])) >= 2


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
    """Edits: B and D mark the text "Plainly", C only tags it. Judges pick the "Plainly" version, else tie.

    Every edit differs by paragraph and editor, so no two judge prompts are the same (the cache would
    answer a repeated prompt without a call). Fact checks by judge "j1" list a lost fact in every B
    edit, so B loses more facts than D without changing content (that needs two judges).
    """

    def __init__(self, cost=0.01):
        self.calls, self.cost = [], cost

    def __call__(self, model, prompt, schema, system=None):
        self.calls.append((model, system, prompt))
        meta = {"requested": model, "served": model + "-x", "cost": self.cost}
        if "text" in schema["properties"]:
            assert system == m.SYSTEM
            original = prompt.rsplit("Paragraph:\n", 1)[1]
            if "Is it hard to follow here?" in prompt:
                text = f"Plainly, as asked ({model}): {original}"
            elif "prose checker" in prompt:
                text = f"Plainly ({model}): {original}"
            else:
                text = f"{original} ({model})"
            return {"text": text}, meta
        if "easier" in schema["properties"]:
            assert system is None
            one = prompt.split("Version 1:\n", 1)[1].split("\n\nVersion 2:\n")[0]
            two = prompt.split("Version 2:\n", 1)[1].split("\n\nGive your reason")[0]
            a, b = one.startswith("Plainly"), two.startswith("Plainly")
            pick = "tie" if a == b else "1" if a else "2"
            return {"reason": "r", "easier": pick}, meta
        revision = prompt.split("Revision:\n", 1)[1]
        lost = ["a fact"] if model == "j1" and revision.startswith("Plainly (") else []
        return {"lost": lost, "added": [], "changed": []}, meta


# Arm B's feedback as readcost prints it at a57e19e, which the run's verify step requires. The
# tests also run against later readcost (a pull request is tested merged with main), where
# `-o agent` already words feedback as #102 does, so the run tests stand B's wording in for it.
B_AT_A57E19E = "readcost: 2 hard-to-read constructions in 150 words. Rewrite these sentences where the finding holds"


@pytest.fixture
def pinned_b(monkeypatch):
    real = m.feedbacks

    def feedbacks(analyzer, text, precision):
        fb = real(analyzer, text, precision)
        return {**fb, "B": f"{B_AT_A57E19E} ({m.sha(text)[:8]})."}
    monkeypatch.setattr(m, "feedbacks", feedbacks)


def _ref(tmp_path, n=3):
    ref = tmp_path / "ref"
    ref.mkdir()
    rows = [{"id": f"p{i}", "text": PARA.replace("release", f"release {i}")} for i in range(n)]
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return ref


def test_a_run_judges_every_pair_in_both_orders_and_the_report_decides(tmp_path, analyzer, pinned_b):
    ref = _ref(tmp_path)
    fake = FakeAsk()
    client = m.Client(ref / "replies.jsonl", ask=fake)
    status = m.run(ref, client, analyzer, editors=["e1", "e2"], judges=["j1", "j2"], workers=2)
    assert status == {"edits": True, "BC": True, "facts": True, "BA": True, "CA": True,
                      "editsD": True, "DB": True, "factsD": True, "DC": True, "DA": True}
    # 3 paragraphs x 2 editors: 12 edits, 3 pairs x 2 orders x 2 judges x 6 units, 2 x 2 x 6 fact checks;
    # then D: 6 edits, 72 judgements, 12 fact checks.
    assert len(fake.calls) == 12 + 72 + 24 + 6 + 72 + 12 == client.calls
    res = m.analyse(m.collect(ref, client, analyzer, ["e1", "e2"], ["j1", "j2"]), analyzer,
                    ["e1", "e2"], ["j1", "j2"])
    assert res["pairs"]["BC"]["estimate"][0] == 1.0 and res["pairs"]["BC"]["label"] == "better"
    assert res["pairs"]["CA"]["counts"] == {"tie": 12}     # neither starts with "Plainly"
    assert res["claims"]["readcost feedback beats a generic instruction"]
    assert not res["claims"]["readcost adds nothing over a generic instruction"]
    # D ties B (both "Plainly"), beats C and A, and loses half a fact less per edit than B.
    assert res["pairs"]["DB"]["counts"] == {"tie": 12} and res["pairs"]["DB"]["label"] == "no meaningful advantage"
    assert res["pairs"]["DC"]["estimate"][0] == 1.0 and res["pairs"]["DA"]["label"] == "better"
    assert res["D_minus_B"]["lost"] == (-0.5, -0.5, -0.5)
    assert res["content"]["B"]["share_changing"][0] == 0.0 and res["content"]["B"]["mean_lost"] == 0.5
    assert res["d_readings"] == {"the question wording should ship": True,
                                 "the question wording should not ship": False,
                                 "an edit with feedback as questions beats a generic instruction": True,
                                 "an edit with feedback as questions beats the original": True}
    assert {k[0] for k in res["length"]} == {"A", "B", "C", "D"}
    text = m.render(res, status, client)
    assert "| B against C | 1.000 [1.000, 1.000] | better |" in text
    assert text.index("| B against C |") < text.index("### Arm D") < text.index("| D against B | 0.500")
    assert "| the question wording should ship | yes |" in text
    assert "| Facts lost per edit | -0.500 [-0.500, -0.500] |" in text
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
    assert again.calls == [] and client2.calls == 198


def test_caps_stop_the_run_before_crossing_and_count_cached_replies(tmp_path, analyzer, pinned_b):
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


def test_arm_d_runs_after_the_original_phases_and_only_d_may_pass_the_old_caps(tmp_path, analyzer, pinned_b):
    ref = _ref(tmp_path, n=1)
    fake = FakeAsk(cost=0.5)
    # One paragraph, one editor, one judge: the original phases make 2 + 2 + 2 + 2 + 2 = 10 calls, $5.
    client = m.Client(ref / "replies.jsonl", ask=fake, cost_cap=5.2, d_cost_cap=7.05)
    status = m.run(ref, client, analyzer, editors=["e1"], judges=["j1"], workers=1)
    assert [k for k, v in status.items() if v] == ["edits", "BC", "facts", "BA", "CA", "editsD", "DB", "factsD"]
    assert status["DC"] is False and "DA" not in status
    # D's edit, its two judgements and its fact check fit under $7.05; D against C does not.
    assert client.spent == pytest.approx(7.0) and len(fake.calls) == 14
    kinds = ["D" if "Is it hard to follow here?" in pr or "Plainly, as asked" in pr else "-" for _m, _s, pr in fake.calls]
    assert kinds[:10] == ["-"] * 10 and kinds[10:] == ["D"] * 4
    # With the old caps stopping an original phase, D never starts.
    (tmp_path / "x").mkdir()
    ref2 = _ref(tmp_path / "x", n=1)
    client2 = m.Client(ref2 / "replies.jsonl", ask=FakeAsk(cost=0.5), cost_cap=1.5, d_cost_cap=100.0)
    status2 = m.run(ref2, client2, analyzer, editors=["e1"], judges=["j1"], workers=1)
    assert status2 == {"edits": True, "BC": False}
    assert m.D_COST_CAP == 106.0 and m.D_CALL_CAP == 9160 and m.COST_CAP == 60.0 and m.CALL_CAP == 5200


def test_the_run_stops_if_b_and_d_get_the_same_feedback(tmp_path, analyzer, monkeypatch):
    monkeypatch.setattr(m, "feedbacks", lambda an, text, prec: {"B": "same", "D": "same"})
    with pytest.raises(SystemExit, match="readcost is not a57e19e"):
        m.run(_ref(tmp_path, n=1), m.Client(tmp_path / "r.jsonl", ask=FakeAsk()), analyzer, ["e1"], ["j1"])


def test_d_readings_follow_amendment_7():
    r = m.d_readings
    tie = (0.50, 0.46, 0.54)
    assert r(tie, (-0.2, -0.4, -0.01), None, None, None, None, None)["the question wording should ship"]
    assert r(tie, (0.0, -0.1, 0.1), (-0.05, -0.08, -0.01), None, None, None, None)["the question wording should ship"]
    # As good on reading, but more facts lost: it should not ship, even with less length change.
    got = r(tie, (0.2, 0.05, 0.4), (-0.05, -0.08, -0.01), None, None, None, None)
    assert not got["the question wording should ship"] and got["the question wording should not ship"]
    # The lower bound must clear 0.45.
    assert not r((0.50, 0.44, 0.56), (-0.2, -0.4, -0.01), None, None, None, None, None)[
        "the question wording should ship"]
    worse = r((0.42, 0.36, 0.49), (0.0, -0.1, 0.1), None, None, None, None, None)
    assert worse["the question wording should not ship"] and not worse["the question wording should ship"]
    # Neither: no reading holds.
    none = r((0.48, 0.42, 0.55), (0.0, -0.1, 0.1), (0.0, -0.1, 0.1), None, None, None, None)
    assert not none["the question wording should ship"] and not none["the question wording should not ship"]
    assert not any(r(None, None, None, None, None, None, None).values())
    beats = r(None, None, None, (0.6, 0.52, 0.68), (0.0, -0.05, 0.05), (0.6, 0.52, 0.68), (0.02, 0.0, 0.05))
    assert beats["an edit with feedback as questions beats a generic instruction"]
    assert beats["an edit with feedback as questions beats the original"]


def test_a_failed_reply_is_asked_again_and_reported_missing_if_it_fails_twice(tmp_path, analyzer, pinned_b):
    ref = _ref(tmp_path, n=1)
    inner = FakeAsk()

    def flaky(model, prompt, schema, system=None):
        if model == "bad":
            inner.calls.append((model, system, prompt))
            return None, {"requested": model, "error": "HTTP 500"}
        return inner(model, prompt, schema, system=system)
    client = m.Client(ref / "replies.jsonl", ask=flaky)
    m.run(ref, client, analyzer, editors=["e1", "bad"], judges=["j1"], workers=1)
    assert sum(c[0] == "bad" for c in inner.calls) == 6    # three arms, asked twice each
    res = m.analyse(m.collect(ref, client, analyzer, ["e1", "bad"], ["j1"]), analyzer, ["e1", "bad"], ["j1"])
    assert res["missing_edits"] == 2 and res["missing_edits_D"] == 1
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
    paths = ["README.md", "docs/guide.md", "docs/huge.md"]
    fetched = []

    def get(repo, commit, path):
        fetched.append((repo, commit, path))
        return "x" * 2_000_000 if path == "docs/huge.md" else f"text of {path}"
    commit, files = m.github_files("o/r", get_tree=lambda repo: ("abc", paths), get=get)
    assert commit == "abc" and files[0] == ("README.md", "text of README.md")
    assert [p for p, _ in files] == ["README.md", "docs/guide.md"]
    assert all(c == "abc" for _r, c, _p in fetched)
    assert m.github_files("o/r", get_tree=lambda repo: None) == "repository unavailable"
    assert m.github_files("o/r", get_tree=lambda repo: ("abc", ["src/x.md"])) == "no README"
    assert m.github_files("o/r", get_tree=lambda repo: ("abc", ["README.md"]),
                          get=lambda *a: "x" * 2_000_000) == "README over 1 MB"
