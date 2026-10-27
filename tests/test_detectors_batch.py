"""Detector precision fixes, bug-hunt rows, opt-in detectors and rationale-keeping suggestions."""

import pytest

from readcost import Analyzer, Config
from readcost.features import FEATURES


@pytest.fixture(scope="module")
def analyzer():
    return Analyzer(Config())


@pytest.fixture(scope="module")
def full():
    return Analyzer(Config(enable=["nominalization", "participial-clause", "repeated-frame"]))


def found(a, text, feature=None):
    fs = a.check_text(text, "markdown").findings
    return [f for f in fs if feature is None or f.feature == feature]


# ---------------------------------------------------------------- false positives

@pytest.mark.parametrize("text", [
    "The bench command prints how long the first search takes on each corpus.",
    "Running readcost explain prints why each one costs the reader time.",
    "The log shows what the first request returned to the client.",
])
def test_embedded_questions_are_not_object_relatives(analyzer, text):
    assert found(analyzer, text, "reduced-object-relative") == []


def test_real_object_relative_is_still_flagged(analyzer):
    assert found(analyzer, "It writes the output in the format the reader expects.", "reduced-object-relative")
    assert found(analyzer, "Keep the reason why the cache exists next to the code.", "reduced-object-relative") == []


def test_verb_misread_as_plural_noun_does_not_close_a_stack(analyzer):
    # "prints" is the verb; the parser makes it the head of "bench command prints".
    assert found(analyzer, "The bench command prints how long the first search takes on each corpus.",
                 "stacked-nouns") == []


def test_sentence_initial_imperative_is_not_a_stacked_noun(analyzer):
    assert found(analyzer, "Flag prose constructions that slow readers down in technical docs.", "stacked-nouns") == []
    # A real stack at the start of a sentence with its own verb is still found.
    assert found(analyzer, "Source segment rebuilds happen at every restart of the store.", "stacked-nouns")


@pytest.mark.parametrize("text", [
    "Install the tree-sitter grammars before you build the parser here.",
    "The extractor depends on markdown-it-py and two of its plugins today.",
])
def test_hyphenated_tool_names_are_not_flagged(analyzer, text):
    assert [f.feature for f in found(analyzer, text)] == []


def test_hyphenated_package_name_counts_as_one_unit(analyzer):
    assert found(analyzer, "Update the py-spy profiler binary before every release.") == []
    # A coined hyphenated compound is still part of a stack.
    assert found(analyzer, "The old region-shard segment files are rebuilt when the store starts.", "stacked-nouns")


def test_excerpt_and_sentence_show_the_original_code(analyzer):
    # long-dependency reports subject and object gaps, so the code span is the subject here.
    fs = found(analyzer, "`NO_COLOR`, which every terminal library on the system reads when it starts and again "
                         "on each redraw, controls colors.", "long-dependency")
    assert fs
    assert "`NO_COLOR`" in fs[0].excerpt and "`NO_COLOR`" in fs[0].sentence
    assert "Xcode" not in fs[0].excerpt + fs[0].sentence


def test_message_names_the_code_span(analyzer):
    fs = found(analyzer, "This is the struct `Builder` creates for each new index.", "reduced-object-relative")
    assert fs
    assert fs[0].message.startswith("'struct `Builder` creates'")
    assert fs[0].excerpt == "struct `Builder` creates"


def test_literal_xcode_in_prose_is_left_alone(analyzer):
    fs = found(analyzer, "Xcode, which every developer on the team installs once and updates whenever a release "
                         "ships, sets the colors.", "long-dependency")
    assert fs and "Xcode" in fs[0].sentence


def test_url_and_path_placeholders_map_back():
    from readcost.extract import CODE, extract_markdown

    seg = extract_markdown("See https://example.com/a_(b) and src/readcost/data/x.json. "
                           "Then run `make` and $x^2$ today.\n", "t.md")[0]
    assert sorted(seg.codes.values()) == sorted(
        ["https://example.com/a_(b)", "src/readcost/data/x.json", "`make`", "$x^2$"])
    assert all(seg.text[k:k + len(CODE)] == CODE for k in seg.codes)


# ---------------------------------------------------------------- bug-hunt rows

