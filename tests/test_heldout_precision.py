"""The held-out precision draw (scripts/heldout_precision.py).

Every fixture is made up; no third-party text is read and nothing touches
the network.
"""

import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


hp = _mod("heldout_precision")


def test_day_queries_cover_the_registered_window():
    qs = hp.day_queries()
    assert len(qs) == 16
    assert qs[0] == "created:2026-11-02 stars:>=50 fork:false archived:false"
    assert qs[-1].startswith("created:2026-11-17 ")
    split = hp.split_query(qs[0])
    assert [q.split()[1] for q in split] == ["stars:50..99", "stars:100..499", "stars:>=500"]
    assert all(q.startswith("created:2026-11-02 ") for q in split)


def test_repo_names_and_exclusion():
    text = 'see https://github.com/Some-Org/tool.git and "other/repo", not docs/rules.md'
    names = hp.repo_names(text)
    assert "some-org/tool" in names and "other/repo" in names
    assert hp.excluded("Some-Org/tool", names) == "in a development corpus"
    assert hp.excluded("arclabs561/anything", set()) == "owner arclabs561"
    assert hp.excluded("new/project", names) is None


def test_fenced_share_counts_lines_inside_fences():
    text = "Intro line.\n\n```sh\nmake\nmake install\n```\n\nClosing line.\n"
    assert hp.fenced_share(text) == 4 / 6
    assert hp.fenced_share("") == 0.0
    assert hp.fenced_share("~~~\na\n~~~\n") == 1.0


def test_doc_paths():
    assert hp.is_doc_path("docs/design.md")
    assert hp.is_doc_path("Docs/Guide.MDX")
    assert hp.is_doc_path("pkg/adr/0001-choice.md")
    assert hp.is_doc_path("src/design/notes.markdown")
    assert not hp.is_doc_path("docs/README.md")
    assert not hp.is_doc_path("docs/CHANGELOG.md")
    assert not hp.is_doc_path("docs/image.png")
    assert not hp.is_doc_path("notes/design.md")
    assert not hp.is_doc_path("docs/node_modules/x/docs/a.md")


def test_pick_docs_is_seeded_and_capped():
    paths = [f"docs/p{i}.md" for i in range(9)] + ["src/main.rs"]
    a = hp.pick_docs("o/r", paths)
    assert a == hp.pick_docs("o/r", list(reversed(paths)))
    assert len(a) == 2 and all(p.startswith("docs/") for p in a)
    assert hp.pick_docs("o/r", ["docs/a.md", "x.md"]) == ["docs/a.md"]


def _items(n, repos=5, rule="stacked-nouns"):
    return [{"key": hp.finding_key("r", i), "repo": f"o/r{i % repos}", "rule": rule, "sentence": f"s{i}"}
            for i in range(n)]


def test_draw_respects_quota_cap_and_seed():
    items = _items(50, repos=5)
    got = hp.draw(items, 8, 2, "seed")
    assert len(got) == 8
    assert max(Counter(x["repo"] for x in got).values()) <= 2
    assert got == hp.draw(list(reversed(items)), 8, 2, "seed")  # input order does not matter
    assert got != hp.draw(items, 8, 2, "other")
    assert len(hp.draw(items, 40, 2, "seed")) == 10  # five repositories, two each


def test_dedupe_keeps_first_in_key_order():
    a = {"key": "b", "rule": "x", "sentence": "same"}
    b = {"key": "a", "rule": "x", "sentence": "same"}
    c = {"key": "c", "rule": "y", "sentence": "same"}
    assert hp.dedupe([a, b, c]) == [b, c]


def test_rule_names_are_balanced():
    names = hp.rule_names(80, "s")
    assert Counter(names) == Counter({r: 8 for r in hp.RULES})
    assert names == hp.rule_names(80, "s")


TOKENS = [("The", "DET", True), ("cache", "NOUN", True), ("keeps", "VERB", True), ("each", "DET", True),
          ("block", "NOUN", True), (",", "PUNCT", False), ("then", "ADV", True), ("writes", "VERB", True)]


def test_decoy_span_ends_on_content_words():
    for seed in range(50):
        span = hp.decoy_span(TOKENS, random.Random(seed))
        assert span is not None
        a, b = span
        assert 1 <= b - a <= 3
        run = TOKENS[a:b + 1]
        assert all(t[2] for t in run)
        assert run[0][1] in hp.CONTENT_POS and run[-1][1] in hp.CONTENT_POS


def test_decoy_span_falls_back_and_gives_up():
    only_two = [("big", "ADJ", True), ("cats", "NOUN", True), (".", "PUNCT", False)]
    assert hp.decoy_span(only_two, random.Random(0)) == (0, 1)
    none = [("the", "DET", True), ("a", "DET", True), ("!", "PUNCT", False)]
    assert hp.decoy_span(none, random.Random(0)) is None


def test_decoy_messages_cover_every_rule():
    for rule in hp.RULES:
        msg = hp.decoy_message(rule, ["cache", "keeps"])
        assert msg and "{" not in msg
    assert hp.decoy_message("long-dependency", ["cache", "keeps", "each"]) == "'cache' and 'each' are 2 words apart"


def test_context_cuts_at_whitespace():
    src = "alpha beta gamma. The sentence itself. delta epsilon zeta"
    s = src.index("The")
    e = src.index("itself.") + len("itself.")
    assert hp.context(src, s, e, width=200) == ("alpha beta gamma.", "delta epsilon zeta")
    before, after = hp.context(src, s, e, width=8)
    assert before == "gamma." and after == "delta"


