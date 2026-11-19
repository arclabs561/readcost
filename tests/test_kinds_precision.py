"""The draw by kind of document (scripts/kinds_precision.py).

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


kp = _mod("kinds_precision")


@pytest.mark.parametrize("path,kind", [
    ("CHANGELOG.md", "changelog"),
    ("docs/release-notes/v2.md", "changelog"),
    ("docs/HISTORY.rst", "changelog"),
    ("ops/runbooks/disk-full.md", "runbook"),
    ("docs/postmortem-2026-01.md", "runbook"),
    ("rfcs/0001-changelog-format.md", "design"),   # a directory beats the stem
    ("docs/adr/0002-use-sqlite.md", "design"),
    ("docs/adr0003.md", "design"),
    ("docs/architecture-decisions/adr-004.md", "design"),
    ("website/blog/2026-11-02-release.md", "blog"),
    ("docs/tutorials/api.md", "tutorial"),         # outermost directory first
    ("docs/reference/tutorial.md", "reference"),
    ("docs/tasks/configure.md", "tutorial"),
    ("docs/getting-started.md", "tutorial"),
    ("docs/install-guide.md", "tutorial"),
    ("docs/man/git-log.1.md", "reference"),
    ("doc/tool.8.rst", "reference"),
    ("docs/api-keys.md", "reference"),
    ("docs/concepts/scheduling.md", "explanation"),
    ("docs/architecture.md", "explanation"),
    ("docs/faq.md", None),
    ("docs/index.md", None),
])
def test_kind_rule(path, kind):
    assert kp.kind_of_path(path) == kind


@pytest.mark.parametrize("path,ok", [
    ("docs/guide.md", True), ("docs/guide.rst", True), ("docs/guide.mdx", True), ("docs/guide.txt", False),
    ("README.md", False), ("docs/Readme.md", False), ("SECURITY.md", False), ("node_modules/x/guide.md", False),
    (".github/ISSUE_TEMPLATE/bug.md", False), ("CHANGELOG.md", True),
])
def test_doc_file(path, ok):
    assert kp.doc_file(path) is ok


def test_eligible_paths_by_source():
    tree = ["README.md", "CHANGELOG.md", "docs/tutorials/a.md", "docs/faq.md", "src/x.go", "src/x_test.go",
            "tests/y.py", "src/z.min.js", "content/en/blog/p.md", "content/zh/blog/p.md", "proposals/0001-x.md",
            "draft-ietf-foo-bar.md", "Policies/terms.md", ".github/x.md", "ops/runbooks/r.md"]
    walk = kp.eligible_paths(tree, "walk")
    assert walk["changelog"] == ["CHANGELOG.md"] and walk["tutorial"] == ["docs/tutorials/a.md"]
    assert walk["code-doc"] == walk["code-ordinary"] == ["src/x.go", "src/x_test.go"]
    assert "docs/faq.md" not in sum(walk.values(), [])
    k8s = kp.eligible_paths(tree, "named", "kubernetes/website")
    assert k8s == {"blog": ["content/en/blog/p.md"]}
    assert kp.eligible_paths(tree, "named", "kotlin/keep") == {"design": ["proposals/0001-x.md"]}
    assert kp.eligible_paths(tree, "standards") == {"standards": ["draft-ietf-foo-bar.md"]}
    assert "Policies/terms.md" in kp.eligible_paths(tree, "contrast")["contrast"]
    assert ".github/x.md" not in kp.eligible_paths(tree, "contrast")["contrast"]
    cs = kp.eligible_paths(tree, "codesearch", search_paths=["ops/runbooks/r.md", "docs/faq.md", "gone.md"])
    assert cs == {"runbook": ["ops/runbooks/r.md"]}
    assert kp.files_per("tutorial", "walk") == 2 and kp.files_per("tutorial", "named") == 30
    assert kp.files_per("code-doc", "walk") == 3 and kp.files_per("standards", "standards") == 1


def test_truncate_changelog_cuts_at_a_line():
    data = b"".join(f"- entry {k}\n".encode() for k in range(30000))
    cut, did = kp.truncate_changelog(data, 1000)
    assert did and len(cut) <= 1000 and cut.endswith(b"\n") and data.startswith(cut)
    assert kp.truncate_changelog(b"short\n", 1000) == (b"short\n", False)


def test_normalize_catches_round_twos_duplicate():
    assert kp.normalize("// The cache, that we keep.") == kp.normalize("The cache that we keep") == \
        "the cache that we keep"


GO = """package x

