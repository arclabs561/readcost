"""Fetch GitHub release notes from a fixed list of projects and tag each as curated or auto-generated.

    python3 -I scripts/fetch_release_notes.py /Volumes/Rebuildable/readcost-ref/broad/release-notes
    PYTHONPATH=src python3 scripts/eval_more.py /Volumes/Rebuildable/readcost-ref/broad

For each repository in ``REPOS`` (30 projects across languages, chosen by
hand for having GitHub releases with written bodies) reads ``repos/{r}/releases`` with ``gh api``
(so it needs a GitHub login) and keeps up to ``--per-repo`` of the newest
non-draft releases that have 50 or more words of prose after cleaning.

A release is ``auto-generated`` when its body has GitHub's generated
structure (a "What's Changed" heading or a "Full Changelog" line) and
``curated`` otherwise. Cleaning drops lines that are only a pull-request or
commit link, a "Full Changelog" line, and the "New Contributors" list, and
removes the "by @user in <pull request URL>" trailer of generated items, so
the item's title stays. User handles are removed. Licence is the repository's
SPDX id; repositories without one are skipped. Category ``release-notes``,
source ``curated`` or ``auto-generated``, with the repository. The text stays
under the output directory, outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

UA = "readcost-eval (https://github.com/arclabs561/readcost)"
REPOS = (
    "rust-lang/rust", "facebook/react", "vuejs/core", "denoland/deno", "astral-sh/uv", "astral-sh/ruff",
    "BurntSushi/ripgrep", "sharkdp/bat", "junegunn/fzf", "prometheus/prometheus", "grafana/grafana",
    "docker/compose", "huggingface/transformers", "pandas-dev/pandas", "tokio-rs/tokio", "rails/rails",
    "vitejs/vite", "eslint/eslint", "cli/cli", "tailwindlabs/tailwindcss", "electron/electron",
    "pydantic/pydantic", "fastapi/fastapi", "gohugoio/hugo", "spf13/cobra", "gin-gonic/gin",
    "charmbracelet/bubbletea", "pallets/click", "encode/httpx", "sveltejs/svelte",
)
MIN_WORDS = 50
URL = r"https?://\S+"


def gh(args: list[str]) -> str:
    return subprocess.run(["gh", "api", "-H", f"User-Agent: {UA}", *args], check=True,
                          capture_output=True, text=True, timeout=120).stdout


def is_generated(body: str) -> bool:
    return bool(re.search(r"^#+\s*What's Changed", body, re.MULTILINE | re.IGNORECASE)
                or re.search(r"\*\*Full Changelog\*\*", body))


def clean_release(body: str) -> str:
    """Release notes without link-only lines, the contributors list, PR trailers or user handles."""
    out, skip = [], False
    for line in body.replace("\r\n", "\n").splitlines():
        if h := re.match(r"^#+\s*(.*)$", line):
            skip = h.group(1).strip().lower().startswith("new contributors")
        if skip or re.search(r"\*\*Full Changelog\*\*", line):
            continue
        line = re.sub(rf"\s+by @[\w-]+(?:\[bot\])?\s+in\s+{URL}", "", line)
        line = re.sub(rf"\s+in\s+{URL}/pull/\d+\s*$", "", line)
        rest = re.sub(rf"{URL}|\[[^\]]*\]\([^)]*\)|#\d+|\b[0-9a-f]{{7,40}}\b|@[\w-]+|[-*+()\[\],:.\s`]", "", line)
        if line.strip() and not rest:
            continue  # only links, issue numbers, hashes or handles
        out.append(re.sub(r"(?<![\w/])@[\w-]+", "", line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def prose_words(md: str) -> int:
    md = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", md)
    md = re.sub(rf"`[^`]*`|{URL}", " ", md)
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", md))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-repo", type=int, default=5)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries, failures = [], []
    for repo in REPOS:
        spdx = (json.loads(gh([f"repos/{repo}"])).get("license") or {}).get("spdx_id")
        if spdx in (None, "", "NOASSERTION"):
            failures.append({"repo": repo, "reason": "no recognized licence"})
            continue
        kept = 0
        for rel in json.loads(gh([f"repos/{repo}/releases?per_page=30"])):
            if kept >= args.per_repo:
                break
            body = rel.get("body") or ""
            if rel.get("draft") or not body.strip():
                continue
            text = clean_release(body)
            if prose_words(text) < MIN_WORDS:
                failures.append({"repo": repo, "tag": rel["tag_name"], "reason": f"under {MIN_WORDS} words"})
                continue
            kind = "auto-generated" if is_generated(body) else "curated"
            tag = re.sub(r"[^\w.-]+", "_", rel["tag_name"])
            path = f"{repo.replace('/', '__')}/{tag}.md"
            (out / path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            (out / path).write_text(text)
            entries.append({"id": f"release-notes/{repo}/{rel['tag_name']}", "category": "release-notes",
                            "source": kind, "repo": repo, "tag": rel["tag_name"],
                            "prerelease": rel.get("prerelease", False), "published": rel.get("published_at"),
                            "author": "", "url": rel["html_url"], "path": path, "format": "markdown",
                            "license": spdx, "fetched_at": now, "via": f"gh api repos/{repo}/releases",
                            "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode())})
            kept += 1
        print(f"{repo}: {kept}", file=sys.stderr)
    (out / "manifest.json").write_text(json.dumps(
        {"description": "GitHub release notes; see scripts/fetch_release_notes.py", "generated_at": now,
         "entries": entries, "failures": failures}, indent=1) + "\n")
    print(len(entries), "releases;", len(failures), "skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
