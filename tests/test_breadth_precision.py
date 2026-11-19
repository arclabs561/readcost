"""The breadth precision draw (scripts/breadth_precision.py).

Every fixture is made up; no third-party text is read and nothing touches
the network.
"""

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


bp = _mod("breadth_precision")


def test_queries_and_splits():
    q = bp.lang_query("C#", 200, 20000)
    assert q == 'language:"C#" stars:200..20000 pushed:>=2026-11-01 created:<2026-01-01 fork:false archived:false'
    assert bp.split_range(200, 20000) == [(200, 10100), (10101, 20000)]
    assert bp.split_range(5, 6) == [(5, 5), (6, 6)]


def test_quotas_match_the_registration():
    assert bp.quota("md") == {"default": 16, "opt-in": 8, "near-default": 8, "near-opt-in": 4, "decoy": 4}
    assert bp.quota("pr") == bp.quota("commit") == bp.quota("rst") == bp.quota("md")
    assert bp.quota("html")["default"] == 8
    assert bp.quota("src-go") == {"default": 4, "opt-in": 2, "near-default": 2, "near-opt-in": 1, "decoy": 1}
    findings = sum(len(bp.DEFAULT_RULES) * bp.quota(s)["default"] + len(bp.OPT_IN_RULES) * bp.quota(s)["opt-in"]
                   for s in bp.STRATA)
    near = sum(sum(bp.quota(s)["near-default" if r in bp.DEFAULT_RULES else "near-opt-in"] for r in bp.LOOSE)
               for s in bp.STRATA)
    decoys = sum(bp.quota(s)["decoy"] for s in bp.STRATA)
    assert (findings, near, decoys) == (750, 200, 25)


@pytest.mark.parametrize("stratum,path,ok", [
    ("md", "docs/guide.md", True),
    ("md", "Docs/Guide.MDX", True),
    ("md", "src/design/x.md", True),
    ("md", "docs/CHANGELOG.md", False),
    ("md", "docs/node_modules/x.md", False),
    ("md", "notes/x.md", False),
    ("rst", "docs/index.rst", True),
    ("rst", "doc/api/history.rst", False),
    ("rst", "src/x.rst", False),
    ("html", "site/about.html", True),
    ("html", "docs/x.htm", True),
    ("html", "public/x.html", False),
    ("src-py", "pkg/mod.py", True),
    ("src-py", "pkg/tests/test_mod.py", False),
    ("src-py", "pkg/x_pb2.py", False),
    ("src-js", "web/app.tsx", True),
    ("src-js", "dist/app.js", False),
    ("src-js", "lib/app.min.js", False),
    ("src-go", "api/x.pb.go", False),
    ("src-go", "internal/gen/x.go", False),
    ("src-jvm", "app/src/main/Main.kt", True),
    ("src-c", "include/x.hpp", True),
    ("src-rb", "lib/x.rb", True),
    ("src-rb", "x.toml", False),
])
def test_eligible(stratum, path, ok):
    assert bp.eligible(stratum, path) is ok


def test_kinds_and_readme_stratum():
    assert bp.kind_of("src-js", "a/b.ts") == "TypeScript comment"
    assert bp.kind_of("src-rs", "a/lib.rs") == "Rust doc comment"
    assert bp.kind_of("commit", "commit/abc") == "commit message"
    assert bp.kind_of("pr", "pr/12") == "pull request description"
    assert all(ext in bp.KIND_BY_EXT for exts in bp.SRC_STRATA.values() for ext in exts)
    assert bp.readme_stratum("README.md") == "md"
    assert bp.readme_stratum("docs/README.rst") == "rst"
    assert bp.readme_stratum("README.txt") is None
    assert bp.check_path("commit", "commit/abc") == "abc.gitmessage"
    assert bp.check_path("pr", "pr/7") == "pr-7.md"


def test_choose_is_seeded_and_order_free():
    a = bp.choose(["c", "a", "b", "d"], 2, "s")
    assert a == bp.choose(["d", "b", "a", "c"], 2, "s")
    assert len(a) == 2 and set(a) <= {"a", "b", "c", "d"}


