"""Run the rater and rewrite tasks over an ensemble of OpenRouter models.

    EVAL_OPENROUTER_API_KEY=... python3 -I scripts/rater_ensemble.py rate    ref/eval ref/eval/analysis/ensemble-rate
    EVAL_OPENROUTER_API_KEY=... python3 -I scripts/rater_ensemble.py rewrite ref/eval ref/eval/analysis/paired

Uses EVAL_OPENROUTER_API_KEY. Models run one at a time (one key; parallel
jobs throttle each other). Each response records the model id OpenRouter
actually served and the cost it reported. Prompts, schemas and paragraph
selection are imported from second_rater.py and paired_rewrite.py so every
model sees exactly what the headless Codex and Claude runs saw.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paired_rewrite
import second_rater

MODELS = [
    "moonshotai/kimi-k3.1-pro",
    "google/gemini-4-argon",
    "deepseek/deepseek-v4.1-flash",
    "minimax/minimax-m3",
    "x-ai/grok-4.7",
    "mistralai/mistral-large-4-0",
    "z-ai/glm-5.3-flashx",
    "meta-llama/llama-4-maverick",
]
URL = "https://openrouter.ai/api/v1/chat/completions"


def ask(model: str, prompt: str, schema: dict) -> tuple[dict | None, dict]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt + "\n\nReturn only the JSON object, no prose."}],
        "temperature": 0,
        "response_format": {"type": "json_schema", "json_schema": {"name": "out", "strict": True, "schema": schema}},
        "usage": {"include": True},
    }
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {os.environ['EVAL_OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"})
    meta: dict = {"requested": model}
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            meta["error"] = f"HTTP {exc.code}"
            if exc.code == 404 and "response_format" in body:
                # No provider for this model serves structured output; ask for
                # JSON in the prompt instead and record that the schema was dropped.
                del body["response_format"]
                meta["schema_dropped"] = True
                req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=req.headers)
                continue
            if attempt == 1:
                return None, meta
            time.sleep(10)
        except (urllib.error.URLError, TimeoutError) as exc:
            meta["error"] = str(exc)[:300]
            if attempt == 1:
                return None, meta
            time.sleep(10)
    else:
        return None, meta
    meta.pop("error", None)
    meta["served"] = data.get("model")
    meta["cost"] = (data.get("usage") or {}).get("cost")
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else None, meta
    except json.JSONDecodeError:
        meta["error"] = "unparseable JSON"
        return None, meta


def rate(corpus: Path, out: Path) -> None:
    rows = [json.loads(x) for x in (corpus / "results/sample.jsonl").read_text().splitlines()]
    items = [{"i": i, "rule": r["feature"], "message": r["message"], "excerpt": r["excerpt"],
              "sentence": r["sentence"]} for i, r in enumerate(rows)]
    for model in MODELS:
        dest = out / f"labels-{model.replace('/', '__')}.json"
        labels = json.loads(dest.read_text()) if dest.exists() else {}
        log = []
        for start in range(0, len(items), 30):
            batch = [x for x in items[start:start + 30] if str(x["i"]) not in labels]
            if not batch:
                continue
            prompt = second_rater.RUBRIC + "\n\nFindings:\n" + json.dumps(batch, ensure_ascii=False, indent=1)
            t = time.time()
            data, meta = ask(model, prompt, second_rater.SCHEMA)
            meta.update(batch=start, seconds=round(time.time() - t))
            log.append(meta)
            print(model, start, "ok" if data else f"FAILED {meta.get('error')}", meta.get("cost"), flush=True)
            for lab in (data or {}).get("labels", []):
                if lab.get("label") in ("c", "d", "w"):
                    labels[str(lab["i"])] = {"label": lab["label"], "present": bool(lab.get("present")),
                                             "cause": lab.get("cause", "")}
            dest.write_text(json.dumps(labels, indent=1))
        with (out / "calls.jsonl").open("a") as fh:
            fh.writelines(json.dumps({"task": "rate", **m}) + "\n" for m in log)


def rewrite(corpus: Path, out: Path) -> None:
    items = paired_rewrite.paragraphs(corpus)
    for model in MODELS:
        dest = out / f"pairs-{model.replace('/', '__')}.jsonl"
        done = {json.loads(x)["i"] for x in dest.read_text().splitlines()} if dest.exists() else set()
        log = []
        for start in range(0, len(items), 8):
            batch = [x for x in items[start:start + 8] if x["i"] not in done]
            if not batch:
                continue
            prompt = paired_rewrite.PROMPT + "\n\nPassages:\n" + json.dumps(
                [{"i": x["i"], "text": x["text"]} for x in batch], ensure_ascii=False, indent=1)
            t = time.time()
            data, meta = ask(model, prompt, paired_rewrite.SCHEMA)
            meta.update(batch=start, seconds=round(time.time() - t))
            log.append(meta)
            print(model, start, "ok" if data else f"FAILED {meta.get('error')}", meta.get("cost"), flush=True)
            by_i = {x["i"]: x for x in batch}
            with dest.open("a") as fh:
                for r in (data or {}).get("rewrites", []):
                    if r.get("i") in by_i and r.get("text"):
                        fh.write(json.dumps({**by_i[r["i"]], "model": model, "rewrite": r["text"]}) + "\n")
        with (out / "calls.jsonl").open("a") as fh:
            fh.writelines(json.dumps({"task": "rewrite", **m}) + "\n" for m in log)


if __name__ == "__main__":
    task, corpus, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    {"rate": rate, "rewrite": rewrite}[task](corpus, out)
