"""Run every test, in process and in subprocesses, against this checkout's source
and in an environment that does not depend on the caller's shell.

Many tests start `python -m readcost` in a temporary directory. Without this,
they import whatever readcost the interpreter has installed, which in a second
worktree can be another branch's editable install, so a stale copy can pass.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

SRC = str(Path(__file__).resolve().parent.parent / "src")
sys.path.insert(0, SRC)
os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (SRC, os.environ.get("PYTHONPATH")) if p)

# The tests must not depend on the shell they start from. Each of these has
# changed a result: an exported GIT_AUTHOR_NAME overrides the author a test
# commits with (test_ci_prose's "AI author" case then passes or fails by the
# caller's shell), a user's git config signs commits or colours output,
# READCOST_CONFIG replaces the config a test wrote, NO_COLOR and FORCE_COLOR
# change what is printed, and a GitHub token sends ci_prose to the network.
# Set here, at import, so that subprocesses inherit the same environment.
STEP_SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")  # kept for the timing report below
for _name in list(os.environ):
    if (_name.startswith(("GIT_", "READCOST_", "GITHUB_")) and _name != "READCOST_TEST_SUBPROCESS") or _name in (
            "GH_TOKEN", "NO_COLOR", "FORCE_COLOR", "CLICOLOR_FORCE", "CLAUDE_PLUGIN_DATA", "XDG_STATE_HOME",
            "XDG_CONFIG_HOME"):
        del os.environ[_name]
os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
# The hooks remember reported findings under the user's cache directory; keep
# a test run out of it (tests of that memory point it at their own tmp_path).
os.environ["READCOST_HOOK_STATE"] = tempfile.mkdtemp(prefix="readcost-hook-state-")
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"


import pytest  # noqa: E402

from readcost.engine import Analyzer  # noqa: E402

# One loaded spaCy pipeline per model name for the whole test process (each
# pytest-xdist worker is its own process). Loading takes about two seconds and
# the pipeline holds no state between texts, so every Analyzer can share it.
# The language server shares pipelines the same way (lsp.Checker).
_MODELS: dict[str, object] = {}
_load_model = Analyzer.nlp.fget


def _shared_model(self):
    if self._nlp is None:
        if self.cfg.model not in _MODELS:
            _MODELS[self.cfg.model] = _load_model(self)
        self._nlp = _MODELS[self.cfg.model]
    return self._nlp


Analyzer.nlp = property(_shared_model)


@pytest.fixture(scope="session")
def analyzer() -> Analyzer:
    """An Analyzer with the default settings, for tests that change none of them."""
    return Analyzer()


_STARTED = time.perf_counter()  # conftest is imported when the run starts


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """In GitHub Actions, add the run's timing to the job summary: total, slowest files and tests."""
    if not STEP_SUMMARY or hasattr(config, "workerinput"):  # pytest-xdist workers report through the controller
        return
    import platform
    from collections import Counter

    reports = [r for outcome in ("passed", "failed", "error") for r in terminalreporter.stats.get(outcome, [])
               if hasattr(r, "duration") and hasattr(r, "nodeid")]
    files, tests = Counter(), Counter()
    for r in reports:  # setup, call and teardown each have a report
        files[r.nodeid.split("::")[0]] += r.duration
        tests[r.nodeid] += r.duration
    wall = time.perf_counter() - _STARTED
    workers = getattr(config.option, "numprocesses", None) or 1
    lines = [f"## Test timing, Python {platform.python_version()}", "",
             f"{len(tests)} tests, {sum(tests.values()):.0f} s of test time on {workers} worker(s)"
             f", {wall:.0f} s wall.", "",
             "| Slowest files | s |", "| --- | ---: |"]
    lines += [f"| {name} | {secs:.1f} |" for name, secs in files.most_common(8)]
    lines += ["", "| Slowest tests | s |", "| --- | ---: |"]
    lines += [f"| {name.replace('|', '/')} | {secs:.1f} |" for name, secs in tests.most_common(10)]
    with open(STEP_SUMMARY, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")
