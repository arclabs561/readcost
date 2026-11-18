#!/usr/bin/env bash
# Download one dataset of the pre-registered repetition test (docs/prereg/repetition.md).
#
#     bash scripts/fetch_repetition_data.sh PART ROOT
#
# PART is helpsteer, helpsteer3_code, stackexchange or ellipse. Hugging Face
# must be reachable (it is from GitHub Actions). ELLIPSE is fetched at a
# pinned commit. Ends by writing ROOT/PART.SHA256SUMS.
set -euo pipefail

part="$1"
root="$2"
hub="https://huggingface.co/datasets"
pq="resolve/refs%2Fconvert%2Fparquet"

get() { mkdir -p "$(dirname "$1")"; curl -fsSL --retry 3 -o "$1" "$2"; }

case "$part" in
  helpsteer)
    # HelpSteer2 only to drop responses that HelpSteer v1 shares with it.
    for split in train validation; do
      get "$root/helpsteer/$split.parquet" "$hub/nvidia/HelpSteer/$pq/default/$split/0000.parquet"
      get "$root/helpsteer2/$split.parquet" "$hub/nvidia/HelpSteer2/$pq/default/$split/0000.parquet"
    done
    files=("$root/helpsteer" "$root/helpsteer2")
    ;;
  helpsteer3_code)
    for split in train validation; do
      get "$root/helpsteer3/$split.parquet" "$hub/nvidia/HelpSteer3/$pq/preference/$split/0000.parquet"
    done
    files=("$root/helpsteer3")
    ;;
  stackexchange)
    # The first shard of each site; shard counts from the dataset's file listing.
    for site_shards in softwareengineering.stackexchange.com:3 unix.stackexchange.com:4 \
                       serverfault.com:5 superuser.com:6; do
      site="${site_shards%%:*}"
      n="${site_shards##*:}"
      get "$root/stackexchange/$site.parquet" \
        "$hub/HuggingFaceH4/stack-exchange-preferences/resolve/main/data/$site/train-00000-of-0000$n.parquet"
    done
    files=("$root/stackexchange")
    ;;
  ellipse)
    get "$root/ellipse/ELLIPSE_Final_github_train.csv" \
      "https://raw.githubusercontent.com/scrosseye/ELLIPSE-Corpus/710963bbf1acf23a28e40643d9f937d06f047dd4/ELLIPSE_Final_github_train.csv"
    files=("$root/ellipse")
    ;;
  *)
    echo "unknown part: $part" >&2
    exit 2
    ;;
esac

find "${files[@]}" -type f -print0 | sort -z | xargs -0 sha256sum > "$root/$part.SHA256SUMS"
du -sh "${files[@]}"
