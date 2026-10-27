"""Built-in reference profiles and `readcost style`."""

import json
import subprocess
import sys

from readcost.profile import Profile, builtin_profiles, load_profile

LISTS = ("It reads Markdown, reStructuredText, HTML, plain text, and JSON from files. "
         "It writes text, JSON, SARIF, GitHub annotations, and Markdown for comments. "
         "It runs in git hooks, editors, CI jobs, chat tools, and agent harnesses. ") * 2


def run(args, cwd):
    return subprocess.run([sys.executable, "-m", "readcost", *args], cwd=cwd, capture_output=True,
                          text=True, check=False)


def test_builtin_profiles_load_with_numbers_and_sources_only():
    names = builtin_profiles()
    assert {"rust-book", "go-docs", "python-docs", "essays", "readmes"} <= set(names)
    for name in names:
        prof = load_profile(name)
        assert prof.words > 5000 and prof.reading_ms_per_word and prof.words_per_sentence
        assert all(s.startswith("http") for s in prof.sources)


def test_older_profiles_without_new_fields_still_load():
    d = json.loads(load_profile("rust-book").to_json())
    del d["reading_ms_per_word"], d["words_per_sentence"]
    assert Profile.from_dict(d).reading_ms_per_word is None


def test_style_marks_rates_far_above_the_reference(tmp_path):
    (tmp_path / "doc.md").write_text(LISTS)
    out = run(["style", "doc.md", "--against", "rust-book"], tmp_path).stdout
    line = next(x for x in out.splitlines() if x.startswith("inline-list per 1k words"))
    assert line.endswith("much higher")
    assert "predicted ms per word" in out and "words per sentence" in out
    assert "much higher" not in next(x for x in out.splitlines() if x.startswith("words per sentence"))


def test_style_list_and_unknown_profile(tmp_path):
    out = run(["style", "--list"], tmp_path).stdout
    assert out.count("words") >= len(builtin_profiles())
    (tmp_path / "doc.md").write_text(LISTS)
    assert run(["style", "doc.md", "--against", "no-such-profile"], tmp_path).returncode == 2