def test_dependency_distance_skips_punctuation(analyzer):
    from readcost.features import dependency_arcs

    doc = analyzer.nlp("The region-shard-segment file is rebuilt on start.")
    arcs = {dep.text: dist for dist, dep, head in dependency_arcs(next(doc.sents))}
    # "region" attaches to "shard": one word away, though two tokens away.
    assert arcs["region"] == 1
    assert arcs["shard"] == 1


def test_dependency_arcs_skip_the_root(analyzer):
    from readcost.features import dependency_arcs

    doc = analyzer.nlp("The parser reads the file once.")
    sent = next(doc.sents)
    deps = [dep.i for _, dep, _ in dependency_arcs(sent)]
    assert sent.root.i not in deps
    assert all(dist > 0 for dist, _, _ in dependency_arcs(sent))


def test_disabling_inline_list_does_not_create_long_dependency():
    text = "In non-Windows environments, if the json/yaml/toml loader is not set, then colors will be suppressed."
    on = Analyzer(Config())
    off = Analyzer(Config(disable=["inline-list"]))
    assert [f.feature for f in found(off, text, "long-dependency")] == \
           [f.feature for f in found(on, text, "long-dependency")]


def test_readme_inline_list_example_counts_once(analyzer):
    fs = found(analyzer, "It supports standard/Sugeno/Yager negations, OWA, power means, and uninorms.", "inline-list")
    assert len(fs) == 1


def test_slash_list_alone_is_still_reported(analyzer):
    assert found(analyzer, "It supports standard/Sugeno/Yager negations for every operator.", "inline-list")


def test_mean_dep_z_is_none_when_long_dependency_is_off():
    r = Analyzer(Config(disable=["long-dependency"])).check_text("The parser reads the file once per run.")
    assert r.mean_dep_z is None
    assert r.to_dict()["mean_dep_z"] is None


def test_mean_dep_z_is_a_number_when_on(analyzer):
    assert isinstance(analyzer.check_text("The parser reads the file once per run.").mean_dep_z, float)


def test_all_caps_prose_still_gets_stacked_nouns(analyzer):
    assert found(analyzer, "THE INDEX STORAGE BUFFER POOL IS REBUILT AT EVERY START OF THE SERVER.", "stacked-nouns")
    # Names in ordinary sentences are still skipped.
    assert found(analyzer, "We ran the benchmark on an Apple M3 Max laptop yesterday.", "stacked-nouns") == []


def test_stacked_noun_severity_counts_allowed_units():
    a = Analyzer(Config(allow=["sidecar cache"]))
    fs = found(a, "The region index sidecar cache file grows after every restart.", "stacked-nouns")
    assert fs and fs[0].severity == "warn"
    assert fs[0].message.startswith("4 ")


# ---------------------------------------------------------------- opt-in detectors

def test_new_detectors_are_off_by_default(analyzer):
    text = "The tool performs validation of the input, making the conversion of the records safer."
    assert {f.feature for f in found(analyzer, text)} & {"nominalization", "participial-clause"} == set()


def test_nominalization_after_light_verb(full):
    fs = found(full, "The tool performs validation of the input before it writes anything.", "nominalization")
    assert fs and "validate" in fs[0].message


def test_two_nominalizations_with_of_in_one_sentence(full):
    assert found(full, "The conversion of the records happens after the validation of the schema.", "nominalization")


@pytest.mark.parametrize("text", [
    "The tool validates the input before it writes anything.",
    "The implementation of the parser lives in one file.",
    "See the documentation for every configuration option.",
    "The community of maintainers reviews each position in the roadmap.",
])
def test_nominalization_negatives(full, text):
    assert found(full, text, "nominalization") == []


@pytest.mark.parametrize("text", [
    "The parser caches every token, making repeated lookups much faster.",
    "Building on this design, the index stores each segment in its own file.",
    "The hook runs after every edit, ensuring that the docs stay readable.",
])
def test_participial_clause_positives(full, text):
    assert found(full, text, "participial-clause")


@pytest.mark.parametrize("text", [
    "While parsing the file, the tool records each error it sees.",
    "The parser makes repeated lookups faster by caching every token.",
    "The running process holds the lock until it exits.",
    "Running the tests takes about thirty seconds on a laptop.",
    "The parser caches every token so that repeated lookups are faster.",
])
def test_participial_clause_negatives(full, text):
    assert found(full, text, "participial-clause") == []


