"""Label the items of rounds 1 to 3 with open models (docs/prereg/open-family-raters.md).

Runs inside a Hugging Face Job on one H200, in the image vllm/vllm-openai:v0.34.0,
with the image's interpreter and packages:

    uv run --no-project --python /usr/bin/python3 scripts/open_raters_job.py \\
        --items hf://datasets/arclabs561/readcost-labels/items \\
        --upload arclabs561/readcost-labels --run-id RUN [--pilot 50]

--items is a folder (or a folder in a Hugging Face dataset) that holds
round{1,2,3}.jsonl.gz, as scripts/rebuild_items.py writes them, and the
rubrics round{N}-RUBRIC.txt and round{N}-RUBRIC_BLIND.txt; a rubric missing
there is read from eval/<round>/RUBRIC.txt or RUBRIC_BLIND.txt in this
checkout.

Each model runs in its own process, one after another. Per round, model,
protocol (primed or unprimed) and sample (s1, s2, s3 at temperature 0.7,
and greedy) the job writes a label file in the schema of
eval/<round>/labels/, the raw replies beside it under raw/, and a log per
model; after each model it uploads the run folder to the private dataset
under runs/<run-id>/. It prints a summary at the end, with the projected
cost of a full run when --pilot is given.

The script needs only the standard library, vllm and huggingface_hub (both
in the image); nothing from readcost is imported. HF_TOKEN is read from
the environment for downloads and the upload.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUNDS = {1: "heldout", 2: "breadth", 3: "kinds"}
PROTOCOLS = ("primed", "unprimed")
RUBRIC_FILES = {"primed": "RUBRIC", "unprimed": "RUBRIC_BLIND"}

# every modality limit at 0 (vLLM: "equivalent to setting --limit-mm-per-prompt to 0 for every modality")
MULTIMODAL_OFF = {"language_model_only": True}
MODELS = {
    "qwen": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0",
             "llm": dict(MULTIMODAL_OFF), "chat_template_kwargs": {"enable_thinking": False}},
    "gemma": {"repo": "google/gemma-4-31B-it", "revision": "842da3794eaa0b77d5f08bae87a17459d91ff475",
              "llm": dict(MULTIMODAL_OFF), "chat_template_kwargs": {"enable_thinking": False}},
    "glm": {"repo": "zai-org/GLM-4.7-Flash", "revision": "7dd20894a642a0aa287e9827cb1a1f7f91386b67",
            "llm": {}, "chat_template_kwargs": {"enable_thinking": False}},
    "mistral": {"repo": "mistralai/Ministral-3-14B-Instruct-2512",
                "revision": "29439f81c2be264d8d393273f99e7db9c0961120",
                "llm": {**MULTIMODAL_OFF, "tokenizer_mode": "mistral", "config_format": "mistral",
                        "load_format": "mistral"},
                "chat_template_kwargs": None},
    # the substitute, used only under the plan's stopping rules
    "olmo": {"repo": "allenai/Olmo-3.1-32B-Instruct", "revision": "ac0587e4a7744a551c059d8cd17ba220bc940dae",
             "llm": {}, "chat_template_kwargs": None},
}
PANEL = ("qwen", "gemma", "glm", "mistral")
LLM_ARGS = {"max_model_len": 8192, "gpu_memory_utilization": 0.90, "enable_prefix_caching": True,
            "generation_config": "vllm", "seed": 0}

# (name, temperature, seed); greedy takes no seed
SAMPLES = (("s1", 0.7, 1), ("s2", 0.7, 2), ("s3", 0.7, 3), ("greedy", 0.0, None))
MAX_TOKENS = 160
RETRY_SEED_OFFSET = 1000
PILOT_SEED = "open-raters-pilot"

# the fields of the rater batch files, in their order (heldout_precision.rater_item,
# breadth_precision.rater_item and blind_item; round 1's unprimed batches had no kind)
FIELDS = {
    (1, "primed"): ("i", "rule", "message", "excerpt", "sentence", "before", "after"),
    (1, "unprimed"): ("i", "excerpt", "sentence", "before", "after"),
    (2, "primed"): ("i", "kind", "rule", "message", "excerpt", "sentence", "before", "after"),
    (2, "unprimed"): ("i", "kind", "excerpt", "sentence", "before", "after"),
}
FIELDS[(3, "primed")] = FIELDS[(2, "primed")]
FIELDS[(3, "unprimed")] = FIELDS[(2, "unprimed")]

# full-run size and prices, for the projection from a pilot
FULL_REQUESTS_PER_MODEL = 23164
PRICE_PER_HOUR = 5.0
COST_MARGIN = 1.25


# --- items and prompts ---

def read_items(folder: Path) -> dict[int, list[dict]]:
    out = {}
    for rnd in ROUNDS:
        path = folder / f"round{rnd}.jsonl.gz"
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                out[rnd] = [json.loads(line) for line in f if line.strip()]
    return out


def items_digest(rows: list[dict]) -> str:
    """SHA-256 of the rows as canonical JSON lines, independent of gzip's header."""
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps(r, ensure_ascii=False, sort_keys=True).encode() + b"\n")
    return h.hexdigest()