// Reader reads the table that the writer leaves behind.
func Reader() {}

func f() {
	// the loop below skips the rows that the filter drops
	for {}
}

/** Block docs of a kind Go does not use. */
/* A plain block comment. */
"""

PY = '''"""Module docstring that the reader sees first."""

def f():
    """Function docstring."""
    # an ordinary comment that explains the loop
    return 1
'''

RS = """//! Crate docs.
/// Item docs.
fn f() {
    // ordinary comment
}
"""

RB = """# Documents the method below.
def m
  # explains a step
end
"""


def _at(text, needle):
    return text.index(needle)


def test_comment_class():
    go = kp.CommentClass(GO, "x.go")
    assert go(_at(GO, "Reader reads")) == "doc"
    assert go(_at(GO, "the loop below")) == "ordinary"
    assert go(_at(GO, "Block docs")) == "doc" and go(_at(GO, "A plain")) == "ordinary"
    py = kp.CommentClass(PY, "x.py")
    assert py(_at(PY, "Module docstring")) == py(_at(PY, "Function docstring")) == "doc"
    assert py(_at(PY, "an ordinary")) == "ordinary"
    rs = kp.CommentClass(RS, "x.rs")
    assert rs(_at(RS, "Crate docs")) == rs(_at(RS, "Item docs")) == "doc"
    assert rs(_at(RS, "ordinary comment")) == "ordinary"
    rb = kp.CommentClass(RB, "x.rb")
    assert rb(_at(RB, "Documents")) == "doc" and rb(_at(RB, "explains")) == "ordinary"
    js = "// a note\nconst x = 1;\n/** JSDoc */\nfunction f() {}\n"
    c = kp.CommentClass(js, "x.ts")
    assert c(_at(js, "a note")) == "ordinary" and c(_at(js, "JSDoc")) == "doc"
    sh = "# a shell comment\n"
    assert kp.CommentClass(sh, "x.sh")(2) == "ordinary"


def test_kind_labels():
    assert kp.kind_label("changelog", "CHANGELOG.md") == "changelog or release notes"
    assert kp.kind_label("code-doc", "a.py") == "Python docstring"
    assert kp.kind_label("code-doc", "a.go") == "doc comment in Go source"
    assert kp.kind_label("code-ordinary", "a.rs") == "ordinary comment in Rust source (not a doc comment)"


def test_zscores_and_ranked_picks():
    assert kp.zscores([3, 3, 3]) == [0.0, 0.0, 0.0]
    z = kp.zscores([1, 2, 3])
    assert abs(sum(z)) < 1e-9 and z[0] < 0 < z[2]
    sents = [{"words": 10, "arc": 2, "depth": 0}, {"words": 30, "arc": 3, "depth": 0},
             {"words": 20, "arc": 12, "depth": 2}, {"words": 30, "arc": 3, "depth": 0}]
    picks = kp.ranked_picks(sents, [0, 0, 1, 0], random.Random(1))
    assert picks["longest"] == 1           # ties go to the first
    assert picks["composite"] == 2         # long arc, deep embedding and a finding
    assert 0 <= picks["random"] < 4
    assert kp.ranked_picks(sents, [0, 0, 0, 5], random.Random(1))["composite"] == 3


def test_arc_words_and_check_text_on_made_up_text():
    an = kp.analyzer()
    doc = an.nlp("The cache that the parser keeps grows.")
    sent = next(doc.sents)
    assert kp.arc_words(sent) >= 4  # "cache" to "grows" spans the relative clause
    text = ("The service reads the configuration file and writes the results to the output folder "
            "before it exits.\n\n" * 12)
    rec = {"stratum": "tutorial", "repo": "a/b", "commit": "c", "path": "docs/tutorials/x.md", "blob": "x",
           "source": "walk"}
    out = kp.check_text(an, text, rec)
    assert not out.get("drop")
    assert out["all_sentences"] and all({"words", "arc", "depth", "sentence"} <= set(s) for s in out["all_sentences"])
    assert len(out["sentences"]) <= len(out["all_sentences"])


def test_check_text_splits_comment_classes():
    src = "\n".join(
        f"/// The function that the reader calls returns the value number {k} of the table.\n"
        f"fn f{k}() {{\n    // The loop that the caller starts reads the row number {k} of the file.\n    g();\n}}"
        for k in range(6))
    rec = {"repo": "a/b", "commit": "c", "path": "src/lib.rs", "blob": "x", "source": "walk"}
    doc = kp.check_text(kp.analyzer("doc"), src, rec | {"stratum": "code-doc"})
    ordinary = kp.check_text(kp.analyzer("all"), src, rec | {"stratum": "code-ordinary"})
    assert all("function" in s["sentence"] for s in doc["all_sentences"])
    assert ordinary["all_sentences"] and all("loop" in s["sentence"] for s in ordinary["all_sentences"])
    for f in doc["findings"] + ordinary["findings"]:
        assert src[f["start"]:f["end"]]


def _f(rule, start, sentence, key, repo="o/r", path="docs/tutorials/x.md", source="walk"):
    return {"rule": rule, "start": start, "end": start + 5, "sentence_start": start, "sentence_end": start + 9,
            "sentence": sentence, "message": "m", "excerpt": "e", "key": key, "repo": repo, "path": path,
            "source": source}


def test_capped_draw_rejects_keys_and_sentences_seen():
    items = [_f("stacked-nouns", 0, "A b c.", "k1"), _f("stacked-nouns", 0, "A b c.", "k1"),   # one key twice
             _f("stacked-nouns", 10, "// a, b c", "k2"), _f("stacked-nouns", 20, "Other.", "k3")]
    keys, norm = set(), set()
    got = kp.capped_draw(items, 10, "s", keys, norm)
    assert sorted(x["key"] for x in got) in (["k1", "k3"], ["k2", "k3"])
    assert kp.capped_draw(items, 10, "s", keys, norm) == []  # nothing again in a later stratum


def test_caps_for_named_sources_and_contrast():
    named = [_f("stacked-nouns", k, f"s{k}", f"n{k}", repo="github/docs", path=f"content/d{k % 3}/f{k}.md",
                source="named") for k in range(20)]
    got = kp.capped_draw(named, 12, "s", set(), set())
    assert len(got) == 4  # at most 4 from one named source
    dirs = [str(Path(x["path"]).parent) for x in got]
    assert max(dirs.count(d) for d in dirs) <= 2
    contrast = [_f("stacked-nouns", k, f"c{k}", f"c{k}", repo="github/site-policy", path=f"P/f{k % 5}.md",
                   source="contrast") for k in range(30)]
    got = kp.capped_draw(contrast, 12, "s", set(), set())
    assert len(got) == 10  # two per file, five files
    walk = [_f("stacked-nouns", k, f"w{k}", f"w{k}", repo=f"o/r{k % 3}") for k in range(30)]
    assert len(kp.capped_draw(walk, 12, "s", set(), set())) == 6


def _kept(stratum, repo, n_find, n_near, n_sent, source="walk", path="docs/tutorials/x.md"):
    findings = [_f("stacked-nouns", 10 * k, f"{repo} {path} f{k}", f"{stratum}{repo}{path}f{k}", repo, path, source)
                for k in range(n_find)]
    for f in findings:
        f["sentence_end"] = f["start"] + 9
    near = [_f("stacked-nouns", 500 + 10 * k, f"{repo} {path} n{k}", f"{stratum}{repo}{path}n{k}", repo, path,
               source) for k in range(n_near)]
    sents = [{"start": 1000 + 20 * k, "end": 1019 + 20 * k, "words": 6 + k, "sentence": f"{repo} {path} s{k}"}
             for k in range(n_sent)]
    alls = [s | {"arc": k % 3, "depth": 0} for k, s in enumerate(sents)]
    return {"stratum": stratum, "repo": repo, "commit": "c", "path": path, "blob": "b", "source": source,
            "findings": findings, "near": near, "sentences": sents, "all_sentences": alls}


def _tokens(rec, start, end):
    words = [("cache", "NOUN"), ("stores", "VERB"), ("the", "DET"), ("plan", "NOUN"), ("today", "NOUN")]
    out, pos = [], start
    for w, p in words:
        out.append([w, p, True, pos, pos + len(w)])
        pos += len(w) + 1
    return out


def test_draw_stratum_quotas_decoys_and_ranked():
    kept = [_kept("tutorial", f"o/r{k}", 5, 5, 6) for k in range(25)]
    items, counts = kp.draw_stratum("tutorial", kept, _tokens, set(), set(), set())
    by = {k: [x for x in items if x["item"] == k] for k in ("finding", "near", "decoy", "ranked")}
    assert len(by["finding"]) == 12 and len(by["near"]) == 4 and len(by["decoy"]) == 16
    assert len({x["repo"] for x in by["decoy"]}) == 16
    assert counts["ranked_docs"] == min(20, len({x["doc"] for x in items if x["item"] != "ranked"}))
    ranks = sorted(r for x in by["ranked"] for r in x["ranks"])
    assert ranks.count("longest") == ranks.count("composite") == ranks.count("random") == counts["ranked_docs"]
    assert all(x["excerpt"] == x["sentence"] and x["rule"] == "" for x in by["ranked"])
    assert len({x["key"] for x in items}) == len(items)
    again, _ = kp.draw_stratum("tutorial", list(reversed(kept)), _tokens, set(), set(), set())
    assert [x["key"] for x in again] == [x["key"] for x in items]


def test_ranked_skips_short_documents_and_repeats_of_a_repository():
    kept = [_kept("blog", "o/a", 1, 0, 3), _kept("blog", "o/b", 1, 0, 6),
            _kept("blog", "o/b", 1, 0, 6, path="blog/y.md")]
    items, counts = kp.draw_stratum("blog", kept, _tokens, set(), set(), set())
    assert counts["ranked_docs"] == 1


def test_build_sample_no_item_twice_and_views():
    kept = [_kept("tutorial", f"o/r{k}", 2, 2, 6) for k in range(4)]
    # the same sentences again in another stratum: rejected there
    kept += [_kept("changelog", f"o/r{k}", 2, 2, 6) | {"stratum": "changelog"} for k in range(4)]
    sources = {(c["repo"], c["path"]): "x" * 3000 for c in kept}
    sample, counts = kp.build_sample(kept, sources, _tokens)
    assert counts["changelog"]["sampled"]["stacked-nouns"] == 0
    assert len({x["i"] for x in sample}) == len(sample) == len({x["key"] for x in sample})
    primed = kp.primed_items(sample)
    assert len(primed) == sum(1 for x in sample if x["item"] != "ranked")
    assert len(kp.blind_items(sample)) == len(sample)
    for x in sample:
        assert set(kp.POINTER_FIELDS) <= set(x)
        assert x["kind"] == kp.KIND[x["stratum"]]
    json.dumps([{k: x[k] for k in kp.POINTER_FIELDS} for x in sample])


PRIMED = f"""Rubric

