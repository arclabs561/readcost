"""Fetch reference text for readcost's per-context profiles.

    python3 scripts/fetch_reference_corpora.py OUT_DIR

Writes OUT_DIR/readme/<owner>__<repo>.md (READMEs from many authors) and
OUT_DIR/commit/<n>.txt (commit messages from golang/go), plus
OUT_DIR/SOURCES.json recording what was fetched and when. Uses the `gh` CLI.
Only derived statistics from this text are shipped with readcost.
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

READMES = [
    "serde-rs/serde", "tokio-rs/tokio", "clap-rs/clap", "rust-lang/cargo", "sharkdp/fd",
    "sharkdp/bat", "astral-sh/uv", "astral-sh/ruff", "PyO3/pyo3", "BurntSushi/ripgrep",
    "psf/requests", "pallets/flask", "pallets/click", "encode/httpx", "pydantic/pydantic",
    "fastapi/fastapi", "python-attrs/attrs", "pytest-dev/pytest", "numpy/numpy",
    "spf13/cobra", "junegunn/fzf", "cli/cli", "charmbracelet/bubbletea", "gohugoio/hugo",
    "expressjs/express", "vitejs/vite", "prettier/prettier", "axios/axios",
    "curl/curl", "redis/redis", "libuv/libuv", "jqlang/jq", "neovim/neovim",
    "tmux/tmux", "sqlite/sqlite", "duckdb/duckdb", "apache/arrow", "pola-rs/polars",
    "huggingface/transformers", "pytorch/pytorch", "denoland/deno", "oven-sh/bun",
]
COMMIT_REPO = "golang/go"
COMMIT_PAGES = 10


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main(out: Path) -> None:
    sources = {"fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
               "readme": [], "commit": {"repo": COMMIT_REPO, "count": 0}}
    (out / "readme").mkdir(parents=True, exist_ok=True)
    for repo in READMES:
        try:
            text = gh("api", f"repos/{repo}/readme", "-H", "Accept: application/vnd.github.raw")
        except subprocess.CalledProcessError:
            print(f"skip {repo}", file=sys.stderr)
            continue
        (out / "readme" / (repo.replace("/", "__") + ".md")).write_text(text)
        sources["readme"].append(repo)
    (out / "commit").mkdir(parents=True, exist_ok=True)
    n = 0
    for page in range(1, COMMIT_PAGES + 1):
        data = json.loads(gh("api", f"repos/{COMMIT_REPO}/commits?per_page=100&page={page}"))
        for c in data:
            msg = c["commit"]["message"]
            if msg.startswith("Merge ") or len(msg.split()) < 8:
                continue
            (out / "commit" / f"{n:05d}.txt").write_text(msg + "\n")
            n += 1
    sources["commit"]["count"] = n
    (out / "SOURCES.json").write_text(json.dumps(sources, indent=1) + "\n")
    print(f"{len(sources['readme'])} READMEs, {n} commit messages")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
