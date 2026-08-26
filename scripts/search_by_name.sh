#!/usr/bin/env bash
# Search CircleCI orb *names* (certified + uncertified) for a keyword.
# Usage: search_by_name.sh <keyword>
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <keyword>" >&2
  exit 1
fi
keyword="$1"

# Match keyword as a whole "/" or "-" delimited segment of the orb name,
# not an arbitrary substring — otherwise short keywords like "uv" false-
# positive on names like "villeneuve", "bouvier", "trouva", "neuvector".
circleci orb list --uncertified --json | jq --arg kw "$keyword" \
  '[.[] | select(.name | test("(^|[-/])" + $kw + "([-/]|$)"; "i"))] | if length == 0 then "NO_NAME_MATCHES" else . end'
