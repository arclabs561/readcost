#!/bin/sh
# Score model outputs stored as JSONL, one record per line with the text in "response".
# Prints one JSON result per record, with counts per feature and the cost index.
readcost check --format jsonl --field response --per-record --output json --fail-on never "$@"
