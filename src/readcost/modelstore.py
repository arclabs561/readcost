"""Find the spaCy model, or fetch it into a cache on first use.

`spacy download` installs the model with pip, which `uvx` and other uv
environments do not have. readcost instead downloads the pinned model wheel
from spaCy's GitHub releases, checks its SHA-256, unpacks only the model
directory into a per-user cache, and loads it from there. An installed
`en_core_web_sm` package is used first when present.

Set READCOST_NO_DOWNLOAD=1 to forbid the download (offline machines, CI that
installs the model itself); readcost then fails with a message saying how to
install it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

MODEL = "en_core_web_sm"
VERSION = "3.8.0"
URL = (f"https://github.com/explosion/spacy-models/releases/download/"
       f"{MODEL}-{VERSION}/{MODEL}-{VERSION}-py3-none-any.whl")
SHA256 = "1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"
PREFIX = f"{MODEL}/{MODEL}-{VERSION}/"  # the model directory inside the wheel


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "readcost" / "models"


def cached_path() -> Path | None:
    path = cache_dir() / f"{MODEL}-{VERSION}"
    return path if (path / "config.cfg").is_file() else None


def _extract(wheel: Path, dest: Path) -> None:
    """Unpack the model directory from the wheel into dest, refusing odd paths."""
    with zipfile.ZipFile(wheel) as zf:
        for member in zf.infolist():
            name = member.filename
            if not name.startswith(PREFIX) or name.endswith("/"):
                continue
            rel = Path(name[len(PREFIX):])
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"unexpected path in model wheel: {name}")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    if not (dest / "config.cfg").is_file():
        raise ValueError(f"model wheel has no {PREFIX}config.cfg")


def install(wheel: Path) -> Path:
    """Verify a downloaded wheel and unpack it into the cache; returns the model path."""
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != SHA256:
        raise ValueError(f"model download has SHA-256 {digest}, expected {SHA256}")
    final = cache_dir() / f"{MODEL}-{VERSION}"
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=final.parent, prefix=".partial-"))
    try:
        _extract(wheel, staging)
        if final.exists():
            shutil.rmtree(final)
        staging.rename(final)  # atomic on one filesystem: no half-written model
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return final


def fetch(timeout: float = 120.0) -> Path:
    if os.environ.get("READCOST_NO_DOWNLOAD"):
        raise OSError(f"spaCy model {MODEL} is not installed and READCOST_NO_DOWNLOAD is set; "
                      "run `readcost setup` where downloads are allowed")
    print(f"readcost: downloading the spaCy model {MODEL} {VERSION} (13 MB, once) to {cache_dir()}",
          file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        wheel = Path(tmp) / "model.whl"
        with urllib.request.urlopen(URL, timeout=timeout) as resp, open(wheel, "wb") as out:
            shutil.copyfileobj(resp, out)
        return install(wheel)


def load(name: str = MODEL, **kwargs):
    """spacy.load(name), falling back to the cached or freshly fetched default model."""
    import spacy

    try:
        return spacy.load(name, **kwargs)
    except OSError:
        if name != MODEL:
            raise
    path = cached_path() or fetch()
    return spacy.load(path, **kwargs)