def test_commit_log_and_filters():
    out = ("1111\x00Ann\x00ann@example.com\x002026-11-03T10:00:00+01:00\x00Fix the parser\n\nMore words.\n\x1e\n"
           "2222\x00dependabot[bot]\x00x@example.com\x002026-11-04T10:00:00Z\x00Bump x\n\x1e\n"
           "3333\x00Bob\x00bob@example.com\x002026-10-31T23:59:59-00:00\x00Old\n\x1e\n"
           "4444\x00Cy\x00cy@example.com\x002026-11-01T00:30:00+01:00\x00Before midnight UTC\n\x1e")
    recs = bp.parse_log(out)
    assert [r["sha"] for r in recs] == ["1111", "2222", "3333", "4444"]
    assert recs[0]["message"] == "Fix the parser\n\nMore words.\n"
    assert [r["sha"] for r in bp.eligible_commits(recs)] == ["1111"]
    assert bp.is_bot("Renovate Bot", "x") and not bp.is_bot("Ann", "ann@example.com")


def test_pr_filters():
    items = [{"number": 1, "body": "Adds x.", "user": {"login": "ann", "type": "User"}},
             {"number": 2, "body": "", "user": {"login": "bob", "type": "User"}},
             {"number": 3, "body": "Bump", "user": {"login": "dependabot[bot]", "type": "Bot"}},
             {"number": 4, "body": "Thing", "user": {"login": "x[bot]", "type": "User"}},
             {"number": 5, "body": None, "user": None}]
    assert [p["number"] for p in bp.eligible_prs(items)] == [1]


def _cand(repo, lang, fork=False):
    return {"repo": repo, "language": lang, "stars": 300, "created_at": "2020-01-01T00:00:00Z",
            "default_branch": "main", "fork": fork, "archived": False, "query": "q"}


def test_walk_caps_owners_and_skips_excluded():
    cands = [_cand(f"own{i % 3}/r{i}", "Go") for i in range(30)] + [_cand("arclabs561/x", "Go"),
                                                                     _cand("ex/cluded", "Go"),
                                                                     _cand("fo/rk", "Go", fork=True)]
    picked, drops = bp.walk(cands, {"ex/cluded"}, per_lang=10, owner_cap=2, langs=("Go",))
    assert len(picked) == 6  # three owners, two each
    assert {"arclabs561/x", "ex/cluded", "fo/rk"}.isdisjoint(c["repo"] for c in picked)
    assert drops["owner cap"] > 0
    again, _ = bp.walk(list(reversed(cands)), {"ex/cluded"}, per_lang=10, owner_cap=2, langs=("Go",))
    assert [c["repo"] for c in again] == [c["repo"] for c in picked]


def test_candidates_round_trip(tmp_path):
    rows = [_cand("b/two", "Rust"), _cand("a/one", "Go", fork=True)]
    p = tmp_path / "c.tsv"
    bp.write_candidates(p, rows)
    back = bp.read_candidates(p)
    assert [r["repo"] for r in back] == ["a/one", "b/two"]
    assert back[0]["fork"] is True and back[1]["stars"] == 300


def test_loosened_restores_the_constants():
    from readcost import features
    before = (features.STACKED_NOUNS_MIN, features.LONG_DEPENDENCY_Z)
    with bp.loosened("long-dependency"):
        assert features.LONG_DEPENDENCY_CORE_MIN == 7 and features.LONG_DEPENDENCY_Z == 2.0
        assert features.STACKED_NOUNS_MIN == before[0]  # one rule at a time
    assert (features.STACKED_NOUNS_MIN, features.LONG_DEPENDENCY_Z) == before
    with pytest.raises(RuntimeError), bp.loosened("stacked-nouns"):
        raise RuntimeError
    assert features.STACKED_NOUNS_MIN == before[0]


def _f(rule, start, end, s0, s1, sentence="S"):
    return {"rule": rule, "start": start, "end": end, "sentence_start": s0, "sentence_end": s1,
            "sentence": sentence, "message": "m", "excerpt": "e", "key": f"{rule}{start}"}


