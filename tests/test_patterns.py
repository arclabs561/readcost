"""The experimental discourse measures (patterns.py) and scripts/eval_patterns.py.

Every sentence and record here is made up; no third-party data is read.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from readcost import Analyzer, Config, patterns

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


@pytest.fixture(scope="module")
def nlp():
    return Analyzer(Config()).nlp


@pytest.fixture(scope="module")
def ev():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("eval_patterns", SCRIPTS / "eval_patterns.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def hits(nlp, text):
    return [(h.pattern, h.kind, text[h.start:h.end]) for h in patterns.measure(nlp, [text]).hits]


# ---------------------------------------------------------------- contrast

@pytest.mark.parametrize("text,kind", [
    ("The cache is not a database but a hint.", "not-but"),
    ("Not only the tests but also the docs changed.", "not-but"),
    ("We ship a feature, not a promise.", "comma-not"),
    ("The tool edits files rather than printing them.", "rather-than"),
    ("It's not a bug. It's a feature.", "setup-resolution"),
    ("This isn't about speed; it's about trust.", "setup-resolution"),
])
def test_contrast_shapes(nlp, text, kind):
    assert [(p, k) for p, k, _ in hits(nlp, text)] == [("contrast", kind)]


@pytest.mark.parametrize("text", [
    "I did not go, but he went anyway.",          # two clauses, nothing corrected
    "The parser is not slow at all.",
    "The build did not finish. The disk was full.",
    "She would rather wait.",
    "It is not ready. We will ship it next week.",
])
def test_plain_negation_is_not_contrast(nlp, text):
    assert not [h for h in hits(nlp, text) if h[0] == "contrast"]


# ------------------------------------------------------------------ series

def test_series_of_three_is_a_triple(nlp):
    report = patterns.measure(nlp, ["The design is fast, simple and safe. It needs time, money, and patience."])
    assert report.count("triple") == 2
    assert report.lists == 2


def test_longer_series_is_a_list_but_not_a_triple(nlp):
    report = patterns.measure(nlp, ["We support Linux, macOS, Windows and BSD."])
    assert report.count("triple") == 0
    assert report.lists == 1


@pytest.mark.parametrize("text", [
    "After lunch, Alice and Bob left.",
    "If it fails, retry and log the error.",
    "Alice and Bob left.",
])
def test_pairs_and_fronted_phrases_are_not_series(nlp, text):
    report = patterns.measure(nlp, [text])
    assert report.lists == 0


# ---------------------------------------------------------- anticipatory it

@pytest.mark.parametrize("text", [
    "It is important to note that the cache expires.",
    "It's worth noting that nothing is free.",
    "It should be noted that the index is stale.",
    "It is clear that the test fails.",
])
def test_anticipatory_it(nlp, text):
    assert [p for p, _, _ in hits(nlp, text)] == ["anticipatory-it"]


@pytest.mark.parametrize("text", [
    "It is a small tool that works.",
    "It was raining when the job started.",
    "It runs the tests that changed.",
])
def test_referring_it_is_not_a_frame(nlp, text):
    assert not hits(nlp, text)


# ------------------------------------------------- restatement and measures

def test_restatement_needs_an_earlier_sentence_with_the_same_content(nlp):
    text = ("The scheduler assigns each job to a worker queue. Logs go to the disk. "
            "Each job is assigned to a worker queue by the scheduler.")
    found = [h for h in hits(nlp, text) if h[0] == "restatement"]
    assert len(found) == 1 and found[0][2].startswith("Each job")
    assert not [h for h in hits(nlp, "The scheduler assigns each job to a queue. Logs go to the disk.")
                if h[0] == "restatement"]


def test_uniform_sentences_have_a_lower_spread(nlp):
    uniform = " ".join(["The service reads the next row.", "The worker checks the old file.",
                        "The client sends the new key.", "The server stores the last page.",
                        "The script prints the first line."])
    varied = ("The job stops. The service reads the next row from the queue and then waits for the lock to "
              "clear. It retries once. The worker checks the old file. When the client sends the new key, "
              "the server stores it with the last page and the script prints one line.")
    a = patterns.measure(nlp, [uniform]).measures
    b = patterns.measure(nlp, [varied]).measures
    assert a["sentence_cv"] < 0.1 < b["sentence_cv"]
    assert a["opener_share"] is None and patterns.measure(nlp, [uniform + " The job ends."]).measures["opener_share"] == 1.0


def test_repeating_a_text_raises_given_rate_overlap_and_compression(nlp):
    base = ("The scheduler assigns each job to a worker queue. A worker pulls the oldest job and runs it in a "
            "sandbox. Results go to the object store. Failures are retried twice before the job is marked dead. "
            "Operators read the dead list every morning and decide what to requeue.")
    other = ("Billing closes the ledger at midnight. Invoices render from a template that finance owns. "
             "Tax tables load once a quarter. Refunds need a second approver above a set amount. "
             "Auditors export the journal as a signed archive.")
    once = patterns.measure(nlp, [base, other] * 2).measures
    padded = patterns.measure(nlp, [base] * 4).measures
    assert padded["given_rate"] > once["given_rate"] - 1e-9
    assert padded["gzip_ratio"] > once["gzip_ratio"]
    assert patterns.measure(nlp, [base]).measures["gzip_ratio"] is None   # under the fixed window


def test_short_or_empty_text(nlp):
    report = patterns.measure(nlp, ["", "Fine."])
    assert report.words == 0 and report.hits == [] and report.per_1000("contrast") == 0.0
    assert report.to_dict()["sentence_cv"] is None


# ----------------------------------------------------------------- not wired

def test_nothing_in_readcost_imports_patterns():
    """The module is an experiment: no rule, metric or command may depend on it."""
    code = ("import sys, readcost, readcost.cli, readcost.engine, readcost.report, readcost.corpus; "
            "from readcost import check_text; r = check_text('It is not a bug. It is a feature.'); "
            "print('readcost.patterns' in sys.modules, sorted(r.metrics))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.startswith("False")
    for key in patterns.PATTERNS:
        assert key not in out
    for src in (ROOT / "src" / "readcost").glob("*.py"):
        if src.name != "patterns.py":
            assert "patterns" not in src.read_text(), src.name


def test_default_rules_do_not_report_the_patterns():
    text = "It is important to note that this is not a bug but a feature, fast, simple and safe."
    found = {f.feature for f in Analyzer(Config()).check_text(text, "text").findings}
    assert not found & set(patterns.PATTERNS)


# -------------------------------------------------------------- the script

def test_paired_difference_and_direction(ev):
    human = [{"x": 0.0}] * 30 + [{"x": 1.0}] * 10
    model = [{"x": 1.0}] * 30 + [{"x": 1.0}] * 10
    r = ev.paired(human, model, "x")
    assert r["n"] == 40 and r["diff"] == pytest.approx(0.75) and r["model_higher"] == 1.0
    assert r["ci"][0] > 0.5
    assert ev.paired(human[:5], model[:5], "x") is None


def test_partial_rho_removes_a_length_effect(ev):
    rng = np.random.default_rng(0)
    length = rng.normal(size=300)
    rows = [{"x": v + rng.normal(scale=0.3), "log_words": v, "letters": rng.normal(), "zipf": rng.normal()}
            for v in length]
    y = length + rng.normal(scale=0.3, size=300)     # x and y share only length
    r = ev.partial(rows, y, "x", np.arange(300), resamples=200)
    assert r["raw"] > 0.7 and abs(r["rho"]) < 0.15 and r["ci"][0] < 0 < r["ci"][1]


def test_lamp_part_runs_on_made_up_records(ev, tmp_path, capsys):
    para = ("The harbour was quiet that morning. It was not a silence but a held breath. Gulls turned, cried, "
            "and settled on the wall. She walked to the end of the pier and counted the boats again. "
            "Nothing had changed since the night before, and the nets still hung where he had left them.")
    records = [{"preedit": para + f" Boat {i} rocked slowly.", "creativity_z_score_pre": str(i % 7),
                "fine_grained_edits": [{"originalText": "It was not a silence but a held breath.", "editedText": "",
                                        "categorization": "Unnecessary Exposition"}] if i % 2 else []}
               for i in range(40)]
    path = tmp_path / "lamp.json"
    path.write_text(json.dumps(records))
    assert ev.main(["lamp", str(path)]) == 0
    out = capsys.readouterr().out
    assert "40 edits of 40 paragraphs" in out
    assert "| contrast | 40 |" in out          # the flagged sentence is found in every record
    assert "edited as unnecessary exposition" in out


def test_arena_cell_filter(ev):
    long = " ".join(["word"] * 80)
    assert ev._prose(json.dumps([long])) == long
    assert ev._prose(json.dumps([long, long])) is None          # more than one turn
    assert ev._prose(json.dumps(["short answer"])) is None
    assert ev._prose(json.dumps([long + "\n```\ncode\n```"])) is None
    assert ev._prose("not json") is None