def read_rubrics(folder: Path, root: Path | None = None) -> dict[tuple[int, str], str]:
    root = ROOT if root is None else root
    out = {}
    for rnd, name in ROUNDS.items():
        for proto, stem in RUBRIC_FILES.items():
            for path in (folder / f"round{rnd}-{stem}.txt", root / "eval" / name / f"{stem}.txt"):
                if path.exists():
                    out[(rnd, proto)] = path.read_text(encoding="utf-8")
                    break
    return out


def item_view(row: dict, rnd: int, proto: str) -> dict:
    """The item as a rater batch file showed it: primed with rule and message, unprimed without."""
    src = row | {"excerpt": row["primed_excerpt"] if proto == "primed" else row["blind_excerpt"]}
    return {k: src.get(k) for k in FIELDS[(rnd, proto)]}


def batch_text(view: dict) -> str:
    return json.dumps([view], ensure_ascii=False, indent=1) + "\n"


def messages(rubric: str, view: dict) -> list[dict]:
    return [{"role": "system", "content": rubric}, {"role": "user", "content": batch_text(view)}]


def reply_schema(item_id: int, proto: str) -> dict:
    """The rubric's reply format for a batch of one item."""
    props = {"i": {"type": "integer", "enum": [item_id]},
             "label": {"type": "string", "enum": ["c", "d", "w"]}}
    if proto == "primed":
        props["present"] = {"type": "boolean"}
    props["cause"] = {"type": "string"}
    entry = {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    return {"type": "object", "properties": {"labels": {"type": "array", "items": entry, "minItems": 1,
                                                         "maxItems": 1}},
            "required": ["labels"], "additionalProperties": False}


def parse_reply(text: str, item_id: int, proto: str) -> dict | None:
    """The one label entry, or None if the reply is not the format the rubric asks for."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    labels = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(labels, list) or len(labels) != 1 or not isinstance(labels[0], dict):
        return None
    e = labels[0]
    if e.get("i") != item_id or e.get("label") not in ("c", "d", "w"):
        return None
    if proto == "primed" and not isinstance(e.get("present"), bool):
        return None
    cause = e.get("cause", "")
    if not isinstance(cause, str):
        return None
    out = {"id": item_id, "label": e["label"]}
    if proto == "primed":
        out["construction_present"] = e["present"]
    out["cause"] = cause
    return out


@dataclass
class Request:
    rnd: int
    proto: str
    item: int
    sample: str
    temperature: float
    seed: int | None
    messages: list[dict]
    schema: dict
    attempt: int = 1

    def key(self) -> tuple:
        return (self.rnd, self.proto, self.item, self.sample)


def pilot_keys(items: dict[int, list[dict]], n: int) -> set[tuple[int, int]]:
    keys = sorted((rnd, r["i"]) for rnd, rows in items.items() for r in rows)
    random.Random(PILOT_SEED).shuffle(keys)
    return set(keys[:n])


def build_requests(items: dict[int, list[dict]], rubrics: dict, samples=SAMPLES,
                   only: set[tuple[int, int]] | None = None) -> list[Request]:
    """Every request, sorted by round, protocol, item and sample, so prefixes repeat back to back."""
    reqs = []
    for rnd in sorted(items):
        for proto in PROTOCOLS:
            rubric = rubrics[(rnd, proto)]
            flag = "in_primed" if proto == "primed" else "in_blind"
            seen = set()
            for row in sorted(items[rnd], key=lambda r: r["i"]):
                if not row.get(flag) or row["i"] in seen or (only is not None and (rnd, row["i"]) not in only):
                    continue
                seen.add(row["i"])
                msg = messages(rubric, item_view(row, rnd, proto))
                schema = reply_schema(row["i"], proto)
                for name, temp, seed in samples:
                    reqs.append(Request(rnd, proto, row["i"], name, temp, seed, msg, schema))
    return reqs


# --- running a model ---

@dataclass
class Reply:
    text: str
    finish_reason: str | None
    prompt_tokens: int
    cached_tokens: int
    output_tokens: int


@dataclass
class ModelResult:
    key: str
    labels: dict[tuple, dict] = field(default_factory=dict)  # Request.key() -> label entry
    raw: dict[tuple, dict] = field(default_factory=dict)
    failures: Counter = field(default_factory=Counter)      # (round, protocol) -> unparsed after retry
    retried: int = 0
    tokens: Counter = field(default_factory=Counter)
    seconds: float = 0.0


Generate = Callable[[list[Request]], list[Reply]]


def run_requests(key: str, reqs: list[Request], generate: Generate) -> ModelResult:
    """Generate, parse, retry the failures once with the seed plus 1,000, and keep what parses."""
    res = ModelResult(key)
    t0 = time.time()
    pending = reqs
    for attempt in (1, 2):
        if not pending:
            break
        replies = generate(pending)
        assert len(replies) == len(pending)
        retry = []
        for req, rep in zip(pending, replies):
            res.tokens["prompt"] += rep.prompt_tokens
            res.tokens["cached"] += rep.cached_tokens
            res.tokens["output"] += rep.output_tokens
            res.tokens["requests"] += 1
            parsed = None if rep.finish_reason == "length" else parse_reply(rep.text, req.item, req.proto)
            res.raw[req.key()] = {"id": req.item, "attempt": attempt, "seed": req.seed, "text": rep.text,
                                  "finish_reason": rep.finish_reason, "prompt_tokens": rep.prompt_tokens,
                                  "cached_tokens": rep.cached_tokens, "output_tokens": rep.output_tokens,
                                  "parsed": parsed is not None}
            if parsed is not None:
                res.labels[req.key()] = parsed
            elif attempt == 1:
                retry.append(Request(req.rnd, req.proto, req.item, req.sample, req.temperature,
                                     None if req.seed is None else req.seed + RETRY_SEED_OFFSET,
                                     req.messages, req.schema, attempt=2))
            else:
                res.failures[(req.rnd, req.proto)] += 1
        res.retried += len(retry) if attempt == 1 else 0
        pending = retry
    res.seconds = time.time() - t0
    return res


def rater_name(key: str, proto: str, sample: str) -> str:
    return f"open-{key}-{proto}-{sample}"


def write_outputs(out: Path, res: ModelResult, reqs: list[Request]) -> list[Path]:
    """Label files under eval/<round>/labels/ and raw replies under eval/<round>/raw/."""
    groups: dict[tuple, list[Request]] = defaultdict(list)
    for r in reqs:
        groups[(r.rnd, r.proto, r.sample)].append(r)
    written = []
    for (rnd, proto, sample), rs in sorted(groups.items()):
        name = rater_name(res.key, proto, sample)
        lab_dir = out / "eval" / ROUNDS[rnd] / "labels"
        raw_dir = out / "eval" / ROUNDS[rnd] / "raw"
        lab_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)
        labels = [res.labels[r.key()] for r in rs if r.key() in res.labels]
        p = lab_dir / f"{name}.json"
        p.write_text(json.dumps(labels, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        written.append(p)
        q = raw_dir / f"{name}.jsonl"
        q.write_text("".join(json.dumps(res.raw[r.key()], ensure_ascii=False) + "\n" for r in rs
                             if r.key() in res.raw), encoding="utf-8")
        written.append(q)
    return written


def model_log(res: ModelResult, spec: dict, env: dict, load_seconds: float) -> dict:
    reqs = res.tokens["requests"]
    return {"model": res.key, "repo": spec["repo"], "revision_requested": spec["revision"],
            "revision_resolved": env.get("revision_resolved"), "env": env, "load_seconds": round(load_seconds, 1),
            "generate_seconds": round(res.seconds, 1), "tokens": dict(res.tokens), "retried": res.retried,
            "parse_failures": {f"round{r} {p}": n for (r, p), n in sorted(res.failures.items())},
            "labels": len(res.labels),
            "requests_per_second": round(reqs / res.seconds, 2) if res.seconds else None,
            "output_tokens_per_second": round(res.tokens["output"] / res.seconds, 1) if res.seconds else None}


def projected_cost(logs: list[dict], requests_per_model: int = FULL_REQUESTS_PER_MODEL,
                   price: float = PRICE_PER_HOUR, margin: float = COST_MARGIN) -> float | None:
    """The plan's projection: sum over models of load time plus requests at the measured rate."""
    secs = 0.0
    for log in logs:
        rate = log.get("requests_per_second")
        if not rate:
            return None
        secs += log["load_seconds"] + requests_per_model / rate
    return secs / 3600 * price * margin


def parse_rates(log: dict, reqs_by_group: Counter) -> dict[str, float]:
    """Share of requests per round and protocol with a label after the retry."""
    out = {}
    for (rnd, proto), n in sorted(reqs_by_group.items()):
        failed = log["parse_failures"].get(f"round{rnd} {proto}", 0)
        out[f"round{rnd} {proto}"] = (n - failed) / n if n else None
    return out


# --- vLLM ---

def vllm_generator(spec: dict) -> tuple[Generate, dict, float]:
    """Load the model with vLLM; return the generate function, the environment record and the load time."""
    import torch
    import vllm
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    env = {"vllm": vllm.__version__, "torch": torch.__version__, "cuda": torch.version.cuda,
           "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
           "python": platform.python_version()}
    try:
        from huggingface_hub import model_info
        env["revision_resolved"] = model_info(spec["repo"], revision=spec["revision"]).sha
    except Exception as exc:  # noqa: BLE001 -- recorded, not fatal: vLLM still loads the pinned revision
        env["revision_resolved"] = f"lookup failed: {type(exc).__name__}"
    t0 = time.time()
    llm = LLM(model=spec["repo"], revision=spec["revision"], tokenizer_revision=spec["revision"],
              **LLM_ARGS, **spec["llm"])
    load_seconds = time.time() - t0

    def generate(reqs: list[Request]) -> list[Reply]:
        params = [SamplingParams(temperature=r.temperature, top_p=1.0, top_k=0, seed=r.seed, max_tokens=MAX_TOKENS,
                                 structured_outputs=StructuredOutputsParams(json=r.schema)) for r in reqs]
        kwargs = {"chat_template_kwargs": spec["chat_template_kwargs"]} if spec["chat_template_kwargs"] else {}
        outs = llm.chat([r.messages for r in reqs], sampling_params=params, use_tqdm=True, **kwargs)
        return [Reply(o.outputs[0].text, o.outputs[0].finish_reason, len(o.prompt_token_ids or []),
                      o.num_cached_tokens or 0, len(o.outputs[0].token_ids)) for o in outs]

    return generate, env, load_seconds


# --- the job ---

def resolve_items(spec: str, cache: Path) -> Path:
    """A local folder, or hf://datasets/OWNER/NAME/PATH downloaded with huggingface_hub."""
    if not spec.startswith("hf://datasets/"):
        return Path(spec)
    owner, name, *rest = spec.removeprefix("hf://datasets/").split("/")
    sub = "/".join(rest)
    from huggingface_hub import snapshot_download
    local = snapshot_download(f"{owner}/{name}", repo_type="dataset", local_dir=cache,
                              allow_patterns=[f"{sub}/*"] if sub else None, token=os.environ.get("HF_TOKEN"))
    return Path(local) / sub


def upload(run_dir: Path, repo: str, run_id: str, message: str) -> None:
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(folder_path=str(run_dir), path_in_repo=f"runs/{run_id}", repo_id=repo, repo_type="dataset",
                      commit_message=message)


def select(items: dict, rubrics: dict, args) -> list[Request]:
    samples = tuple(s for s in SAMPLES if s[0] in args.samples)
    only = pilot_keys(items, args.pilot) if args.pilot else None
    if args.no_ranked:
        items = {rnd: [r for r in rows if rnd != 3 or r.get("in_primed")] for rnd, rows in items.items()}
    return build_requests(items, rubrics, samples, only)


def run_one(key: str, args) -> int:
    """Run one model in this process and write its outputs and log."""
    spec = MODELS[key]
    folder = Path(args.items_dir)
    items, rubrics = read_items(folder), read_rubrics(folder)
    reqs = select(items, rubrics, args)
    generate, env, load_seconds = vllm_generator(spec)
    res = run_requests(key, reqs, generate)
    run_dir = Path(args.out) / args.run_id
    write_outputs(run_dir, res, reqs)
    log = model_log(res, spec, env, load_seconds)
    log["parse_rate"] = parse_rates(log, Counter((r.rnd, r.proto) for r in reqs))
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / f"{key}.json").write_text(json.dumps(log, indent=1) + "\n")
    return 0


