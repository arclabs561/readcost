"""Why the stage 2 search could not tell its candidates apart: noise in the cached judgements.

Runs in a CPU Hugging Face Job from the cached replies of `agent-text-search/main-1`; it asks
no model. Writes `noise.json` and `noise.md` and uploads them under `diagnostics/search-noise/`.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_text_job as atj
import eval_agent_text as at
import eval_edit_arms as ea

DATASET = "arclabs561/readcost-labels"
Z = 1.96 + 0.8416      # two-sided 5%, 80% power
DELTA = 0.03


def fail(*_a, **_k):
    return None, {"error": "no model in a diagnosis"}


def outcome_x_c(client, judge, e, c):
    p0, p1 = at.pick(client, judge, e, c), at.pick(client, judge, c, e)
    first = {"1": "X", "2": "C", "tie": "tie"}.get(p0) if p0 else None
    second = {"1": "C", "2": "X", "tie": "tie"}.get(p1) if p1 else None
    return ea.outcome(first, second, "X", "C")


def main() -> int:
    from huggingface_hub import HfApi, hf_hub_download
    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    if not api.repo_info(DATASET, repo_type="dataset").private:
        raise SystemExit(f"{DATASET} is not private")
    ref = Path("/tmp/diag")
    ref.mkdir(parents=True, exist_ok=True)
    got = Path(hf_hub_download(DATASET, "agent-text-search/main-1/replies.jsonl", repo_type="dataset",
                               token=token, local_dir=str(ref / "dl")))
    (ref / "replies.jsonl").write_text(got.read_text())
    atj.fetch_all(ref)
    from readcost import Analyzer, Config
    analyzer = Analyzer(Config())
    client = ea.Client(ref / "replies.jsonl", ask=fail, count_cost=False)
    pl = at.search_plan(analyzer, ref)
    tx = pl["texts"]
    eds, js = at.EDITORS, at.JUDGES

    # Per unit and candidate: change, read, utility; per judge: its own change call and outcome.
    vals: dict = {}
    per_judge_change: dict = {}
    per_judge_out: dict = {}
    for (pid, sp, cand), pr in pl["prompts"].items():
        for ed in eds:
            e = at.edit_text(client, ed, pr)
            if e is None:
                continue
            c = at.anchor(client, ed, tx[pid])
            ch, rd = at.score(client, ed, pr, tx[pid], js)
            vals[(pid, ed, sp, cand)] = (ch, rd)
            for j in js:
                f = at.facts_of(client, j, tx[pid], e)
                if f:
                    per_judge_change[(pr, ed, j)] = bool(f["lost"] or f["changed"])
                if c is not None:
                    per_judge_out[(pr, ed, j)] = outcome_x_c(client, j, e, c)

    res: dict = {"units": len(vals), "species": {}}
    sds, rhos, sd_diffs = [], [], []
    for sp in ["scope", *at.FIX_CANDIDATES]:
        pids = pl["units"].get(sp, set())
        seed = {(pid, ed): vals.get((pid, ed, "seed", "v0")) for pid in pids for ed in eds}
        rows = {}
        for cand in ("v1", "v2", "v3"):
            gain = {"change": {}, "read": {}, "utility": {}}
            pairs_u = []
            for pid in pids:
                for ed in eds:
                    a, b = vals.get((pid, ed, sp, cand)), seed.get((pid, ed))
                    if not a or not b:
                        continue
                    if a[0] is not None and b[0] is not None:
                        gain["change"][(pid, ed)] = a[0] - b[0]
                    if a[1] is not None and b[1] is not None:
                        gain["read"][(pid, ed)] = a[1] - b[1]
                    if None not in a and None not in b:
                        ua, ub = a[1] - a[0], b[1] - b[0]
                        gain["utility"][(pid, ed)] = ua - ub
                        pairs_u.append((ua, ub))
            row = {k: ea.cluster_boot(v) if v else None for k, v in gain.items()}
            row["units"] = len(pairs_u)
            if len(pairs_u) > 2:
                ua = [p[0] for p in pairs_u]
                ub = [p[1] for p in pairs_u]
                d = [x - y for x, y in pairs_u]
                sd_u, sd_d = statistics.pstdev(ua + ub), statistics.pstdev(d)
                rho = statistics.correlation(ua, ub) if statistics.pstdev(ua) and statistics.pstdev(ub) else None
                row.update({"sd_utility": round(sd_u, 4), "sd_paired_diff": round(sd_d, 4),
                            "rho": round(rho, 3) if rho is not None else None})
                sds.append(sd_u)
                sd_diffs.append(sd_d)
                if rho is not None:
                    rhos.append(rho)
            rows[cand] = row
        res["species"][sp] = rows
    sd_u = statistics.median(sds) if sds else 0.0
    sd_d = statistics.median(sd_diffs) if sd_diffs else 0.0
    res["power"] = {"median_sd_utility": round(sd_u, 4), "median_sd_paired_diff": round(sd_d, 4),
                    "median_rho": round(statistics.median(rhos), 3) if rhos else None,
                    "units_paired_for_0.03": round((Z * sd_d / DELTA) ** 2),
                    "units_per_arm_unpaired_for_0.03": round(2 * (Z * sd_u / DELTA) ** 2),
                    "note": "units are paragraph-editor pairs; clustering by paragraph would raise both"}

    # Splits: inconsistent picks across the two orders, per judge.
    split = {}
    for j in js:
        oc = [o for (pr, ed, jj), o in per_judge_out.items() if jj == j and o is not None]
        split[j] = {"judgements": len(oc), "split_share": round(sum(o == "split" for o in oc) / len(oc), 3) if oc else None,
                    "outcomes": dict(Counter(oc))}
    allo = [o for o in per_judge_out.values() if o is not None]
    split["all"] = {"judgements": len(allo),
                    "split_share": round(sum(o == "split" for o in allo) / len(allo), 3) if allo else None}
    res["splits_vs_C"] = split

    # Agreement between the two judges.
    j1, j2 = js
    both_ch = [(per_judge_change[(pr, ed, j1)], per_judge_change[(pr, ed, j2)])
               for (pr, ed, j) in per_judge_change if j == j1 and (pr, ed, j2) in per_judge_change]
    nch = max(1, len(both_ch))
    agree_ch = sum(a == b for a, b in both_ch) / nch
    p1 = sum(a for a, _ in both_ch) / nch
    p2 = sum(b for _, b in both_ch) / nch
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    norm = {"split": "tie"}
    both_o = [(norm.get(per_judge_out[(pr, ed, j1)], per_judge_out[(pr, ed, j1)]),
               norm.get(per_judge_out[(pr, ed, j2)], per_judge_out[(pr, ed, j2)]))
              for (pr, ed, j) in per_judge_out if j == j1 and per_judge_out.get((pr, ed, j1))
              and per_judge_out.get((pr, ed, j2))]
    agree_o = sum(a == b for a, b in both_o) / len(both_o) if both_o else None
    ca, cb = Counter(a for a, _ in both_o), Counter(b for _, b in both_o)
    n = len(both_o)
    pe_o = sum(ca[k] * cb[k] for k in ca) / (n * n) if n else None
    res["judge_agreement"] = {
        "change": {"edits": len(both_ch), "agree": round(agree_ch, 3), "rate_" + j1: round(p1, 3),
                   "rate_" + j2: round(p2, 3), "kappa": round((agree_ch - pe) / (1 - pe), 3) if pe < 1 else None},
        "readability_vs_C": {"edits": n, "agree": round(agree_o, 3) if agree_o is not None else None,
                             "kappa": round((agree_o - pe_o) / (1 - pe_o), 3) if pe_o is not None and pe_o < 1 else None,
                             j1: dict(ca), j2: dict(cb)}}

    out = Path("/tmp/diag-out")
    out.mkdir(exist_ok=True)
    (out / "noise.json").write_text(json.dumps(res, indent=1, default=str))
    lines = ["## Search noise", "", f"Units scored: {res['units']}.", "",
             "| Species | Cand | Units | Gain in utility [95%] | Gain in change | Gain in read | SD diff | rho |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]

    def f(e):
        return "—" if e is None else "{:+.3f} [{:+.3f}, {:+.3f}]".format(*e)
    for sp, rows in res["species"].items():
        for cand, r in rows.items():
            lines.append(f"| {sp} | {cand} | {r['units']} | {f(r['utility'])} | {f(r['change'])} | {f(r['read'])} | "
                         f"{r.get('sd_paired_diff')} | {r.get('rho')} |")
    lines += ["", "Power: " + json.dumps(res["power"]), "", "Splits against C: " + json.dumps(res["splits_vs_C"]),
              "", "Judge agreement: " + json.dumps(res["judge_agreement"])]
    (out / "noise.md").write_text("\n".join(lines) + "\n")
    print((out / "noise.md").read_text())
    api.upload_folder(folder_path=str(out), path_in_repo="diagnostics/search-noise", repo_id=DATASET,
                      repo_type="dataset", commit_message="diagnostics: search noise")
    return 0


if __name__ == "__main__":
    sys.exit(main())
