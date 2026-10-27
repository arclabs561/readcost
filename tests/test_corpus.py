"""Repetition across texts: templates, CR-POS and openers."""

import subprocess
import sys

from readcost import Analyzer, Config
from readcost.corpus import analyze, split_records

# Constructed: the same frame refilled, against varied sentences of similar length.
FRAMED = [f"This change improves the {a} of the {b} for every user. This change reduces the {c} of the {d}."
          for a, b, c, d in [("speed", "parser", "cost", "build"), ("safety", "cache", "size", "index"),
                             ("clarity", "docs", "noise", "logs"), ("latency", "server", "load", "queue")]]
VARIED = ["The parser got faster after we cached tokens, and builds are cheaper now.",
          "Why did the cache shrink? Because the index stopped storing duplicate keys.",
          "Logs are quieter; we dropped three warnings nobody acted on and fixed the docs.",
          "Under load the server once stalled, so requests now queue with a deadline."]


def test_refilled_frames_are_more_repetitive_than_varied_text():
    a = Analyzer(Config())
    framed = analyze(a, [(f"f{i}.md", t) for i, t in enumerate(FRAMED)])
    varied = analyze(a, [(f"v{i}.md", t) for i, t in enumerate(VARIED)])
    assert framed.cr_pos > varied.cr_pos
    assert framed.templates_per_token > varied.templates_per_token
    assert framed.top_openers[0]["opener"] == "this change" and framed.top_openers[0]["count"] == 8
    assert framed.top_templates[0]["texts"] == 4


def test_split_records_on_separator_lines():
    assert split_records("one\n---\ntwo\n\n=====\nthree\n") == ["one", "two", "three"]


def test_cli_needs_two_texts(tmp_path):
    (tmp_path / "a.md").write_text(FRAMED[0])
    run = subprocess.run([sys.executable, "-m", "readcost", "corpus", "a.md"], cwd=tmp_path,
                         capture_output=True, text=True, check=False)
    assert run.returncode == 2 and "two or more texts" in run.stderr
    (tmp_path / "many.md").write_text("\n---\n".join(FRAMED))
    run = subprocess.run([sys.executable, "-m", "readcost", "corpus", "--split", "many.md"], cwd=tmp_path,
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0 and run.stdout.startswith("4 texts")
