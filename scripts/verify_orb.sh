#!/usr/bin/env bash
# Verify a specific orb candidate: metadata/stats + a peek at its source.
# Usage: verify_orb.sh <namespace>/<orb>[@version]
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <namespace>/<orb>[@version]" >&2
  exit 1
fi
orb="$1"

echo "## circleci orb get $orb"
circleci orb get "$orb" --json 2>/dev/null | jq . || circleci orb get "$orb"
echo
echo "## circleci orb source $orb (first 100 lines)"
circleci orb source "$orb" 2>/dev/null | head -100
