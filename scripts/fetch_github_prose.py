"""Fetch pull request descriptions and review comments for evaluation.

    python3 -I scripts/fetch_github_prose.py REF/eval-github
    python3 scripts/eval_corpus.py REF/eval-github

Takes, from each repository below, the 20 most recently updated merged pull
requests whose description has 40 or more words, and the 20 most recent review
comments by people (not bots) with 25 or more words. Uses the `gh` CLI, so it
needs a GitHub login. Writes REF/eval-github/manifest.json in the schema of
scripts/fetch_eval_corpus.py (categories "pr" and "review"). The text is each
author's and stays under REF, outside the repository.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOS = ["python/cpython", "rust-lang/rust", "django/django", "kubernetes/kubernetes",
         "astral-sh/ruff", "facebook/react"]
PER_REPO = 20


def gh(path: str) -> list[dict]:
    out = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path],
                         check=True, capture_output=True, text=True, timeout=120).stdout
    return json.loads(out)


def main(ref: Path) -> None:
    entries = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def record(category: str, repo: str, num: str, url: str, body: str, via: str) -> None:
        source = repo.replace("/", "-")
        rel = f"{category}/{source}/{num}.md"
        path = ref / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        entries.append({"id": f"{category}/{source}/{num}", "category": category, "source": source,
                        "author": "", "url": url, "path": rel, "format": "markdown",
                        "license": "each author's; GitHub terms of service", "fetched_at": now, "via": via,
                        "sha256": hashlib.sha256(body.encode()).hexdigest(), "bytes": len(body.encode())})

    for repo in REPOS:
        pulls = gh(f"/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
        kept = 0
        for p in pulls:
            body = p.get("body") or ""
            if p.get("merged_at") and len(body.split()) >= 40 and p["user"]["type"] != "Bot":
                record("pr", repo, str(p["number"]), p["html_url"], body, "gh api pulls")
                kept += 1
                if kept == PER_REPO:
                    break
        comments = gh(f"/repos/{repo}/pulls/comments?sort=created&direction=desc&per_page=100")
        kept = 0
        for c in comments:
            body = c.get("body") or ""
            if len(body.split()) >= 25 and c["user"]["type"] != "Bot":
                record("review", repo, str(c["id"]), c["html_url"], body, "gh api pulls/comments")
                kept += 1
                if kept == PER_REPO:
                    break
        print(repo, sum(e["source"] == repo.replace("/", "-") for e in entries), file=sys.stderr)
    (ref / "manifest.json").write_text(json.dumps(
        {"description": "PR descriptions and review comments; see scripts/fetch_github_prose.py",
         "generated_at": now, "entries": entries, "failures": []}, indent=1) + "\n")
    print(len(entries), "texts")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
