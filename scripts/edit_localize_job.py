"""The edit localization test (docs/prereg/edit-localize.md) in one Hugging Face Job with one H200.

It runs like `scripts/edit_arms_job.py`, from a source tarball whose src/
and uv.lock are a57e19e's, in the image `eval_edit_arms.VLLM_IMAGE`:

    hf jobs run --flavor h200 --timeout 2h30m --secrets HF_TOKEN \\
        -e READCOST_SHA=<commit> -e RUN_ID=main-1 -e "JOB_ARGS=--hours 2.5" \\
        <image> /bin/sh -lc "$JOB_SCRIPT"

1. checks that src/ and uv.lock are those of a57e19e;
2. fetches the edit test's 60 paragraphs and the 140 new ones at their commits;
3. starts from the replies of the edit test's run `main-1b` (and of any run named with
   `--also-from`), so B's and C's edits and fact checks of the 60 are read, not asked;
4. loads one model at a time: each editor for its edits, then each judge for its fact
   checks and E against B;
5. after each model and at the end, uploads the outputs to the private dataset
   `arclabs561/readcost-labels` under `edit-localize/<run id>/`, without the paragraphs,
   and writes the report (`edit-localize.md`, `edit-localize.json`).
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
import eval_edit_arms as ea
import eval_edit_localize as el

ROOT = el.ROOT
JOB_SCRIPT = job.JOB_SCRIPT.replace("scripts/edit_arms_job.py", "scripts/edit_localize_job.py")
DATASET = job.DATASET
START_FROM = "edit-arms/main-1b"
MIN_CACHED = 0.95   # main-1b left 2 of its 360 B and C edits missing
PASSES = [("editor", ["edits"]), ("judge", ["facts", "EB"])]


def upload(ref: Path, run_id: str, token: str | None, repo_id: str = DATASET, api=None) -> None:
    """The outputs under edit-localize/<run id>/ in a private dataset; stops if the dataset is public."""
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
    if not api.repo_info(repo_id, repo_type="dataset").private:
        raise SystemExit(f"{repo_id} is not private; nothing uploaded")
    api.upload_folder(folder_path=str(ref), path_in_repo=f"edit-localize/{run_id}", repo_id=repo_id,
                      repo_type="dataset", ignore_patterns=["texts.jsonl", "old/*", "new/*"],
                      commit_message=f"edit-localize {run_id}")


def download(folder: str, token: str | None, dest: Path, repo_id: str = DATASET) -> Path:
    """replies.jsonl of an earlier run (``folder`` such as edit-arms/main-1b) into ``dest``."""
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo_id, f"{folder}/replies.jsonl", repo_type="dataset", token=token,
                                local_dir=str(dest)))


def fetch_both(ref: Path, old: Path, new: Path, fetch=ea.fetch) -> list[dict]:
    """The 60 and the 140, the new ones marked, into ref/texts.jsonl."""
    rows = []
    missing = []
    for name, pointers, is_new in (("old", old, False), ("new", new, True)):
        fetch(pointers, ref / name)
        rows += [{**json.loads(x), "new": is_new} for x in (ref / name / "texts.jsonl").read_text().splitlines()]
        missing += json.loads((ref / name / "missing.json").read_text())
    (ref / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (ref / "missing.json").write_text(json.dumps(missing, indent=1))
    return rows


def draw_counts(new: Path, ref: Path) -> str:
    from collections import Counter
    walk = [json.loads(x) for x in (new / "walk.jsonl").read_text().splitlines()] if (new / "walk.jsonl").exists() else []
    missing = json.loads((ref / "missing.json").read_text()) if (ref / "missing.json").exists() else []
    out = Counter(x["outcome"] for x in walk)
    return (f"Continued draw: walked {len(walk)} more repositories ("
            + ", ".join(f"{k}: {v}" for k, v in out.most_common()) + f"); missing at run time {len(missing)}.")


def main(argv: list[str] | None = None, backends=None, uploader=upload, clock=time.time, fetch=ea.fetch,
         verify=ea.verify, analyzer=None, env=None, downloader=download) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--hours", type=float, required=True, help="the job's timeout, in hours")
    ap.add_argument("--backend", choices=sorted(job.BACKENDS), default="server")
    ap.add_argument("--ref", type=Path, default=ROOT / "ref" / "edit-localize")
    ap.add_argument("--old", type=Path, default=el.OLD_POINTERS)
    ap.add_argument("--new", type=Path, default=el.POINTERS)
    ap.add_argument("--workers", type=int, default=128)
    ap.add_argument("--also-from", metavar="RUN_ID", help="also start from this run's replies (a second job)")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args(argv)
    if a.hours > el.HOURS:
        ap.error(f"the plan allows at most {el.HOURS} hours")
    backends = backends or job.BACKENDS
    env = os.environ if env is None else env
    start = clock()
    deadline = start + a.hours * 3600 - job.RESERVE_S
    ref = a.ref
    if ref.exists():
        shutil.rmtree(ref)
    ref.mkdir(parents=True)
    logs = ref / "logs"
    editors, judges = ea.open_models()
    log: dict = {"run_id": a.run_id, "image": ea.VLLM_IMAGE, "backend": a.backend, "hours": a.hours,
                 "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
                 "readcost_sha": env.get("READCOST_SHA"),
                 "models": {m: {k: ea.OPEN_MODELS[m][k] for k in ("revision", "family", "licence")}
                            for m in editors + judges}, "steps": [], "stopped": None, "started_from": []}
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
        log["stopped"] = "src/ or uv.lock is not a57e19e"
        save(final=True)
        return 1
    with tempfile.TemporaryDirectory() as tmp, (ref / "replies.jsonl").open("w") as out:
        for folder in [START_FROM] + ([f"edit-localize/{a.also_from}"] if a.also_from else []):
            got = downloader(folder, env.get("HF_TOKEN"), Path(tmp) / folder.replace("/", "_"))
            text = got.read_text()
            out.write(text if text.endswith("\n") or not text else text + "\n")
            log["started_from"].append({"folder": folder, "replies": len(text.splitlines()), "sha256": ea.sha(text)})
    fetch_both(ref, a.old, a.new, fetch)
    if analyzer is None:
        from readcost import Analyzer, Config
        analyzer = Analyzer(Config())
    client = ea.Client(ref / "replies.jsonl", ask=lambda *x, **k: (None, {"error": "no model loaded"}),
                       call_cap=el.CALL_CAP, count_cost=False, deadline=deadline, clock=clock)
    log["cache_at_start"] = client.calls
    # B's and C's edits of the edit test's paragraphs must come from main-1b's cache. If its prompts
    # no longer match (another readcost, another prompt), stop before any model is loaded.
    paras = el.load(ref)
    fb = el.all_feedback(analyzer, paras)
    old = [(p, ed, arm) for p in paras if not p["new"] for ed in editors for arm in ("B", "C")]
    found = sum(el.edit_of(client, p, ed, arm, fb) is not None for p, ed, arm in old)
    log["old_edits_in_cache"] = {"found": found, "of": len(old)}
    if old and found < MIN_CACHED * len(old):
        log["stopped"] = f"only {found} of {len(old)} of the edit test's B and C edits are in the cache"
        save(final=True)
        return 1
    done_judges = []
    for role, phases in PASSES:
        for model in editors if role == "editor" else judges:
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
            client.ask = backend.ask
            before = client.new_calls
            try:
                got = el.run(ref, client, analyzer, editors, judges, workers=a.workers,
                             call_editors=[model] if role == "editor" else [],
                             call_judges=[model] if role == "judge" else [], phases=phases)
            except ea.CapReached as exc:
                got = {ph: False for ph in phases}
                log["stopped"] = str(exc)
            finally:
                backend.stop()
            step["calls"] = client.new_calls - before
            step["end_s"] = round(clock() - start)
            step["status"] = got
            for ph in phases:
                status[ph] = status.get(ph, True) and bool(got.get(ph))
            if role == "judge" and got.get("facts"):
                done_judges.append(model)
            save()
        else:
            continue
        break
    data = el.collect(ref, client, analyzer, editors, judges)
    res = el.analyse(data, analyzer, editors, judges, judges_done=done_judges)
    calls = {"calls": client.calls, "new": client.new_calls, "cached": client.cached_hits}
    text = el.render(res, status, calls, draw_counts(a.new, ref))
    (ref / "edit-localize.md").write_text(text)
    (ref / "edit-localize.json").write_text(json.dumps({"results": res, "status": status, "calls": calls},
                                                       indent=1, default=str))
    print(text)
    save(final=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
