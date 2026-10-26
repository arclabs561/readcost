"""Predicted reading time: properties from the eye-tracking literature, and the report wiring."""

import json
import subprocess
import sys

import pytest

from readcost import Analyzer, Config, readtime

pytestmark = pytest.mark.skipif(not readtime.available(), reason="reading-time model data missing")


def ms(words):
    return list(readtime.predict(readtime.features(words)))


def test_longer_words_take_longer_to_read():
    # Word length is the strongest single predictor of reading time (Rayner 1998).
    a = ms("We saw the cat on the mat today .".split())
    b = ms("We saw the photosynthesis on the mat today .".split())
    assert b[3] > a[3] + 50


def test_rarer_words_take_longer_than_common_words_of_the_same_length():
    # Frequency effect at matched length: "house" and "nadir"-like pairs.
    common = ms("They walked to the house before noon .".split())[4]
    rare = ms("They walked to the gnome before noon .".split())[4]
    assert rare > common


def test_ordinary_prose_lands_near_observed_reading_rates():
    # OneStop and Provo readers average about 200 ms per word.
    text = ("The city council met on Tuesday to discuss the new budget. Several members "
            "asked why the cost of road repairs had doubled since last year, and the "
            "mayor promised a full report by the end of the month.")
    mean = sum(ms(text.split())) / len(text.split())
    assert 160 < mean < 260


def test_code_spans_are_left_out_of_the_estimate():
    r = Analyzer(Config()).check_text("Run `make install` and then call `parse()` once per file.", "markdown")
    assert r.reading_seconds is not None
    plain = Analyzer(Config()).check_text("Run and then call once per file.", "markdown")
    assert r.reading_seconds == pytest.approx(plain.reading_seconds, rel=0.25)


def test_result_reports_reading_time_for_whole_documents_only():
    a = Analyzer(Config())
    text = "The index stores one list of documents for each term.\n\nYou can search it from several threads.\n"
    whole = a.check_text(text, "markdown")
    assert whole.reading_ms_per_word and 100 < whole.reading_ms_per_word < 400
    assert whole.reading_seconds == pytest.approx(whole.reading_ms_per_word * len(text.split()) / 1000)
    assert a.check_text(text, "markdown", lines=[(1, 1)]).reading_seconds is None


def test_json_and_text_output_carry_reading_time(tmp_path):
    (tmp_path / "doc.md").write_text("The index stores one list of documents for each term.\n")
    out = subprocess.run([sys.executable, "-m", "readcost", "check", str(tmp_path / "doc.md"), "-o", "json"],
                         capture_output=True, text=True, check=False)
    row = json.loads(out.stdout)[0]
    assert row["reading_seconds"] > 0 and row["reading_ms_per_word"] > 0
    text = subprocess.run([sys.executable, "-m", "readcost", "check", str(tmp_path / "doc.md")],
                          capture_output=True, text=True, check=False).stdout
    assert "predicted reading time" in text
