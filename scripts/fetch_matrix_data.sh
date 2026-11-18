#!/usr/bin/env bash
# Download one part of the dataset matrix (scripts/dataset_matrix.py) under ROOT.
#
#     bash scripts/fetch_matrix_data.sh PART ROOT
#
# PART is one of the names in the `matrix` job of .github/workflows/eval.yml.
# Hugging Face, OSF and ugent.be must be reachable (they are from GitHub
# Actions). Repositories on GitHub are fetched at a pinned commit. Each part
# ends by writing ROOT/PART/SHA256SUMS, which the derived dataset's manifest
# records, so a later reader can tell whether the source changed.
set -euo pipefail

part="$1"
root="$2"
dest="$root/$part"
mkdir -p "$dest"
hub="https://huggingface.co/datasets"
pq="resolve/refs%2Fconvert%2Fparquet"

get() { curl -fsSL --retry 3 -o "$1" "$2"; }

github() {  # github OWNER/REPO COMMIT DIR
  mkdir -p "$3"
  curl -fsSL --retry 3 "https://codeload.github.com/$1/tar.gz/$2" | tar -xz -C "$3" --strip-components=1
}

case "$part" in
  helpsteer2)
    get "$dest/train.parquet" "$hub/nvidia/HelpSteer2/$pq/default/train/0000.parquet"
    get "$dest/validation.parquet" "$hub/nvidia/HelpSteer2/$pq/default/validation/0000.parquet"
    ;;
  helpsteer3)
    mkdir -p "$dest/feedback" "$dest/edit"
    for split in train validation; do
      get "$dest/feedback/$split.parquet" "$hub/nvidia/HelpSteer3/$pq/feedback/$split/0000.parquet"
      get "$dest/edit/$split.parquet" "$hub/nvidia/HelpSteer3/$pq/edit/$split/0000.parquet"
    done
    ;;
  summeval)
    get "$dest/test.parquet" "$hub/mteb/summeval/$pq/default/test/0000.parquet"
    ;;
  axis)
    for split in test validation; do
      get "$dest/$split.parquet" "$hub/openai/summarize_from_feedback/$pq/axis/$split/0000.parquet"
    done
    ;;
  iterater)
    for split in train validation test; do
      get "$dest/$split.parquet" "$hub/wanyu/IteraTeR_human_sent/$pq/default/$split/0000.parquet"
    done
    ;;
  pararev)
    get "$dest/annot.parquet" "$hub/taln-ls2n/pararev/$pq/pararev_annot_subset/train/0000.parquet"
    ;;
  readmepp)
    github tareknaous/readme b7b6d0808ad2e12c77867a0563ba7b229cbaf911 "$dest/repo"
    ;;
  scarecrow)
    github yao-dou/scarecrow f3f4fffc23596af6840b973ddb7fca8e03d992ab "$dest/repo"
    ;;
  arxivedits)
    github chaojiang06/arXivEdits 113913d68522c1c8428d8e191d5c9bed633da6ce "$dest/repo"
    ;;
  geco)
    for f in EnglishMaterial MonolingualReadingData; do
      get "$dest/$f.xlsx" "https://expsy.ugent.be/downloads/geco/files/$f.xlsx"
    done
    ;;
  *)
    echo "unknown part: $part" >&2
    exit 2
    ;;
esac

(cd "$dest" && find . -type f ! -name SHA256SUMS -size -400M -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
du -sh "$dest"
