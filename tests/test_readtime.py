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
    # Longer words take longer to read; length carries the most importance in
    # the model fitted to OneStop (docs/evaluation.md, "Reading-time model").
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


def test_features_are_compared_in_float32_like_scikit_learn():
    # scikit-learn's trees compare float32 features with float64 thresholds.
    # Take the first tree's root split (every row passes it) and a value just
    # above the threshold in float64 that is not above it in float32: both
    # must take the same branch, as they do in the training library.
    import numpy as np

    spec = readtime._model()
    root = spec["trees"][0]
    f, t = int(root["feature"][0]), float(root["threshold"][0])
    x = float(np.nextafter(np.float32(t), np.float32(np.inf)))  # first float32 above t
    below = float(np.float32(t)) if float(np.float32(t)) <= t else float(np.nextafter(np.float32(t), np.float32(-np.inf)))
    above64 = (below + x) / 2 if (below + x) / 2 > t else t + (x - t) / 4
    assert np.float32(above64) <= np.float32(x) and above64 > t
    rows = np.zeros((2, 14))
    rows[0, f] = above64
    rows[1, f] = float(np.float32(above64))
    a, b = readtime.predict(rows)
    assert a == b
