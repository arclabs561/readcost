"""The edit-arms test on open-weight models, in one Hugging Face Job with one H200.

The plan is docs/prereg/edit-arms.md, with its amendment of 19 November
2026. The job runs in the image `eval_edit_arms.VLLM_IMAGE`, from a source
tarball of this repository. The pilot, started with the `hf` command line:

    hf jobs run --flavor h200 --timeout 90m --secrets HF_TOKEN \
        -e READCOST_SHA=<commit> -e RUN_ID=pilot-1 -e "JOB_ARGS=--pilot --hours 1.5" \
        <image> /bin/sh -lc "$JOB_SCRIPT"

where JOB_SCRIPT is `JOB_SCRIPT` below. The full run uses `--timeout 4h`
and `JOB_ARGS=--hours 4`.

What it does:

1. checks that src/ and uv.lock are those of a57e19e (`eval_edit_arms.verify`);
2. fetches the 60 paragraphs from GitHub at their commits (the first 5 with
   `--pilot`);
3. loads one model at a time with `vllm serve` (or vLLM's offline `LLM`
   with `--backend offline`, which needs vllm importable in this
   environment), runs that model's calls, and stops it. The full run makes
   three passes: each editor's edits for B, C and D; each judge's B
   against C; each judge's other phases. The pilot makes two, loading each
   judge once;
4. after each model and at the end, writes `run.json` (timings, calls,
   failures per model) and `status.json`, and uploads the outputs to the
   private dataset `arclabs561/readcost-labels` under `edit-arms/<run id>/`
   (token from HF_TOKEN). The paragraphs themselves are not uploaded;
5. writes the report (`edit-arms.md`, `edit-arms.json`), or for the pilot
   only counts, failures and timings (`pilot.json`).

The job's own clock stops new calls 15 minutes before `--hours` is up, so
the report and the upload finish inside the job's timeout.

`--resume-from RUN_ID` (the prereg's amendment of 20 November 2026) starts
from that run's replies in the dataset instead of an empty cache. A phase
that run finished for a model is not run again for it: its replies are read
from the cache ("served from cache") and nothing in it is asked, not even a
call that failed twice. A model with nothing left to ask is not loaded. The
original phases' call cap is `RESUMED_CALL_CAP`, and `--hours` may be at
most `RESUMED_HOURS`. The outputs, under the new run id, hold the replies of
both runs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_edit_arms as ea
from eval_edit_arms import sha

ROOT = Path(__file__).resolve().parent.parent
# The job's shell command: the source at READCOST_SHA, readcost and its pins from uv.lock (the
# `verify` extra brings huggingface_hub), the spaCy model, then this script. vLLM is the image's.
JOB_SCRIPT = (
    'set -eu; cd /tmp; '
    'curl -fsSL "https://codeload.github.com/arclabs561/readcost/tar.gz/$READCOST_SHA" | tar xz; '
    'cd "readcost-$READCOST_SHA"; '
    'python3 -m pip install -q uv==0.13.9; '
    'uv sync --locked --no-dev --group eval --extra verify --python python3; '
    'uv run --no-sync readcost setup; '
    'exec uv run --no-sync python scripts/edit_arms_job.py --run-id "$RUN_ID" $JOB_ARGS')
DATASET = "arclabs561/readcost-labels"
PILOT_PARAGRAPHS = 5
RESERVE_S = 15 * 60          # stop new calls this long before the job's hours are up
READY_TIMEOUT_S = 45 * 60    # download, load and compile one model
JUDGE_REST = ["facts", "BA", "CA", "DB", "factsD", "DC", "DA"]
EDIT_PHASES = ["edits", "editsD"]
UPLOAD_SKIP = ["texts.jsonl"]   # the paragraphs belong to their authors; the job refetches them
# The amendment of 20 November 2026, for resuming main-1: the original phases' call cap, and the job's hours.
RESUMED_CALL_CAP = 7500
RESUMED_HOURS = 1.5


def passes(pilot: bool) -> list[tuple[str, list[str]]]:
    """(role, phases) in order. The full run loads each judge twice, so B against C finishes first."""
    if pilot:
        return [("editor", EDIT_PHASES), ("judge", ["BC"] + JUDGE_REST)]
    return [("editor", EDIT_PHASES), ("judge", ["BC"]), ("judge", JUDGE_REST)]


class VllmServer:
    """`vllm serve` for one model on this machine; ``ask`` talks to it over HTTP."""

    def __init__(self, model: str, logs: Path, port: int = 8000, vllm: str = "vllm",
                 ready_timeout: float = READY_TIMEOUT_S):
        self.model, self.port = model, port
        self.log_path = logs / f"vllm-{model.replace('/', '__')}.log"
        env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONHOME")}
        cmd = [vllm, "serve", *ea.serve_args(model), "--host", "127.0.0.1", "--port", str(port)]
        logs.mkdir(parents=True, exist_ok=True)
        self.log = self.log_path.open("a")
        self.log.write("$ " + " ".join(cmd) + "\n")
        self.log.flush()
        self.proc = subprocess.Popen(cmd, stdout=self.log, stderr=subprocess.STDOUT, env=env)
        self._wait(ready_timeout)
        self.ask = ea.openai_ask(f"http://127.0.0.1:{port}/v1", {model: ea.OPEN_MODELS[model]["extra"]})

    def _wait(self, timeout: float) -> None:
        until = time.time() + timeout
        while time.time() < until:
            if self.proc.poll() is not None:
                raise RuntimeError(f"vllm serve exited with {self.proc.returncode}; see {self.log_path.name}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=5) as r:
                    if r.status == 200:
                        return
            except OSError:
                pass
            time.sleep(5)
        self.stop()
        raise RuntimeError(f"vllm serve not ready after {timeout:.0f} s; see {self.log_path.name}")

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.log.close()


class OfflineEngine:
    """vLLM's offline `LLM` in this process. Freeing GPU memory between models is best effort."""

    def __init__(self, model: str, logs: Path, **_kw):
        self.ask = ea.open_backend("offline", model)

    def stop(self) -> None:
        import gc
        self.ask.close()
        del self.ask
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:  # no torch or no GPU: nothing to free
            pass


