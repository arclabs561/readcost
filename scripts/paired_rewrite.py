"""Paired human vs model-rewrite experiment for readcost.

    READCOST_CODEX_HOME=DIR python3 -I scripts/paired_rewrite.py ref/eval ref/eval/analysis/paired codex
    python3 -I scripts/paired_rewrite.py ref/eval ref/eval/analysis/paired claude

READCOST_CODEX_HOME is a temporary Codex home holding only auth.json and a
two-line config.toml (model, model_provider), so a global AGENTS.md does
not shape the rewrites; claude runs with --safe-mode for the same reason.

Picks human paragraphs (120-260 words, prose only) from the essay and docs
categories of the evaluation corpus, up to 5 per source with a fixed seed,
and asks a headless model to rewrite each one with the same facts (the
prompt follows Cekini et al. 2026). Writes OUT_DIR/pairs-<model>.jsonl with
the original and the rewrite. Batches of 8 paragraphs, one call at a time.
"""
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

PROMPT = """Rewrite each of the following passages as a new, standalone passage in your own words. Cover the
same facts and claims, without adding outside information or omitting substantive content. Write naturally,
for the same audience, using your own wording, sentence structure and paragraphing. Return JSON matching the
schema, one entry per passage with its "i" unchanged and the rewrite in "text"."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rewrites"],
          "properties": {"rewrites": {"type": "array", "items": {
              "type": "object", "additionalProperties": False, "required": ["i", "text"],
              "properties": {"i": {"type": "integer"}, "text": {"type": "string"}}}}}}


def paragraphs(corpus: Path) -> list[dict]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    by_source: dict[str, list[dict]] = {}
    for e in manifest["entries"]:
        if e["category"] not in ("essay", "docs"):
            continue
        p = Path(e["path"]) if Path(e["path"]).is_absolute() else corpus / e["path"]
        text = p.read_text(errors="replace")
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        for para in re.split(r"\n\s*\n", text):
            para = " ".join(para.split())
            words = para.split()
            if not 120 <= len(words) <= 260 or para.startswith(("#", "-", "*", ">", "|", "1.")):
                continue
            if "`" in para or "http" in para or sum(w.isalpha() for w in words) < 0.8 * len(words):
                continue
            by_source.setdefault(e["source"], []).append({"source": e["source"], "id": e["id"], "text": para})
    rng = random.Random(1)
    picked = []
    for source in sorted(by_source):
        items = by_source[source]
        rng.shuffle(items)
        picked.extend(items[:5])
    for i, item in enumerate(picked):
        item["i"] = i
    return picked


def call(model: str, prompt: str, out: Path, tag: str) -> dict | None:
    schema = out / "schema.json"
    answer = out / f"answer-{tag}.json"
    if model == "codex":
        cmd = ["gtimeout", "900", "codex", "exec", "--model", "gpt-6.1-sol", "--sandbox", "read-only",
               "--ephemeral", "--skip-git-repo-check", "--ignore-rules", "-c", "project_doc_max_bytes=0",
               "--output-schema", str(schema), "-o", str(answer), "-"]
        # A minimal CODEX_HOME (auth plus model) keeps the global AGENTS.md out of the rewrites.
        env = {**os.environ, "CODEX_HOME": os.environ["READCOST_CODEX_HOME"]}
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=out, check=False, env=env)
        if proc.returncode != 0 or not answer.exists():
            (out / f"stderr-{tag}.txt").write_text(proc.stderr[-4000:])
            return None
        return json.loads(answer.read_text())
    # --safe-mode keeps the login but drops CLAUDE.md, skills, hooks and MCP servers.
    cmd = ["gtimeout", "900", "claude", "-p", "--safe-mode", "--model", "claude-sonnet-5-5",
           "--no-session-persistence", "--tools", "", "--output-format", "json", "--max-budget-usd", "2",
           "--json-schema", schema.read_text()]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=out, check=False)
    if proc.returncode != 0:
        (out / f"stderr-{tag}.txt").write_text(proc.stderr[-4000:] + proc.stdout[-2000:])
        return None
    answer.write_text(proc.stdout)
    env = json.loads(proc.stdout)
    data = env.get("structured_output") or env.get("result")
    return json.loads(data) if isinstance(data, str) else data


def main(corpus: Path, out: Path, model: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "schema.json").write_text(json.dumps(SCHEMA))
    items = paragraphs(corpus)
    (out / "originals.jsonl").write_text("".join(json.dumps(x) + "\n" for x in items))
    dest = out / f"pairs-{model}.jsonl"
    done = {json.loads(line)["i"] for line in dest.read_text().splitlines()} if dest.exists() else set()
    print(len(items), "paragraphs from", len({x["source"] for x in items}), "sources;", len(done), "done", flush=True)
    for start in range(0, len(items), 8):
        batch = [x for x in items[start:start + 8] if x["i"] not in done]
        if not batch:
            continue
        prompt = PROMPT + "\n\nPassages:\n" + json.dumps([{"i": x["i"], "text": x["text"]} for x in batch],
                                                        ensure_ascii=False, indent=1)
        t = time.time()
        data = call(model, prompt, out, f"{model}-{start:03d}")
        print(f"{model} batch {start}: {'ok' if data else 'FAILED'} in {time.time() - t:.0f}s", flush=True)
        if not data:
            continue
        by_i = {x["i"]: x for x in batch}
        with dest.open("a") as fh:
            for r in data["rewrites"]:
                if r["i"] in by_i:
                    fh.write(json.dumps({**by_i[r["i"]], "model": model, "rewrite": r["text"]}) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "codex")
