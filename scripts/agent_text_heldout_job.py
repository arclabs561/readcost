"""Stage 2, part 2, the held-out test (docs/prereg/agent-text-search.md), in one Hugging Face Job with one H200.

As `scripts/agent_text_job.py`, with `JOB_ARGS=--hours 1.25`, but: the 100 held-out
paragraphs (`eval/agent-text-heldout/`), R* from `eval/agent-text-search/r_star.json`, an
empty reply cache, three editors, and two judges from families no earlier test used. Each
judge is pinned to the revision the Hub serves when the job starts. A judge that does not
load, or whose first 200 replies fail to parse more than 10% of the time, is replaced by
`ibm-granite/granite-3.3-8b-instruct`, which then answers that judge's calls. Outputs go
under `agent-text-heldout/<run id>/`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_text_job as atj
import edit_arms_job as job
import eval_agent_text as at
import eval_agent_text_heldout as ho
import eval_edit_arms as ea

ROOT = ho.ROOT
JOB_SCRIPT = job.JOB_SCRIPT.replace("scripts/edit_arms_job.py", "scripts/agent_text_heldout_job.py")
FOLDER = "agent-text-heldout"


def upload(ref: Path, run_id: str, token: str | None, repo_id: str = job.DATASET, api=None) -> None:
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
    if not api.repo_info(repo_id, repo_type="dataset").private:
        raise SystemExit(f"{repo_id} is not private; nothing uploaded")
    api.upload_folder(folder_path=str(ref), path_in_repo=f"{FOLDER}/{run_id}", repo_id=repo_id,
                      repo_type="dataset", ignore_patterns=["texts.jsonl", "p*/*"],
                      commit_message=f"{FOLDER} {run_id}")


def hub_revision(model: str, token: str | None) -> str:
    from huggingface_hub import HfApi
    return HfApi(token=token).model_info(model).sha


def failed_share(path: Path, model: str, first: int = ho.FIRST) -> float:
    rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    mine = [r for r in rows if r["model"] == model][:first]
    return sum(r.get("data") is None for r in mine) / len(mine) if mine else 1.0


def main(argv: list[str] | None = None, backends=None, uploader=upload, clock=time.time, fetch=ea.fetch,
         verify=at.verify, analyzer=None, env=None, revision=hub_revision) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--hours", type=float, required=True)
    ap.add_argument("--backend", choices=sorted(job.BACKENDS), default="server")
    ap.add_argument("--ref", type=Path, default=ROOT / "ref" / FOLDER)
    ap.add_argument("--pointers", type=Path, default=ho.POINTERS)
    ap.add_argument("--r-star", type=Path, default=ho.R_STAR)
    ap.add_argument("--workers", type=int, default=128)
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args(argv)
    if a.hours > ho.HOURS:
        ap.error(f"the plan allows at most {ho.HOURS} hours for the held-out test")
    backends = backends or job.BACKENDS
    env = os.environ if env is None else env
    start = clock()
    deadline = start + a.hours * 3600 - job.RESERVE_S
    ref = a.ref
    if ref.exists():
        shutil.rmtree(ref)
    ref.mkdir(parents=True)
    logs = ref / "logs"
    rs = ho.load_r_star(a.r_star)
    log: dict = {"run_id": a.run_id, "image": ea.VLLM_IMAGE, "hours": a.hours, "r_star": rs,
                 "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
                 "readcost_sha": env.get("READCOST_SHA"), "steps": [], "stopped": None, "judges_used": []}
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
    for m, cfg in ho.NEW_MODELS.items():
        ea.OPEN_MODELS[m] = {**cfg, "revision": revision(m, env.get("HF_TOKEN"))}
    log["models"] = {m: {k: ea.OPEN_MODELS[m][k] for k in ("revision", "family", "licence")}
                     for m in ho.EDITORS + ho.JUDGES + [ho.FALLBACK]}
    log["paragraphs"] = atj.fetch_all(ref, (a.pointers,), fetch)
    if analyzer is None:
        from readcost import Analyzer, Config
        analyzer = Analyzer(Config())
    client = ea.Client(ref / "replies.jsonl", ask=lambda *x, **k: (None, {"error": "no model loaded"}),
                       call_cap=ho.CALL_CAP, count_cost=False, deadline=deadline, clock=clock)

    def step(model, role, phases):
        st = {"model": model, "role": role, "phases": phases, "start_s": round(clock() - start)}
        log["steps"].append(st)
        try:
            backend = backends[a.backend](model, logs)
        except Exception as exc:  # noqa: BLE001  a model that does not load leaves its calls missing
            st["error"] = str(exc)[:500]
            save()
            return None
        st["ready_s"] = round(clock() - start)
        client.ask = backend.ask
        before = client.new_calls
        try:
            got = ho.run(ref, client, analyzer, rs, workers=a.workers,
                         call_editors=[model] if role == "editor" else [],
                         call_judges=[model] if role == "judge" else [], phases=phases)
        finally:
            backend.stop()
        st["calls"], st["end_s"], st["status"] = client.new_calls - before, round(clock() - start), got
        save()
        return got

    for ed in ho.EDITORS:
        if clock() >= deadline:
            log["stopped"] = "time limit reached"
            break
        got = step(ed, "editor", ["edits"])
        status["edits"] = status.get("edits", True) and bool(got and got.get("edits"))
    for jdg in ho.JUDGES:
        if clock() >= deadline:
            log["stopped"] = log["stopped"] or "time limit reached"
            break
        got = step(jdg, "judge", ["facts", "read"])
        share = failed_share(ref / "replies.jsonl", jdg)
        if got is None or share > ho.MAX_FAILED:
            log.setdefault("fallbacks", []).append({"judge": jdg, "failed_share": round(share, 3),
                                                    "loaded": got is not None})
            jdg = ho.FALLBACK
            got = step(jdg, "judge", ["facts", "read"])
        log["judges_used"].append(jdg)
        for ph in ("facts", "read"):
            status[ph] = status.get(ph, True) and bool(got and got.get(ph))
    judges = log["judges_used"] or ho.JUDGES
    res = ho.analyse(ref, client, analyzer, rs, judges=judges)
    complete = all(status.get(ph) for ph in ("edits", "facts", "read")) and len(judges) == len(ho.JUDGES)
    calls = {"calls": client.calls, "new": client.new_calls}
    walk = [json.loads(x) for x in (a.pointers / "walk.jsonl").read_text().splitlines()] \
        if (a.pointers / "walk.jsonl").exists() else []
    from collections import Counter
    draw_line = (f"Held-out draw: walked {len(walk)} more repositories ("
                 + ", ".join(f"{k}: {v}" for k, v in Counter(x["outcome"] for x in walk).most_common()) + ").")
    text = ho.render(res, status, calls, rs, draw_line)
    if not complete:
        text += "\nNot every phase finished for two judges, so no decision is made.\n"
        res["decision"]["replace"] = False
    (ref / "heldout.md").write_text(text)
    (ref / "heldout.json").write_text(json.dumps({"results": res, "status": status, "calls": calls,
                                                  "complete": complete}, indent=1, default=str))
    print(text)
    save(final=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