def test_repeated_frame_in_one_document(full):
    text = ("This approach reduces the latency of every request. "
            "This change improves the speed of every query. "
            "This design lowers the cost of every lookup.")
    fs = found(full, text, "repeated-frame")
    assert len(fs) == 1
    assert "3 sentences" in fs[0].message


def test_varied_sentences_have_no_frame(full):
    text = ("The index stores one list of documents for each term. "
            "You can search it from several threads at once. "
            "When a segment fills up, the writer starts a new one and merges old ones in the background. "
            "Queries never wait for a merge.")
    assert found(full, text, "repeated-frame") == []


def test_two_repeats_are_not_a_frame(full):
    text = ("This approach reduces the latency of every request. "
            "This change improves the speed of every query. "
            "Nothing else changed in the release.")
    assert found(full, text, "repeated-frame") == []


# ---------------------------------------------------------------- rationale-keeping suggestions

def test_inline_list_suggestion_keeps_the_reason(analyzer):
    fs = found(analyzer, "It supports negations from three families, implications defined by residuation, ordered weighted averages, and uninorms with any neutral element, "
                         "because fuzzy logic needs all of them.", "inline-list")
    assert fs
    s = fs[0].suggestion.lower()
    assert "split" in s and "because" in s and "keep" in s


def test_long_dependency_suggestion_keeps_the_reason(analyzer):
    fs = found(analyzer, "The index, which every query reads since it must see the latest writes and no reader "
                         "may block a writer, serves all lookups.", "long-dependency")
    assert fs
    assert "since" in fs[0].suggestion and "keep" in fs[0].suggestion.lower()


def test_suggestion_without_a_reason_is_the_plain_fix(analyzer):
    fs = found(analyzer, "It supports negations from three families, implications defined by residuation, ordered weighted averages, and uninorms with any neutral element.", "inline-list")
    assert fs and fs[0].suggestion == "Use a bulleted list."


def test_list_items_do_not_form_a_frame(full):
    text = ("- This approach reduces the latency of every request.\n"
            "- This change improves the speed of every query.\n"
            "- This design lowers the cost of every lookup.\n")
    assert found(full, text, "repeated-frame") == []


# ---------------------------------------------------------------- lexicon data

@pytest.fixture
def fake_lexicon(monkeypatch):
    from readcost import lexicon

    def install(raw: bytes):
        class File:
            def joinpath(self, _):
                return self

            def read_bytes(self):
                return raw

        monkeypatch.setattr(lexicon.resources, "files", lambda _: File())
        monkeypatch.setattr(lexicon, "_LEX", None)
        lexicon.noun_animacy.cache_clear()
        lexicon._nominalizations.cache_clear()
    yield install
    lexicon.noun_animacy.cache_clear()
    lexicon._nominalizations.cache_clear()