def summary(run_dir: Path, keys: list[str], pilot: int | None) -> str:
    lines = [f"run {run_dir.name}"]
    logs = []
    for key in keys:
        p = run_dir / "logs" / f"{key}.json"
        if not p.exists():
            lines.append(f"{key}: no log (failed or not run)")
            continue
        log = json.loads(p.read_text())
        logs.append(log)
        worst = min((v for v in log["parse_rate"].values() if v is not None), default=None)
        lines.append(f"{key}: {log['repo']}@{log['revision_resolved']} vllm {log['env'].get('vllm')}; "
                     f"load {log['load_seconds']} s, generate {log['generate_seconds']} s, "
                     f"{log['requests_per_second']} req/s, {log['output_tokens_per_second']} out tok/s; "
                     f"tokens {log['tokens']}; retried {log['retried']}; failures {log['parse_failures']}; "
                     f"lowest parse rate {worst if worst is None else f'{worst:.1%}'}")
    if pilot and logs:
        cost = projected_cost(logs)
        lines.append("projected full run: " + ("n/a" if cost is None else
                                               f"${cost:.2f} on h200 ({len(logs)} models, margin {COST_MARGIN})"))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--items", required=True, help="folder, or hf://datasets/OWNER/NAME/PATH")
    ap.add_argument("--out", default="/tmp/open-raters")
    ap.add_argument("--run-id", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    ap.add_argument("--models", default=",".join(PANEL), help="comma-separated keys of MODELS")
    ap.add_argument("--samples", default=",".join(s[0] for s in SAMPLES))
    ap.add_argument("--pilot", type=int, help="label only the first N items of the pilot order")
    ap.add_argument("--no-ranked", action="store_true", help="leave out round 3's ranked sentences")
    ap.add_argument("--upload", help="dataset repo for runs/<run-id>/, e.g. arclabs561/readcost-labels")
    ap.add_argument("--one", help=argparse.SUPPRESS)
    ap.add_argument("--items-dir", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    args.samples = tuple(x for x in args.samples.split(",") if x)
    keys = [k for k in args.models.split(",") if k]
    unknown = [k for k in keys if k not in MODELS]
    if unknown:
        ap.error(f"unknown model keys: {unknown}")
    if args.one:
        return run_one(args.one, args)

    run_dir = Path(args.out) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    folder = resolve_items(args.items, Path(args.out) / "items-cache")
    items, rubrics = read_items(folder), read_rubrics(folder)
    missing = [f"round{r} {p}" for r in items for p in PROTOCOLS if (r, p) not in rubrics]
    if not items or missing:
        print(f"items in {folder}: rounds {sorted(items)}; rubrics missing: {missing}", file=sys.stderr)
        return 2
    reqs = select(items, rubrics, args)
    run = {"run_id": args.run_id, "argv": sys.argv[1:], "pilot": args.pilot, "samples": list(args.samples),
           "models": {k: MODELS[k] for k in keys}, "llm_args": LLM_ARGS, "max_tokens": MAX_TOKENS,
           "items": {f"round{r}": {"rows": len(rows), "sha256": items_digest(rows)} for r, rows in items.items()},
           "rubrics": {f"round{r} {p}": hashlib.sha256(t.encode()).hexdigest() for (r, p), t in rubrics.items()},
           "requests_per_model": len(reqs), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (run_dir / "run.json").write_text(json.dumps(run, indent=1) + "\n")
    print(f"{len(reqs)} requests per model; items {run['items']}", flush=True)
    for key in keys:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--items", args.items, "--items-dir", str(folder),
               "--out", args.out, "--run-id", args.run_id, "--models", key, "--samples", ",".join(args.samples),
               "--one", key]
        if args.pilot:
            cmd += ["--pilot", str(args.pilot)]
        if args.no_ranked:
            cmd.append("--no-ranked")
        t0 = time.time()
        code = subprocess.run(cmd, check=False).returncode
        print(f"{key}: exit {code} after {time.time() - t0:.0f} s", flush=True)
        if args.upload:
            upload(run_dir, args.upload, args.run_id, f"open raters {args.run_id}: {key} (exit {code})")
    text = summary(run_dir, keys, args.pilot)
    (run_dir / "summary.txt").write_text(text + "\n")
    if args.upload:
        upload(run_dir, args.upload, args.run_id, f"open raters {args.run_id}: summary")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
