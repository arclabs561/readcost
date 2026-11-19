"""Pull request text from a GitHub event file: `readcost check --pr-text` and readcost.prtext.

Every event here is made up; nothing is fetched and nothing comes from the
environment the tests run in.
"""

import json

import pytest
from cliproc import run_cli as run

from readcost import prtext, report

DENSE = ("This change adds a flag to the loader so that people can read their files again.\r\n\r\n"
         "We tune the shard compaction retry budget by hand, and the tests still pass on every platform.\r\n")
TEMPLATE = ("<!-- Say what the change does. The cache eviction policy tuning results show segment merge "
            "cost growth. -->\r\n")
CODE = "```\r\nThe storage-shrink job runs nightly with shard compaction retry budget values.\r\n```\r\n"


def event(tmp_path, body, title="Read files again", name="event.json", **extra):
    path = tmp_path / name
    path.write_text(json.dumps({"action": "opened", **extra,
                                "pull_request": {"number": 7, "title": title, "body": body}}))
    return path


@pytest.fixture
def env(tmp_path):
    # A bare environment: nothing from the caller's GitHub or readcost settings.
    return {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "NO_COLOR": "1"}


def test_read_event_takes_the_pull_request_and_nothing_else(tmp_path):
    assert prtext.read_event(event(tmp_path, "Body."))["number"] == 7
    (tmp_path / "push.json").write_text(json.dumps({"ref": "refs/heads/main", "commits": []}))
    assert prtext.read_event(tmp_path / "push.json") is None
    (tmp_path / "issue.json").write_text(json.dumps({"issue": {"number": 3, "body": "Text."}}))
    assert prtext.read_event(tmp_path / "issue.json") is None


def test_comments_and_code_in_the_description_are_not_read(analyzer):
    title, body = prtext.check_pull_request(analyzer, {"title": "Read files again",
                                                        "body": TEMPLATE + CODE + DENSE})
    assert (title.path, body.path) == (prtext.TITLE, prtext.BODY)
    assert [f.excerpt for f in body.findings] == ["compaction retry budget"]
    # Line 1 is the comment, 2-4 the code block, 5 the first sentence, 7 the dense one.
    assert [f.line for f in body.findings] == [7]


def test_a_missing_body_is_an_empty_description(analyzer):
    title, body = prtext.check_pull_request(analyzer, {"title": None, "body": None})
    assert title.words == body.words == 0 and not body.findings


def test_annotations_name_the_text_and_the_line_within_it(tmp_path, env):
    out = run(["check", "--pr-text", event(tmp_path, TEMPLATE + DENSE), "-o", "github"], cwd=tmp_path, env=env)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    assert len(lines) == 1 and "file=" not in lines[0]
    assert lines[0].startswith("::warning title=readcost stacked-nouns in the pull request description%2C line 4::")


def test_no_paths_with_pr_text_does_not_read_stdin(tmp_path, env):
    out = run(["check", "--pr-text", event(tmp_path, DENSE), "-o", "concise"],
              stdin="We tune the index shard compaction retry budget by hand.\n", cwd=tmp_path, env=env)
    assert "<stdin>" not in out.stdout and "pull request description:3" in out.stdout


def test_files_and_pr_text_together_in_the_comment(tmp_path, env):
    (tmp_path / "notes.md").write_text("We tune the index shard compaction retry budget by hand each week.\n")
    out = run(["check", "notes.md", "--pr-text", event(tmp_path, DENSE), "-o", "pr-comment", "--fail-on", "never"],
              cwd=tmp_path, env=env)
    assert out.returncode == 0, out.stderr
    text = out.stdout
    assert "1 file, pull request title and pull request description checked" in text
    assert "| pull request description, line 3 | stacked-nouns |" in text
    assert "| notes.md:1 | stacked-nouns |" in text


def test_pr_text_is_advisory_unless_its_own_level_is_set(tmp_path, env):
    dense = DENSE + "\r\nThe cache eviction policy tuning results show segment merge cost growth.\r\n"
    ev = event(tmp_path, dense, title="Tune the shard compaction retry budget")
    base = ["check", "--pr-text", ev, "-o", "github"]
    assert run(base, cwd=tmp_path, env=env).returncode == 0
    assert run([*base, "--fail-on", "advise"], cwd=tmp_path, env=env).returncode == 0  # files only
    assert run([*base, "--pr-text-fail-on", "advise"], cwd=tmp_path, env=env).returncode == 1
    assert run([*base, "--pr-text-fail-on", "advise", "--exit-zero"], cwd=tmp_path, env=env).returncode == 0


def test_file_verdicts_still_follow_fail_on(tmp_path, env):
    (tmp_path / "notes.md").write_text("We tune the index shard compaction retry budget by hand.\n")
    out = run(["check", "notes.md", "--pr-text", event(tmp_path, DENSE), "-o", "github", "--fail-on", "advise"],
              cwd=tmp_path, env=env)
    assert out.returncode == 1


def test_short_text_is_not_checked(tmp_path, env):
    ev = event(tmp_path, "Fixes #12. We tune the shard compaction retry budget.", title="Fix it")
    out = run(["check", "--pr-text", ev, "-o", "github"], cwd=tmp_path, env=env)
    assert out.returncode == 0 and out.stdout == "" and "under 30; not checked" in out.stderr
    out = run(["check", "--pr-text", ev, "-o", "github", "--pr-text-min-words", "0"], cwd=tmp_path, env=env)
    assert "compaction retry budget" in out.stdout


def test_an_event_without_a_pull_request_checks_only_files(tmp_path, env):
    (tmp_path / "push.json").write_text(json.dumps({"ref": "refs/heads/main"}))
    out = run(["check", "--pr-text", "push.json", "-o", "github"], cwd=tmp_path, env=env)
    assert out.returncode == 0 and out.stdout == "" and "no pull request in this event" in out.stderr


def test_an_unreadable_event_is_an_error(tmp_path, env):
    (tmp_path / "bad.json").write_text("{not json")
    assert run(["check", "--pr-text", "bad.json"], cwd=tmp_path, env=env).returncode == 2
    assert run(["check", "--pr-text", "missing.json"], cwd=tmp_path, env=env).returncode == 2


def test_hostile_text_stays_data(tmp_path, env):
    # Annotation commands, a shell substitution, HTML and a mention in the description.
    body = ("We tune the shard compaction retry budget $(touch pwned) by hand, and the tests "
            "still pass on every platform we run.\r\n::error file=x::injected <b>@octocat</b>\r\n\r\n"
            "The loader reads each file once and keeps the result for the next caller to use.\r\n")
    ev = event(tmp_path, body)
    gh = run(["check", "--pr-text", ev, "-o", "github"], cwd=tmp_path, env=env)
    assert not (tmp_path / "pwned").exists()
    assert all(ln.startswith("::warning title=readcost ") for ln in gh.stdout.splitlines())
    comment = run(["check", "--pr-text", ev, "-o", "pr-comment"], cwd=tmp_path, env=env).stdout
    assert "@octocat" not in comment and "<b>" not in comment


def test_sarif_does_not_claim_a_file(tmp_path, env):
    out = run(["check", "--pr-text", event(tmp_path, DENSE), "-o", "sarif"], cwd=tmp_path, env=env)
    loc = json.loads(out.stdout)["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert "uriBaseId" not in loc["artifactLocation"]


def test_where():
    assert prtext.where(prtext.BODY, 3) == "pull request description, line 3"
    assert prtext.where(prtext.TITLE, 1) == "pull request title"
    assert prtext.where("docs/a.md", 3) == "docs/a.md:3"
    assert report.PR_TEXT == prtext.PATHS
