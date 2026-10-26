# /// script
# dependencies = ["polars>=1"]
# ///
"""Turn eye-tracking interest-area reports into per-text word sequences.

    uv run scripts/reading_time_prep.py ROOT

ROOT/onestop/ia_Paragraph_ordinary.csv  (OneStop, ordinary reading, CC BY 4.0;
    https://osf.io/download/xkgfz/, a zip holding this CSV)
ROOT/provo/Provo_Corpus-Eyetracking_Data.csv  (Provo, CC BY 4.0;
    https://osf.io/download/a32be/)

Writes ROOT/texts.jsonl: one line per text with corpus, text id, words and
the mean total reading time (dwell time, ms) of each word across readers,
counting a skipped word as 0 ms, as Cekini et al. 2026 do.
"""
import json
import sys
from pathlib import Path

import polars as pl


def onestop(path: Path) -> list[dict]:
    df = (pl.scan_csv(path, infer_schema_length=0)
          .filter((pl.col("practice_trial").str.to_lowercase() == "false")
                  & (pl.col("repeated_reading_trial").str.to_lowercase() == "false"))
          .select(["participant_id", "article_batch", "article_id", "difficulty_level", "paragraph_id", "IA_ID", "IA_LABEL",
                   "IA_DWELL_TIME"])
          .with_columns(pl.col("IA_ID").cast(pl.Int64),
                        pl.col("IA_DWELL_TIME").cast(pl.Float64, strict=False).fill_null(0.0))
          .group_by(["article_batch", "article_id", "difficulty_level", "paragraph_id", "IA_ID"])
          .agg(pl.col("IA_LABEL").first(), pl.col("IA_DWELL_TIME").mean().alias("rt"),
               pl.col("participant_id").n_unique().alias("readers"))
          .sort(["article_batch", "article_id", "difficulty_level", "paragraph_id", "IA_ID"])
          .collect())
    out = []
    for key, g in df.group_by(["article_batch", "article_id", "difficulty_level", "paragraph_id"], maintain_order=True):
        out.append({"corpus": "onestop", "id": "/".join(map(str, key)), "article": f"{key[0]}/{key[1]}",
                    "words": g["IA_LABEL"].to_list(), "rt": g["rt"].to_list(), "readers": int(g["readers"].min())})
    return out


def provo(path: Path) -> list[dict]:
    df = (pl.read_csv(path, infer_schema_length=0)
          .select(["Participant_ID", "Text_ID", "Word_Number", "Word", "IA_DWELL_TIME"])
          .with_columns(pl.col("Word_Number").cast(pl.Int64, strict=False),
                        pl.col("IA_DWELL_TIME").cast(pl.Float64, strict=False).fill_null(0.0))
          .drop_nulls("Word_Number")
          .group_by(["Text_ID", "Word_Number"])
          .agg(pl.col("Word").first(), pl.col("IA_DWELL_TIME").mean().alias("rt"),
               pl.col("Participant_ID").n_unique().alias("readers"))
          .sort(["Text_ID", "Word_Number"]))
    out = []
    for key, g in df.group_by("Text_ID", maintain_order=True):
        tid = key[0] if isinstance(key, tuple) else key
        out.append({"corpus": "provo", "id": str(tid), "article": f"provo-{tid}",
                    "words": g["Word"].to_list(), "rt": g["rt"].to_list(), "readers": int(g["readers"].min())})
    return out


def main(root: Path) -> None:
    texts = onestop(root / "onestop/ia_Paragraph_ordinary.csv") + provo(root / "provo/Provo_Corpus-Eyetracking_Data.csv")
    with open(root / "texts.jsonl", "w") as fh:
        fh.writelines(json.dumps(t) + "\n" for t in texts)
    for c in ("onestop", "provo"):
        ts = [t for t in texts if t["corpus"] == c]
        n = sum(len(t["words"]) for t in ts)
        mean = sum(sum(t["rt"]) for t in ts) / n
        print(f"{c}: {len(ts)} texts, {n} word occurrences, mean {mean:.1f} ms/word, "
              f"min readers per text {min(t['readers'] for t in ts)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
