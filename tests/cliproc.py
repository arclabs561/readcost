"""Run the readcost command line for a test, in this process or in a new one.

A new interpreter imports spaCy and loads the model, which takes two to six
seconds, and most tests only need the exit code and what was printed. So
``run_cli`` calls ``readcost.cli.main`` here, with the working directory,
standard streams and environment set as a subprocess would have them, and
returns a ``subprocess.CompletedProcess``. conftest.py shares one loaded
model between the calls.

``run_subprocess`` starts ``python -m readcost`` for the tests that need a
real process: the entry point, the process pool, signals and pipes.
``READCOST_TEST_SUBPROCESS=1`` makes ``run_cli`` do the same, to confirm
that a test gives the same result both ways.
"""

import contextlib
import io
import os
import subprocess
import sys

FORCE_SUBPROCESS = bool(os.environ.get("READCOST_TEST_SUBPROCESS"))


def run_subprocess(args, stdin=None, cwd=None, env=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin, check=False,
                          capture_output=True, text=True, cwd=cwd, env=env)


def _stream(text: str = "") -> io.TextIOWrapper:
    # A text stream over bytes, as a pipe is: it has .buffer and no terminal.
    stream = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8", newline="")
    stream.mode = "r+"
    return stream


def _text(stream: io.TextIOWrapper) -> str:
    stream.flush()
    return stream.buffer.getvalue().decode("utf-8").replace("\r\n", "\n")


def run_cli(args, stdin=None, cwd=None, env=None):
    """``python -m readcost ARGS`` without the new process.

    ``env`` replaces the whole environment, as it does for ``subprocess.run``.
    """
    if FORCE_SUBPROCESS:
        return run_subprocess(args, stdin, cwd, env)
    from readcost import cli

    args = [str(a) for a in args]
    saved_cwd, saved_env = os.getcwd(), dict(os.environ)
    saved_streams = sys.stdin, sys.stdout, sys.stderr
    out, err = _stream(), _stream()
    try:
        if cwd is not None:
            os.chdir(cwd)
        if env is not None:
            os.environ.clear()
            os.environ.update(env)
        sys.stdin, sys.stdout, sys.stderr = _stream(stdin or ""), out, err
        try:
            code = cli.main(args)
        except SystemExit as exc:  # argparse, and commands that exit by themselves
            code = exc.code
            if isinstance(code, str):
                print(code, file=sys.stderr)
                code = 1
        with contextlib.suppress(ValueError):
            sys.stdout.flush()
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved_streams
        os.chdir(saved_cwd)
        os.environ.clear()
        os.environ.update(saved_env)
        cli._WORKER = None
    return subprocess.CompletedProcess(["readcost", *args], code or 0, _text(out), _text(err))
