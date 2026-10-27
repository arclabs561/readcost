"""readcost compare and reading-time hotspots."""

import json
import subprocess
import sys

from readcost import Analyzer, Config, readtime

# The README's own before/after (see "For example, this sentence from a README").
OLD = ("For store restart measurement, the example prints first snapshot-query cost\n"
       "with persisted WAND sidecars present versus after deleting those sidecars and\n"
       "forcing source-segment rebuilds.\n")
NEW = ("To measure a store restart, the example reopens a checkpointed store and\n"
       "prints the duration of its first snapshot query. It does this twice: once\n"
       "with the persisted WAND sidecars present, and once after deleting those\n"
       "sidecars, which forces each segment to be rebuilt from its source vectors.\n")


def run(args, cwd):
    return subprocess.run([sys.executable, "-m", "readcost", *args], cwd=cwd, capture_output=True,
                          text=True, check=False)


def files(tmp_path):
    (tmp_path / "old.md").write_text(OLD)
    (tmp_path / "new.md").write_text(NEW)
    return "old.md", "new.md"


def test_compare_reports_per_word_and_total_time_separately(tmp_path):
    old, new = files(tmp_path)
    out = json.loads(run(["compare", "-o", "json", old, new], tmp_path).stdout)
    o, n = out["old"], out["new"]
    # The rewrite reads faster per word but takes longer in total, because it is longer.
    assert n["reading_ms_per_word"] < o["reading_ms_per_word"]
    assert n["reading_seconds"] > o["reading_seconds"]
    assert n["counts"] == {} and o["counts"] == {"stacked-nouns": 1, "hyphen-compound": 1}
    text = run(["compare", old, new], tmp_path).stdout
    assert "by rule: hyphen-compound 1 -> 0, stacked-nouns 1 -> 0" in text


def test_compare_fail_on(tmp_path):
    old, new = files(tmp_path)
    assert run(["compare", old, new], tmp_path).returncode == 0
    assert run(["compare", "--fail-on", "slower", old, new], tmp_path).returncode == 1  # longer, so slower in total
    assert run(["compare", "--fail-on", "slower", new, old], tmp_path).returncode == 0
    assert run(["compare", "--fail-on", "worse", new, old], tmp_path).returncode == 1  # more findings


def test_compare_shows_findings_only_in_the_rewrite(tmp_path):
    old, new = files(tmp_path)
    out = run(["compare", new, old], tmp_path).stdout  # the dense version as the "rewrite"
    assert "Only in old.md:" in out and "warn[stacked-nouns]" in out
    assert "Only in" not in run(["compare", old, new], tmp_path).stdout


def test_word_times_add_up_to_the_estimate():
    para = " ".join(NEW.split())
    times = readtime.word_times(para)
    words, ms = readtime.estimate([para])
    assert len(times) == words and abs(sum(t[3] for t in times) - ms) < 1e-6
    assert all(para[a:b] == w for a, b, w, _ in times)


def test_hotspots_rank_sentences_by_time_beyond_their_length():
    slow = ("Phosphorylation cascades modulate mitochondrial thermogenesis via uncoupling "
            "proteins, notwithstanding idiosyncratic polymorphisms. ")
    plain = "We went to the shop and then we came back home to eat our lunch together. "
    r = Analyzer(Config()).check_text(plain + slow + plain, "markdown")
    assert r.hotspots and r.hotspots[0]["sentence"].startswith("Phosphorylation")
    assert all(h["words"] >= 8 and h["excess_ms"] > 0 for h in r.hotspots)
    assert not [h for h in r.hotspots if h["sentence"].startswith("We went")]


def test_readme_compare_example_is_current(tmp_path):
    from pathlib import Path

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    start = readme.index("$ readcost compare cmp-old.md cmp-new.md\n") + len("$ readcost compare cmp-old.md cmp-new.md\n")
    shown = readme[start:readme.index("```", start)]
    (tmp_path / "cmp-old.md").write_text(OLD)
    (tmp_path / "cmp-new.md").write_text(NEW)
    assert run(["compare", "cmp-old.md", "cmp-new.md"], tmp_path).stdout == shown


def test_compare_reads_the_old_text_from_a_git_revision(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "doc.md").write_text(OLD)
    git("add", "doc.md")
    git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "old")
    (tmp_path / "doc.md").write_text(NEW)
    by_rev = run(["compare", "HEAD:doc.md", "doc.md", "-o", "json"], tmp_path)
    (tmp_path / "old.md").write_text(OLD)
    by_file = run(["compare", "old.md", "doc.md", "-o", "json"], tmp_path)
    assert by_rev.returncode == by_file.returncode == 0
    assert json.loads(by_rev.stdout)["old"]["points"] == json.loads(by_file.stdout)["old"]["points"] > 0
    missing = run(["compare", "HEAD:nope.md", "doc.md"], tmp_path)
    assert missing.returncode == 2 and "cannot read HEAD:nope.md" in missing.stderr
