#!/usr/bin/env bash
# Search GitHub for orb implementations/mentions not (yet) surfaced in the
# CircleCI registry name search — catches unlisted/experimental orbs and
# README-only mentions.
# Usage: search_github.sh <keyword>
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <keyword>" >&2
  exit 1
fi
keyword="$1"

echo "## gh search code: \"$keyword\" + circleci orb"
gh search code "$keyword" "circleci orb" --limit 20 || echo "(no code results)"
echo
echo "## gh search repos: \"$keyword orb circleci\""
gh search repos "$keyword orb circleci" --limit 20 || echo "(no repo results)"
