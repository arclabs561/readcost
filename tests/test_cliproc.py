"""The test helpers themselves: the in-process command line and the fixed environment."""

import os
import subprocess
import sys

from cliproc import run_cli, run_subprocess

DENSE = "We tune the shard compaction retry budget by hand.\n"


def test_in_process_run_matches_a_real_process(tmp_path):
    args = ["check", "-o", "json", "-"]
    here, there = run_cli(args, DENSE, tmp_path), run_subprocess(args, DENSE, tmp_path)
    assert (here.returncode, here.stdout, here.stderr) == (there.returncode, there.stdout, there.stderr)
    assert '"stacked-nouns"' in here.stdout
    usage = run_cli(["check", "--no-such-flag"], cwd=tmp_path), run_subprocess(["check", "--no-such-flag"], cwd=tmp_path)
    assert usage[0].returncode == usage[1].returncode == 2 and usage[0].stdout == usage[1].stdout == ""


def test_in_process_run_restores_the_process_state(tmp_path):
    cwd, env, streams = os.getcwd(), dict(os.environ), (sys.stdin, sys.stdout, sys.stderr)
    proc = run_cli(["check", "-"], DENSE, tmp_path, {"PATH": os.environ["PATH"], "READCOST_CONFIG": "missing.toml"})
    assert proc.returncode == 2 and "missing.toml" in proc.stderr  # the variable reached the command
    assert (os.getcwd(), dict(os.environ), (sys.stdin, sys.stdout, sys.stderr)) == (cwd, env, streams)


def test_git_identity_and_user_config_do_not_reach_the_tests(tmp_path):
    # conftest.py clears them; an exported GIT_AUTHOR_NAME once decided whether test_ci_prose passed.
    assert not [k for k in os.environ if k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_", "GITHUB_"))]
    assert "READCOST_CONFIG" not in os.environ and "NO_COLOR" not in os.environ
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    seen = subprocess.run(["git", "config", "--get-regexp", "^(user|commit|gpg)\\."], cwd=tmp_path,
                          capture_output=True, text=True, check=False)
    assert seen.stdout == ""