def test_truncated_lexicon_counts_as_missing(fake_lexicon):
    import gzip
    import json

    from readcost import lexicon

    raw = gzip.compress(json.dumps({"animate_nouns": ["person"]}).encode())
    fake_lexicon(raw[:len(raw) // 2])
    assert lexicon.has_wordnet() is False
    assert lexicon.noun_animacy("table") is None


def test_lexicon_without_animate_nouns_does_not_raise(fake_lexicon):
    import gzip
    import json

    from readcost import lexicon

    fake_lexicon(gzip.compress(json.dumps({"animate_verbs": ["eat"]}).encode()))
    assert lexicon.has_wordnet() is True
    assert lexicon.noun_animacy("table") is None
    assert lexicon.noun_animacy("user") is True


# ---------------------------------------------------------------- guards seen on human READMEs

def test_participle_after_a_subordinator_is_not_flagged(full):
    assert found(full, "This might come up when, for example, reading a file one line at a time.",
                 "participial-clause") == []


def test_participle_inside_a_list_is_not_flagged(full):
    assert found(full, "Use it if you like speed, filtering by default, and fewer bugs.", "participial-clause") == []
    assert found(full, "In short, pick it for speed, filtering by default, fewer bugs and Unicode support.",
                 "participial-clause") == []
    assert found(full, "Comes with support for following links, controlling the number of open files.",
                 "participial-clause") == []


def test_nominalization_naming_a_thing_is_not_flagged(full):
    assert found(full, "This crate provides a fast implementation of ordered sets and maps.", "nominalization") == []
    assert found(full, "The crate provides implementations of the trait for every map.", "nominalization") == []


def test_colon_lead_ins_do_not_form_a_frame(full):
    text = ("If you are a Homebrew user, then you can install the tool from the main tap:\n\n    brew install x\n\n"
            "If you are a MacPorts user, then you can install the tool from the main ports:\n\n    port install x\n\n"
            "If you are a Windows user, then you can install the tool from the main bucket:\n\n    scoop install x\n")
    assert found(full, text, "repeated-frame") == []


# ---------------------------------------------------------------- profile fit

def test_profile_built_from_a_document_scores_it_at_mean_z_zero(tmp_path):
    # build_profile must fit the arcs dependency_z scores with. A least-squares
    # fit has zero mean residual on its own points, so scoring the same text
    # against its own profile gives mean z near 0; fitting with other arcs
    # (punctuation counted, root arc kept) shifts every z.
    from readcost.profile import Profile, build_profile

    doc = tmp_path / "ref.md"
    doc.write_text(
        "The \"region-shard-segment\" index, built once at startup, answers lookups quickly.\n\n"
        "Each worker reads the queue, checks the lease, and writes the result back.\n\n"
        "When a request arrives (from any client), the router picks a shard by hash.\n\n"
        "The cache keeps recent pages; older pages go to disk, where the compactor merges them.\n\n"
        "Users who run the tool on large trees should raise the open-file limit first.\n\n"
        "A short note: the parser skips comments, blank lines, and trailing whitespace.\n\n"
        "The build script, which runs in CI, downloads the model and caches it.\n\n"
        "If the lock is held, the second process waits; it never steals the lock.\n\n"
        "Our \"fast path\" covers ASCII input, which is most input in practice.\n\n"
        "The exporter writes one file per day, named by date, into the archive.\n\n"
        "Tests that touch the network are skipped unless the flag is set.\n\n"
        "The old format, still read for compatibility, is never written again.\n"
    )
    placeholder = Profile("placeholder", 0, 0, (0.0, 0.78, 0.42))
    prof = build_profile([str(doc)], "self", lambda: Analyzer(Config(), profile=placeholder))
    result = Analyzer(Config(), profile=prof).check_file(str(doc))
    assert result.mean_dep_z is not None
    assert abs(result.mean_dep_z) < 0.05


# ---------------------------------------------------------------- README table

def _readme_rows():
    import re
    from pathlib import Path

    readme = Path(__file__).resolve().parent.parent / "README.md"
    for line in readme.read_text().splitlines():
        m = re.match(r"\| ([a-z-]+)((?: \([^)]*\))?) \| (.+?) \| .+ \|$", line)
        if m and m.group(1) in FEATURES:  # skips other tables, such as the tool comparison
            yield m.group(1), m.group(2), m.group(3)


@pytest.mark.parametrize("feature,note,example", list(_readme_rows()))
def test_readme_examples_trigger_their_detector(feature, note, example):
    # The "What it flags" table is the public claim; each example must fire
    # the detector it illustrates under the configuration its note names.
    cfg = Config()
    if "opt-in" in note:
        cfg.rules[feature] = "info"
    if "stacked-nouns off" in note:
        cfg.rules["stacked-nouns"] = "ignore"
    example = example.strip('"')  # example text is quoted in the table
    # Phrases in the table are not sentences; put them in one.
    text = example if example.endswith(".") else f"The fix keeps {example} in the module."
    assert feature in {f.feature for f in Analyzer(cfg).check_text(text, "markdown").findings}


@pytest.mark.parametrize("sentence", [
    # Shaped like labelled findings the eight-rater majority rejected
    # (docs/evaluation.md): a fronted connective, or a
    # clause-to-clause arc, rather than a subject or object far from its verb.
    "Likewise, if some other process opens the log file and writes junk into the middle of it, "
    "then the log might become unreadable.",
])
def test_long_dependency_ignores_connectives_and_clause_links(analyzer, sentence):
    assert not found(analyzer, sentence, "long-dependency")


def test_long_dependency_reports_the_subject_and_its_verb(analyzer):
    fs = found(analyzer, "The index, which is built once from every document in the corpus at startup and then "
                         "rebuilt only when the compactor runs, serves all queries.", "long-dependency")
    assert [f.message.split(" are ")[0] for f in fs] == ["'index' and 'serves'"]
