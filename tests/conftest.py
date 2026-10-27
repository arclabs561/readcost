"""Run every test, in process and in subprocesses, against this checkout's source.

Many tests start `python -m readcost` in a temporary directory. Without this,
they import whatever readcost the interpreter has installed, which in a second
worktree can be another branch's editable install, so a stale copy can pass.
"""

import os
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parent.parent / "src")
sys.path.insert(0, SRC)
os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (SRC, os.environ.get("PYTHONPATH")) if p)