def test_near_misses_skip_sentences_with_a_default_finding():
    default = [_f("stacked-nouns", 10, 20, 0, 50), _f("inline-list", 60, 70, 55, 90)]
    loose = [_f("stacked-nouns", 30, 35, 0, 50), _f("stacked-nouns", 60, 64, 55, 90),
             _f("inline-list", 60, 70, 55, 90)]
    got = bp.near_misses(default, loose, "stacked-nouns")
    assert [(f["start"], f["end"]) for f in got] == [(60, 64)]
    assert bp.dedupe_against([_f("x", 1, 2, 0, 9, "A"), _f("x", 3, 4, 0, 9, "B")], [_f("x", 5, 6, 0, 9, "A")]) \
        == [_f("x", 3, 4, 0, 9, "B")]


def test_check_text_finds_near_misses_on_made_up_text():
    an = bp.analyzer()
    text = ("You can install it with pip, conda or uv on any system that runs the job.\n\n"
            "The service reads the configuration file and writes the results to the output folder "
            "before it exits.\n\n" * 3)
    rec = {"stratum": "md", "repo": "a/b", "commit": "c", "path": "docs/x.md", "blob": "x"}
    assert bp.check_text(an, text[:300], rec)["drop"] == "under 100 words"
    out = bp.check_text(an, text * 3, rec)
    near = {f["rule"] for f in out["near"]}
    assert "inline-list" in near  # three items: one short of the default four
    assert "inline-list" not in {f["rule"] for f in out["findings"]}
    assert all(f["message"].startswith("3 items") for f in out["near"] if f["rule"] == "inline-list")
    # The parse cache leaves the default findings as a fresh run gives them.
    fresh = an.check_text(text * 3, None, "docs/x.md")
    assert sorted((f.feature, f.start) for f in fresh.findings if f.start is not None) == \
        sorted((f["rule"], f["start"]) for f in out["findings"])
    for s in out["sentences"]:
        assert not any(s["start"] < f["sentence_end"] and f["sentence_start"] < s["end"]
                       for f in out["findings"] + out["near"])


def test_check_text_reads_commit_messages_and_doc_comments():
    an = bp.analyzer()
    msg = "parser: fix the cache\n\nThe cache that the parser keeps was never cleared when the file changed.\n"
    rec = {"stratum": "commit", "repo": "a/b", "commit": "c", "path": "commit/abc", "blob": "abc"}
    out = bp.check_text(an, msg, rec)
    assert not out.get("drop") and out["words"] > 0
    src = "\n".join(f"/// The function that the reader calls returns the value number {k} of the table.\n"
                    f"fn f{k}() {{}}" for k in range(6))
    rec = {"stratum": "src-rs", "repo": "a/b", "commit": "c", "path": "src/lib.rs", "blob": "x"}
    out = bp.check_text(an, src, rec)
    assert not out.get("drop") and out["words"] >= 40
    assert all(src[f["start"]:f["end"]] for f in out["findings"])


def _kept(stratum, repo, n_find, n_near, n_sent):
    findings = [_f("stacked-nouns", 10 * k, 10 * k + 5, 10 * k, 10 * k + 9, f"{repo} f{k}") |
                {"key": f"{stratum}{repo}f{k}"} for k in range(n_find)]
    near = [_f("stacked-nouns", 500 + 10 * k, 505 + 10 * k, 500 + 10 * k, 509 + 10 * k, f"{repo} n{k}") |
            {"key": f"{stratum}{repo}n{k}"} for k in range(n_near)]
    sents = [{"start": 1000 + 20 * k, "end": 1019 + 20 * k, "words": 6, "sentence": f"{repo} s{k}"}
             for k in range(n_sent)]
    path = {"commit": "commit/abc", "md": "docs/x.md"}.get(stratum, "pkg/x.go")
    return {"stratum": stratum, "repo": repo, "commit": "c", "path": path, "blob": "b",
            "findings": findings, "near": near, "sentences": sents}


