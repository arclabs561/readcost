"""Stage 3 (docs/prereg/agent-text-dynamic.md) in one Hugging Face Job with one H200.

It runs like `scripts/edit_localize_job.py`, from a source tarball of this
repository at the plan's commit, in the image `eval_edit_arms.VLLM_IMAGE`,
with `JOB_ARGS=--hours 1.5`. As `scripts/agent_text_job.py`, but:

1. checks that src/ and uv.lock are those of e1871db (0.4.0);
2. fetches the localization control's 200 paragraphs at their commits;
3. starts from the search's replies (`agent-text-search/main-1`), and stops before
   loading a model if fewer than 95% of the edits expected in the cache are found;
4. loads one model at a time: each editor for its edits; each judge for the
   calibration and fact checks; each judge for the screen; each judge for the
   confirmation and audit set. Judges answer with token log probabilities;
5. uploads the outputs to the private dataset under `agent-text-dynamic/<run id>/`,
   without the paragraphs, and writes the report (`dynamic.md`, `dynamic.json`).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_arms_job as job
import eval_agent_text as at
import eval_agent_text_dynamic as dy
import eval_edit_arms as ea

ROOT = at.ROOT
JOB_SCRIPT = job.JOB_SCRIPT.replace("scripts/edit_arms_job.py", "scripts/agent_text_dynamic_job.py")
DATASET = job.DATASET
START_FROM = "agent-text-search/main-1"
FOLDER = "agent-text-dynamic"
MIN_ANCHORS = 0.95
PASSES = [("editor", dy.EDITORS, ["edits"]), ("judge", dy.JUDGES, ["calib", "facts"]),
          ("judge", dy.JUDGES, ["screen"]), ("judge", dy.JUDGES, ["confirm"])]


def upload(ref: Path, run_id: str, token: str | None, repo_id: str = DATASET, api=None) -> None:
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
    if not api.repo_info(repo_id, repo_type="dataset").private:
        raise SystemExit(f"{repo_id} is not private; nothing uploaded")
    api.upload_folder(folder_path=str(ref), path_in_repo=f"{FOLDER}/{run_id}", repo_id=repo_id,
                      repo_type="dataset", ignore_patterns=["texts.jsonl", "p*/*"],
                      commit_message=f"{FOLDER} {run_id}")


def download(folder: str, token: str | None, dest: Path, repo_id: str = DATASET) -> Path:
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo_id, f"{folder}/replies.jsonl", repo_type="dataset", token=token,
                                local_dir=str(dest)))


def fetch_all(ref: Path, pointers=at.POINTER_FILES, fetch=ea.fetch) -> int:
    rows, missing = [], []
    for i, ptr in enumerate(pointers):
        fetch(ptr, ref / f"p{i}")
        rows += (ref / f"p{i}" / "texts.jsonl").read_text().splitlines()
        missing += json.loads((ref / f"p{i}" / "missing.json").read_text())
    (ref / "texts.jsonl").write_text("".join(r + "\n" for r in rows))
    (ref / "missing.json").write_text(json.dumps(missing, indent=1))
    return len(rows)


def with_logprobs(backend, model: str):
    """The backend's ask, or for a local vLLM server an ask that also returns token log probabilities."""
    port = getattr(backend, "port", None)
    if port is None:
        return backend.ask
    return dy.logprob_ask(f"http://127.0.0.1:{port}/v1", {model: ea.OPEN_MODELS[model]["extra"]})