BACKENDS = {"server": VllmServer, "offline": OfflineEngine}


def upload(ref: Path, run_id: str, token: str | None, repo_id: str = DATASET, api=None) -> None:
    """The outputs under edit-arms/<run id>/ in a private dataset; stops if the dataset is public."""
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
    api.create_repo(repo_id, repo_type="dataset", private=True, exist_ok=True)
    if not api.repo_info(repo_id, repo_type="dataset").private:
        raise SystemExit(f"{repo_id} is not private; nothing uploaded")
    api.upload_folder(folder_path=str(ref), path_in_repo=f"edit-arms/{run_id}", repo_id=repo_id,
                      repo_type="dataset", ignore_patterns=UPLOAD_SKIP,
                      commit_message=f"edit-arms {run_id}")


def download(run_id: str, token: str | None, dest: Path, repo_id: str = DATASET) -> Path:
    """replies.jsonl and run.json of an earlier run, from the dataset, into ``dest``; returns their folder."""
    from huggingface_hub import hf_hub_download
    for name in ("replies.jsonl", "run.json"):
        hf_hub_download(repo_id, f"edit-arms/{run_id}/{name}", repo_type="dataset", token=token,
                        local_dir=str(dest))
    return dest / "edit-arms" / run_id


def finished(prior: dict) -> set[tuple[str, str]]:
    """(model, phase) pairs that an earlier run's steps finished."""
    return {(s["model"], ph) for s in prior.get("steps", []) for ph, ok in (s.get("status") or {}).items() if ok}


