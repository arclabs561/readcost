"""The PR comment output, the false-positive link, and SARIF help links."""

import json
import subprocess
import sys

from readcost import report
from readcost.config import Config
from readcost.engine import Result
from readcost.features import Finding
from readcost.hooks.common import feedback

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")
PLAIN = "The index stores one list per term.\n"


def run(args, stdin=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin, check=False,
                          capture_output=True, text=True, cwd=cwd)


def finding(path="a.md", line=3, severity="warn", message="3 nouns stacked", feature="stacked-nouns"):
    return Finding(feature=feature, severity=severity, message=message, excerpt="x", sentence="x",
                   path=path, line=line, suggestion="Unpack it")


# --- pr-comment ----------------------------------------------------------------

def test_pr_comment_starts_with_marker_and_lists_findings_worst_first():
    results = [
        Result(path="docs/a.md", words=100, verdict="block", reading_seconds=20.0, reading_ms_per_word=200.0,
               findings=[finding(path="docs/a.md", line=9), finding(path="docs/a.md", line=2, severity="error",
                                                                      feature="long-dependency", message="far apart")]),
        Result(path="b.md", words=50, verdict="pass", reading_seconds=10.0, reading_ms_per_word=200.0),
    ]
    out = report.pr_comment(results)
    assert out.splitlines()[0] == report.COMMENT_MARKER == "<!-- readcost -->"
    assert "2 files" in out and "1 block" in out and "1 pass" in out
    rows = [ln for ln in out.splitlines() if ln.startswith("| ") and "---" not in ln]
    assert rows[0] == "| Where | Rule | Message |"
    assert rows[1:] == ["| docs/a.md:2 | long-dependency | far apart |",
                        "| docs/a.md:9 | stacked-nouns | 3 nouns stacked |"]
    assert "30 s" in out and "150 words" in out
    assert "advisory" in out and report.FEEDBACK_URL in out


def test_pr_comment_escapes_table_cells_and_mentions():
    r = Result(path="a.md", words=10, verdict="advise",
               findings=[finding(message="ask @octocat | then <b>bold</b>\nnext")])
    row = next(ln for ln in report.pr_comment([r]).splitlines() if ln.startswith("| a.md:3"))
    assert row.count(" | ") == 2 and "\\|" in row
    assert "@octocat" not in row and "<b>" not in row


def test_pr_comment_caps_rows():
    r = Result(path="a.md", words=500, verdict="block", findings=[finding(line=i) for i in range(1, 13)])
    out = report.pr_comment([r], max_items=8)
    assert sum(ln.startswith("| a.md:") for ln in out.splitlines()) == 8
    assert "4 more" in out


def test_pr_comment_empty_cases():
    clean = report.pr_comment([Result(path="a.md", words=40, verdict="pass")])
    assert clean.startswith(report.COMMENT_MARKER) and "No findings" in clean and "| Where" not in clean
    none = report.pr_comment([])
    assert none.startswith(report.COMMENT_MARKER) and "No Markdown" in none


def test_pr_comment_from_cli(tmp_path):
    out = run(["check", "-o", "pr-comment", "--fail-on", "never", "--stdin-name", "README.md", "-"],
              DENSE, tmp_path).stdout
    assert out.startswith(report.COMMENT_MARKER) and "| README.md:1 |" in out


# --- false-positive link ---------------------------------------------------------

def test_text_outputs_and_agent_end_with_one_feedback_line(tmp_path):
    for fmt in ("full", "concise", "agent"):
        out = run(["check", "-o", fmt, "--fail-on", "never", "-"], DENSE, tmp_path).stdout
        last = out.rstrip("\n").splitlines()[-1]
        assert report.FEEDBACK_URL in last, fmt
        assert out.count(report.FEEDBACK_URL) == 1, fmt


def test_no_feedback_line_without_findings(tmp_path):
    for fmt in ("full", "concise", "agent"):
        out = run(["check", "-o", fmt, "--fail-on", "never", "-"], PLAIN, tmp_path).stdout
        assert report.FEEDBACK_URL not in out, fmt


def test_feedback_line_suppressed_by_config(tmp_path):
    (tmp_path / "readcost.toml").write_text("feedback_link = false\n")
    for fmt in ("full", "concise", "agent"):
        out = run(["check", "-o", fmt, "--fail-on", "never", "-"], DENSE, tmp_path).stdout
        assert out and report.FEEDBACK_URL not in out, fmt


def test_agent_feedback_line_fits_max_chars():
    results = [Result(path="a.md", words=50, findings=[finding(line=i) for i in range(1, 30)])]
    out = report.agent(results, max_chars=300, feedback_link=True)
    assert len(out) <= 300 and out.endswith(report.FEEDBACK_URL)


def test_hook_feedback_and_other_formats_have_no_link():
    r = Result(path="a.md", words=50, verdict="advise", findings=[finding()])
    assert report.FEEDBACK_URL not in feedback(Config(), r)
    assert report.FEEDBACK_URL not in report.agent([r])
    assert report.FEEDBACK_URL not in report.full([r])
    assert report.FEEDBACK_URL not in report.concise([r])
    assert report.FEEDBACK_URL not in report.github([r])


# --- SARIF -------------------------------------------------------------------------

def test_sarif_rules_link_to_readme_and_results_stay_plain():
    doc = json.loads(report.sarif([Result(path="a.md", findings=[finding()])]))
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert rules and all(rule["helpUri"] == report.RULES_URL for rule in rules)
    assert report.RULES_URL.startswith("https://github.com/arclabs561/readcost")
    assert all("properties" not in res for res in doc["runs"][0]["results"])


def test_json_columns_slice_the_excerpt_out_of_the_source():
    from readcost import Analyzer

    text = "# Title\n\nWe tune the shard compaction retry budget\nby hand every week.\n"
    r = Analyzer(Config()).check_text(text, "markdown", "doc.md")
    rows = json.loads(report.as_json([r]))[0]["findings"]
    stack = next(f for f in rows if f["feature"] == "stacked-nouns")
    line = text.splitlines()[stack["line"] - 1]
    assert stack["end_line"] == stack["line"]
    assert line[stack["column"] - 1:stack["end_column"] - 1] == stack["excerpt"]


def test_json_and_agent_output_carry_measured_precision():
    from readcost import Analyzer

    r = Analyzer(Config()).check_text(DENSE, "markdown", "doc.md")
    rows = json.loads(report.as_json([r]))[0]["findings"]
    data = report.rule_precision()["rules"]
    for f in rows:
        row = data.get(f["feature"])
        if row and row["labelled"] >= 5:
            assert f["precision"] == {"accepted": row["accepted"], "labelled": row["labelled"]}
        else:
            assert f["precision"] is None
    assert any(f["precision"] for f in rows)
    first = next(f for f in rows if f["precision"])
    p = first["precision"]
    assert f"(raters accepted {p['accepted']} of {p['labelled']} such findings)" in report.agent([r])