def test_batches_shuffle_per_seed_and_cover_everything():
    items = [{"i": i} for i in range(100)]
    b1 = hp.batches(items, 1)
    b2 = hp.batches(items, 2)
    assert len(b1) == 2 or len(b1) == 3
    assert sorted(x["i"] for b in b1 for x in b) == list(range(100))
    assert [x["i"] for b in b1 for x in b] != [x["i"] for b in b2 for x in b]
    assert all(35 <= len(b) <= 50 for b in b1)


def test_ids_are_unique_and_fixed():
    keys = [hp.finding_key(i) for i in range(300)]
    ids = hp.assign_ids(keys)
    assert len(set(ids.values())) == 300
    assert ids == hp.assign_ids(list(reversed(keys)))


def test_rubric_is_verbatim_with_reply_format():
    sys.path.insert(0, str(SCRIPTS))
    from second_rater import RUBRIC
    text = hp.rubric_text()
    assert RUBRIC in text
    assert hp.EXTRA_DEFINITIONS in text
    assert '"construction_present"' in text and '"labels"' in text


def _checked(n_repos=30):
    """Made-up results of `check`: findings and finding-free sentences per file."""
    rows, sources = [], {}
    for r in range(n_repos):
        repo, path = f"own/repo{r}", "README.md"
        words = [f"Alpha{r}", "builds", "every", "small", "index", "quickly", "today"]
        src = " ".join(words) + ". " + " ".join(reversed(words)) + "."
        toks, pos = [], 0
        tags = ["PROPN", "VERB", "DET", "ADJ", "NOUN", "ADV", "NOUN"]
        for w, t in zip(words, tags):
            toks.append([w, t, True, pos, pos + len(w)])
            pos += len(w) + 1
        sent = {"start": 0, "end": pos, "words": 7,
                "sentence": " ".join(words) + ".", "tokens": toks}
        findings = []
        for k, rule in enumerate(hp.RULES):
            if (r + k) % 2:
                continue
            findings.append({"rule": rule, "message": "m", "excerpt": "x", "sentence": f"{rule} sentence {r}",
                             "start": 50, "end": 55, "sentence_start": pos + 1, "sentence_end": len(src),
                             "key": hp.finding_key(repo, "c", path, rule, r)})
        rows.append({"repo": repo, "commit": "c" * 40, "path": path, "blob": f"b{r}", "stratum": "S1",
                     "words": 400, "findings": findings, "sentences": [sent]})
        sources[(repo, path)] = src
    rows.append({"repo": "own/dropped", "commit": "c", "path": "README.md", "blob": "z", "stratum": "S1",
                 "drop": "mostly code"})
    return rows, sources


def test_build_sample_on_made_up_results():
    rows, sources = _checked()
    sample, counts = hp.build_sample(rows, sources)
    real = [x for x in sample if not x["decoy"]]
    decoys = [x for x in sample if x["decoy"]]
    assert counts["sampled"]["S1"]["stacked-nouns"] == 15  # every finding of the rule (cap 2, one each)
    assert all(x["repo"] != "own/dropped" for x in sample)
    # one decoy sentence per file, so D-random takes them all and D-long finds none left
    assert len(decoys) == 30
    assert counts["decoys"]["S1"] == {"random": 30}
    assert len({x["i"] for x in sample}) == len(sample)
    for d in decoys:
        assert d["rule"] in hp.RULES
        assert sources[(d["repo"], d["path"])][d["start"]:d["end"]] == d["excerpt"]
        assert d["excerpt"] in d["sentence"]
    assert all(set(hp.POINTER_FIELDS) <= set(x) for x in sample)
    again, _ = hp.build_sample(json.loads(json.dumps(rows)), sources)
    assert [x["key"] for x in again] == [x["key"] for x in sample]
    assert len(real) == sum(counts["sampled"]["S1"].values())


def test_check_one_on_a_made_up_readme(tmp_path):
    prose = ("The parser caches every token, making lookups faster. The tool performs validation of the input. "
             "It supports Rust, Go, Python, Java and Haskell in one binary. "
             "Readers who open the guide find the steps in order.\n\n") * 12
    text = "# Tool\n\n" + prose + "\n\n```sh\nmake\n```\n"
    path = tmp_path / "README.md"
    path.write_text(text)
    an = hp.analyzer()
    row = hp.check_one(an, path, "own/tool", "c" * 40, "README.md", "blob", "S1")
    assert "drop" not in row
    rules = {f["rule"] for f in row["findings"]}
    assert {"participial-clause", "nominalization"} <= rules  # opt-in rules are on
    for f in row["findings"]:
        assert text[f["start"]:f["end"]] == f["excerpt"]
    hit = [(f["sentence_start"], f["sentence_end"]) for f in row["findings"]]
    assert row["sentences"]
    for s in row["sentences"]:
        assert all(not (a < s["end"] and s["start"] < b) for a, b in hit)
        assert text[s["start"]:s["end"]] == s["sentence"]
        for t in s["tokens"]:
            if t[3] is not None:
                assert text[t[3]:t[4]] == t[0]
    short = tmp_path / "short.md"
    short.write_text("A short README that says little about the tool here.\n")
    assert hp.check_one(an, short, "own/tool", "c", "short.md", "b", "S1")["drop"] == "under 300 words"