def main(argv: list[str] | None = None, backends=None, uploader=upload, clock=time.time, fetch=ea.fetch,
         verify=at.verify, analyzer=None, env=None, downloader=download, pointers=at.POINTER_FILES) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--hours", type=float, required=True)
    ap.add_argument("--backend", choices=sorted(job.BACKENDS), default="server")
    ap.add_argument("--ref", type=Path, default=ROOT / "ref" / FOLDER)
    ap.add_argument("--workers", type=int, default=128)
    ap.add_argument("--also-from", metavar="RUN_ID", help="also start from this run's replies (a second job)")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args(argv)
    if a.hours > dy.HOURS:
        ap.error(f"the plan allows at most {dy.HOURS} hours for one job")
    backends = backends or job.BACKENDS
    env = os.environ if env is None else env
    start = clock()
    deadline = start + a.hours * 3600 - job.RESERVE_S
    ref = a.ref
    if ref.exists():
        shutil.rmtree(ref)
    ref.mkdir(parents=True)
    logs = ref / "logs"
    models = dy.EDITORS + dy.JUDGES
    log: dict = {"run_id": a.run_id, "image": ea.VLLM_IMAGE, "hours": a.hours,
                 "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
                 "readcost_sha": env.get("READCOST_SHA"),
                 "models": {m: {k: ea.OPEN_MODELS[m][k] for k in ("revision", "family", "licence")} for m in models},
                 "steps": [], "stopped": None, "started_from": []}
    status: dict = {}

    def save(final: bool = False) -> None:
        log["seconds"] = round(clock() - start)
        log["replies"] = job.reply_counts(ref / "replies.jsonl")
        (ref / "run.json").write_text(json.dumps(log, indent=1))
        (ref / "status.json").write_text(json.dumps({"phases": status, "final": final}, indent=1))
        if a.no_upload:
            return
        try:
            uploader(ref, a.run_id, env.get("HF_TOKEN"))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001  an upload that fails is tried again after the next model
            log.setdefault("upload_errors", []).append(str(exc)[:300])

    if verify() != 0:
        log["stopped"] = "src/ or uv.lock is not e1871db"
        save(final=True)
        return 1
    with tempfile.TemporaryDirectory() as tmp, (ref / "replies.jsonl").open("w") as out:
        for folder in [START_FROM] + ([f"{FOLDER}/{a.also_from}"] if a.also_from else []):
            text = downloader(folder, env.get("HF_TOKEN"), Path(tmp) / folder.replace("/", "_")).read_text()
            out.write(text if text.endswith("\n") or not text else text + "\n")
            log["started_from"].append({"folder": folder, "replies": len(text.splitlines()), "sha256": ea.sha(text)})
    log["paragraphs"] = fetch_all(ref, pointers, fetch)
    if analyzer is None:
        from readcost import Analyzer, Config
        analyzer = Analyzer(Config())
    client = ea.Client(ref / "replies.jsonl", ask=lambda *x, **k: (None, {"error": "no model loaded"}),
                       call_cap=dy.CALL_CAP, count_cost=False, deadline=deadline, clock=clock)
    log["cache_at_start"] = client.calls
    pl = dy.plan(analyzer, ref)
    log["plan"] = {"prompts": len(pl["prompts"]), "audit": len(pl["audit"]), "train": len(pl["train"]),
                   "calib": len(pl["calib"]),
                   "groups": {sp: {k: len(v) for k, v in g.items()} for sp, g in pl["groups"].items()}}
    expected = ([(ed, pl["prompts"][(pid, "seed", "v0")]) for pid in pl["main"] if (pid, "seed", "v0") in pl["prompts"]
                 for ed in dy.EDITORS]
                + [(ed, pl["prompts"][(pid, "note", "c1")]) for pid in pl["rules"] for ed in dy.EDITORS])
    found = sum(at.edit_text(client, ed, pr) is not None for ed, pr in expected)
    log["expected_in_cache"] = {"found": found, "of": len(expected)}
    if found < MIN_ANCHORS * len(expected):
        log["stopped"] = f"only {found} of {len(expected)} expected edits in the cache"
        save(final=True)
        return 1
    for role, models_, phases in PASSES:
        for model in models_:
            if clock() >= deadline:
                log["stopped"] = log["stopped"] or "time limit reached"
                break
            step = {"model": model, "role": role, "phases": phases, "start_s": round(clock() - start)}
            log["steps"].append(step)
            try:
                backend = backends[a.backend](model, logs)
            except Exception as exc:  # noqa: BLE001  a model that does not load leaves its calls missing
                step["error"] = str(exc)[:500]
                for ph in phases:
                    status[ph] = False
                save()
                continue
            step["ready_s"] = round(clock() - start)
            client.ask = with_logprobs(backend, model)
            before = client.new_calls
            try:
                got = dy.run(ref, client, analyzer, workers=a.workers,
                             call_editors=[model] if role == "editor" else [],
                             call_judges=[model] if role == "judge" else [], phases=phases)
            finally:
                backend.stop()
            step["calls"] = client.new_calls - before
            step["end_s"] = round(clock() - start)
            step["status"] = got
            for ph in phases:
                status[ph] = status.get(ph, True) and bool(got.get(ph))
            save()
        else:
            continue
        break
    res = dy.analyse(client, analyzer, pl)
    complete = all(status.get(ph) for ph in ("edits", "calib", "facts", "screen", "confirm"))
    calls = {"calls": client.calls, "new": client.new_calls}
    text = dy.report(res, status, calls)
    if not complete:
        text += "\nNot every phase finished, so no choice is made.\n"
        for r in res["species"].values():
            r["winner"] = None
    (ref / "dynamic.md").write_text(text)
    (ref / "dynamic.json").write_text(json.dumps({"results": res, "status": status, "calls": calls,
                                                 "complete": complete}, indent=1, default=str))
    print(text)
    save(final=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