class CacheOnly:
    """A client's cache without its model: a reply not in the cache is None, and nothing is asked,
    written or counted toward the caps. ``wanted`` collects the keys that would have been asked.
    With ``count``, a cached reply counts as served from cache."""

    def __init__(self, client: ea.Client, count: bool = True):
        self.client, self.count, self.wanted = client, count, set()

    def __getattr__(self, name):
        return getattr(self.client, name)

    def __call__(self, model: str, system: str | None, prompt: str, schema: dict) -> dict | None:
        k = self.client.key(model, system, prompt)
        with self.client.lock:
            row = self.client.ok.get(k)
            if row is None:
                self.wanted.add(k)
                return None
            if self.count:
                self.client.cached_hits += 1
            return row["data"]


def reply_counts(path: Path) -> dict:
    """{model: {"replies", "failed", "errors"}} over the reply cache."""
    out: dict = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        row = json.loads(line)
        c = out.setdefault(row["model"], {"replies": 0, "failed": 0, "errors": Counter()})
        c["replies"] += 1
        if row.get("data") is None:
            c["failed"] += 1
            c["errors"][(row.get("meta") or {}).get("error") or "?"] += 1
    return {k: {**v, "errors": dict(v["errors"])} for k, v in out.items()}


def main(argv: list[str] | None = None, backends=None, uploader=upload, clock=time.time, fetch=ea.fetch,
         verify=ea.verify, analyzer=None, env=None, downloader=download) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--pilot", action="store_true", help=f"the first {PILOT_PARAGRAPHS} paragraphs, no win rates")
    ap.add_argument("--hours", type=float, required=True, help="the job's timeout, in hours")
    ap.add_argument("--backend", choices=sorted(BACKENDS), default="server")
    ap.add_argument("--mistral-fallback", action="store_true",
                    help="Ministral 3 14B in place of Mistral Small 4 (the prereg's fallback)")
    ap.add_argument("--ref", type=Path, default=ROOT / "ref" / "edit-arms")
    ap.add_argument("--pointers", type=Path, default=ROOT / "eval" / "edit-arms")
    ap.add_argument("--workers", type=int, default=128, help="calls in flight at once")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--resume-from", metavar="RUN_ID",
                    help="start from that run's replies in the dataset (the prereg's amendment of 20 November)")
    a = ap.parse_args(argv)
    if a.resume_from and a.pilot:
        ap.error("--resume-from is for a full run, not the pilot")
    if a.resume_from == a.run_id:
        ap.error("a resumed run needs a new --run-id")
    if a.resume_from and a.hours > RESUMED_HOURS:
        ap.error(f"a resumed run may take at most {RESUMED_HOURS} hours")
    backends = backends or BACKENDS
    env = os.environ if env is None else env
    start = clock()
    deadline = start + a.hours * 3600 - RESERVE_S
    ref = a.ref
    if ref.exists():
        shutil.rmtree(ref)       # every run starts from an empty reply cache
    ref.mkdir(parents=True)
    logs = ref / "logs"
    editors, judges = ea.open_models(fallback=a.mistral_fallback)
    log: dict = {"run_id": a.run_id, "pilot": a.pilot, "image": ea.VLLM_IMAGE, "backend": a.backend,
                 "hours": a.hours, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
                 "readcost_sha": env.get("READCOST_SHA"),
                 "models": {m: {k: ea.OPEN_MODELS[m][k] for k in ("revision", "family", "licence")}
                            for m in editors + judges},
                 "steps": [], "stopped": None}
    status: dict = {}
    done: set = set()
    if a.resume_from:
        with tempfile.TemporaryDirectory() as tmp:
            got = downloader(a.resume_from, env.get("HF_TOKEN"), Path(tmp))
            prior = json.loads((got / "run.json").read_text())
            shutil.copyfile(got / "replies.jsonl", ref / "replies.jsonl")
        models = {m: v["revision"] for m, v in log["models"].items()}
        if {m: v.get("revision") for m, v in prior.get("models", {}).items()} != models:
            raise SystemExit(f"{a.resume_from} ran other models or revisions; not resumed")
        done = finished(prior)
        log["resumed_from"] = {"run_id": a.resume_from, "readcost_sha": prior.get("readcost_sha"),
                               "replies": len((ref / "replies.jsonl").read_text().splitlines()),
                               "replies_sha256": sha((ref / "replies.jsonl").read_text()),
                               "finished": len(done)}

    def save(final: bool = False) -> None:
        log["seconds"] = round(clock() - start)
        log["replies"] = reply_counts(ref / "replies.jsonl")
        (ref / "run.json").write_text(json.dumps(log, indent=1))
        (ref / "status.json").write_text(json.dumps({"phases": status, "final": final}, indent=1))
        if a.no_upload:
            return
        try:
            uploader(ref, a.run_id, env.get("HF_TOKEN"))
        except SystemExit:
            raise
        except Exception as exc:  # an upload that fails is tried again after the next model
            log.setdefault("upload_errors", []).append(str(exc)[:300])

    if verify() != 0:
        log["stopped"] = "src/ or uv.lock is not a57e19e"
        save(final=True)
        return 1
    fetch(a.pointers, ref)
    if a.pilot:
        rows = (ref / "texts.jsonl").read_text().splitlines()[:PILOT_PARAGRAPHS]
        (ref / "texts.jsonl").write_text("".join(r + "\n" for r in rows))
    if analyzer is None:
        from readcost import Analyzer, Config
        analyzer = Analyzer(Config())
    client = ea.Client(ref / "replies.jsonl", ask=lambda *x, **k: (None, {"error": "no model loaded"}),
                       call_cap=RESUMED_CALL_CAP if a.resume_from else ea.CALL_CAP,
                       count_cost=False, deadline=deadline, clock=clock)

    def run_step(c, model, role, phases):
        return ea.run(ref, c, analyzer, editors, judges, workers=a.workers,
                      call_editors=[model] if role == "editor" else [],
                      call_judges=[model] if role == "judge" else [], phases=phases)

    for role, phases in passes(a.pilot):
        for model in editors if role == "editor" else judges:
            if clock() >= deadline:
                log["stopped"] = log["stopped"] or "time limit reached"
                break
            step = {"model": model, "role": role, "phases": phases, "start_s": round(clock() - start)}
            log["steps"].append(step)
            carried = [ph for ph in phases if (model, ph) in done]
            left = [ph for ph in phases if ph not in carried]
            if carried:
                # Finished by the earlier run: read from the cache, ask nothing.
                view = CacheOnly(client)
                got = run_step(view, model, role, carried)
                step["status"] = got
                step["carried_from"] = a.resume_from
                step["not_asked"] = len(view.wanted)
                for ph in carried:
                    status[ph] = status.get(ph, True) and bool(got.get(ph))
            if left and a.resume_from:
                plan = CacheOnly(client, count=False)
                planned = run_step(plan, model, role, left)
                step["planned_calls"] = len(plan.wanted)
                if not plan.wanted:
                    step["status"] = {**step.get("status", {}), **planned}
                    for ph in left:
                        status[ph] = status.get(ph, True) and bool(planned.get(ph))
                    left = []
            if not left:
                step["loaded"] = False
                step["end_s"] = round(clock() - start)
                save()
                continue
            try:
                backend = backends[a.backend](model, logs)
            except Exception as exc:  # a model that does not load leaves its calls missing
                step["error"] = str(exc)[:500]
                for ph in left:
                    status[ph] = False
                save()
                continue
            step["ready_s"] = round(clock() - start)
            client.ask = backend.ask
            before = client.new_calls
            try:
                got = run_step(client, model, role, left)
            finally:
                backend.stop()
            step["calls"] = client.new_calls - before
            step["end_s"] = round(clock() - start)
            step["status"] = {**step.get("status", {}), **got}
            for ph in left:
                status[ph] = status.get(ph, True) and bool(got.get(ph))
            save()
        else:
            continue
        break

    if a.pilot:
        (ref / "pilot.json").write_text(json.dumps({"steps": log["steps"], "replies": reply_counts(ref / "replies.jsonl"),
                                                    "status": status}, indent=1))
    else:
        text = ea.report(ref, ref / "edit-arms.json", client=client, analyzer=analyzer, pointers=a.pointers,
                         editors=editors, judges=judges, count_cost=False)
        (ref / "edit-arms.md").write_text(text)
        print(text)
    save(final=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