def _tokens(rec, start, end):
    words = [("cache", "NOUN"), ("stores", "VERB"), ("the", "DET"), ("plan", "NOUN"), ("today", "NOUN")]
    out, pos = [], start
    for w, p in words:
        out.append([w, p, True, pos, pos + len(w)])
        pos += len(w) + 1
    return out


def test_draw_stratum_respects_quotas_and_caps():
    kept = [_kept("md", f"o/r{k}", 5, 5, 3) for k in range(6)]
    items, counts = bp.draw_stratum("md", kept, _tokens)
    finds = [x for x in items if x["item"] == "finding"]
    near = [x for x in items if x["item"] == "near"]
    decoys = [x for x in items if x["item"] == "decoy"]
    assert len(finds) == 12 and len(near) == 8 and len(decoys) == 4  # cap 2 x 6 repositories; quotas 8 and 4
    assert max(sum(1 for x in finds if x["repo"] == r) for r in {x["repo"] for x in finds}) == 2
    assert len({x["repo"] for x in decoys}) == 4
    assert counts["sampled"]["stacked-nouns"] == 12 and counts["sampled"]["inline-list"] == 0
    assert all(d["rule"] in bp.RULES and d["message"] for d in decoys)
    again, _ = bp.draw_stratum("md", list(reversed(kept)), _tokens)
    assert [x["key"] for x in again] == [x["key"] for x in items]


def test_build_sample_fills_view_fields():
    kept = [_kept("src-go", f"o/r{k}", 2, 2, 2) for k in range(3)] + \
           [_kept("commit", f"o/r{k}", 2, 1, 1) for k in range(2)]
    src = "x" * 2000
    sources = {(c["repo"], c["path"]): src for c in kept}
    sample, _ = bp.build_sample(kept, sources, _tokens)
    assert {x["family"] for x in sample} == {"doc comments", "commit"}
    assert len({x["i"] for x in sample}) == len(sample)
    for x in sample:
        assert set(bp.rater_item(x)) == {"i", "kind", "rule", "message", "excerpt", "sentence", "before", "after"}
        assert set(bp.blind_item(x)) == {"i", "kind", "excerpt", "sentence", "before", "after"}
        assert set(bp.POINTER_FIELDS) <= set(x)
    assert {x["kind"] for x in sample if x["stratum"] == "commit"} == {"commit message"}
    json.dumps([{k: x[k] for k in bp.POINTER_FIELDS} for x in sample])


PRIMED = """Rubric

You are labelling findings.

Reply format

Each batch file is a JSON list of findings. Each finding has "i" (its id), "rule", "message", "excerpt"
(the flagged words). scripts/heldout_report.py also reads the reply objects.
"""

BLIND = """Rubric (unprimed protocol)

You are helping an editor of technical writing. Each item is one sentence from a project's
documentation, with a few marked words ("excerpt") somewhere in it.

Reply format

Each batch file is a JSON list of items. Each item has "i" (its id), "excerpt" (the marked words),
"""


def test_rubrics_change_only_to_name_the_kind():
    p = bp.rubric_primed(PRIMED)
    assert bp.KIND_LINE in p and '"i" (its id), "kind", "rule"' in p
    assert p.replace("\n" + bp.KIND_LINE + "\n", "").replace('"kind", ', "").replace(
        "The report script also reads", "scripts/heldout_report.py also reads") == PRIMED
    b = bp.rubric_blind(BLIND)
    assert bp.KIND_LINE in b and '"i" (its id), "kind", "excerpt"' in b and "commit message or a pull" in b


def test_batches_cover_every_item_once():
    items = [{"i": 100000 + k} for k in range(97)]
    for seed in bp.RATER_SEEDS.values():
        bs = bp.hp.batches(items, seed)
        assert sorted(x["i"] for b in bs for x in b) == [x["i"] for x in items]
        assert all(35 <= len(b) <= 50 for b in bs)
    orders = {tuple(x["i"] for b in bp.hp.batches(items, s) for x in b) for s in
              [*bp.RATER_SEEDS.values(), *bp.BLIND_SEEDS.values()]}
    assert len(orders) == 15
    random.Random(0)
