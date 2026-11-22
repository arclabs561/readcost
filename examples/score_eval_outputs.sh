#!/bin/sh
# Score model outputs stored as JSONL, one record per line with the text in "response".
# Prints a JSON array with a result for each record, including counts and cost index.
readcost check --format jsonl --field response --per-record --output json --fail-on never "$@"