Two rules the list above does not define.

{kp.bp.KIND_LINE}

Reply format
"""

BLIND = f"""Rubric (unprimed protocol)

Each item is one sentence from a software
project's text {kp.BLIND_SOURCE_OLD}, with a few marked words.

{kp.bp.KIND_LINE}

Reply format
"""


def test_rubrics_change_only_the_kind():
    p = kp.rubric_primed(PRIMED)
    assert kp.KIND_LINE in p and p.replace(kp.KIND_LINE, kp.bp.KIND_LINE) == PRIMED
    b = kp.rubric_blind(BLIND)
    assert kp.KIND_LINE in b and kp.BLIND_SOURCE_NEW in b
    assert b.replace(kp.KIND_LINE, kp.bp.KIND_LINE).replace(kp.BLIND_SOURCE_NEW, kp.BLIND_SOURCE_OLD) == BLIND


def test_rater_seeds_and_batches():
    assert kp.RATER_SEEDS["rater1"] == 7001 and kp.BLIND_SEEDS["blind3"] == 8003
    items = [{"i": 100000 + k} for k in range(120)]
    orders = {tuple(x["i"] for b in kp.hp.batches(items, s) for x in b) for s in
              [*kp.RATER_SEEDS.values(), *kp.BLIND_SEEDS.values()]}
    assert len(orders) == 15


def test_walk_and_tsv(tmp_path):
    cands = [{"repo": f"o{k % 7}/r{k}", "population": "ab"[k % 2], "language": "", "stars": 300,
              "created_at": "2020", "default_branch": "main", "fork": k == 4, "archived": False, "license": "MIT"}
             for k in range(40)]
    picked, drops = kp.walk(cands, {"o1/r1"}, {"o2/r2"})
    assert all(c["repo"] not in ("o1/r1", "o2/r2", "o4/r4") for c in picked)
    owners = [c["repo"].split("/")[0] for c in picked]
    assert max(owners.count(o) for o in owners) <= 2
    assert drops["b: in a development corpus"] == 1 and drops["a: named source"] == 1
    kp.write_tsv(tmp_path / "c.tsv", cands)
    back = kp.read_tsv(tmp_path / "c.tsv")
    assert sorted(back, key=lambda r: r["repo"]) == sorted(cands, key=lambda r: r["repo"])
