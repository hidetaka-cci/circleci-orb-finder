#!/usr/bin/env bash
# Search the *content* of every certified orb's source YAML for a keyword.
#
# Why this exists: orb *names* only tell you about orbs published as their
# own package. A tool can be supported *inside* a broader orb without ever
# appearing in its name (e.g. the `uv` package manager is implemented as a
# `pkg-manager: uv` option inside `circleci/python`, not as its own orb).
# Name search and GitHub search both miss this. This script does not need
# to know the domain the keyword belongs to — it just fetches every
# certified orb's source and greps it, so it works for arbitrary keywords.
#
# Certified orbs are a small, bounded set (order of ~100), so fetching all
# of them is cheap enough to do outright. This does NOT cover the much
# larger pool of uncertified/community orbs (tens of thousands) — grepping
# all of those is not currently cost-effective. If search_by_name.sh or
# search_github.sh surfaced a specific uncertified orb, verify it directly
# with verify_orb.sh instead.
#
# Usage: search_by_content.sh <keyword> [--refresh]
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <keyword> [--refresh]" >&2
  exit 1
fi
keyword="$1"
refresh_flag="${2:-}"

CACHE_DIR="${TMPDIR:-/tmp}/circleci_orb_finder_cache"
SOURCES_DIR="$CACHE_DIR/sources"
MANIFEST="$CACHE_DIR/manifest.json"
TTL_SECONDS=$((7 * 24 * 3600)) # 1 week — certified orbs change infrequently

mkdir -p "$SOURCES_DIR"

file_age_seconds() {
  local f="$1"
  local mtime
  mtime=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)
  echo $(( $(date +%s) - mtime ))
}

need_refresh=1
if [[ -f "$MANIFEST" && "$refresh_flag" != "--refresh" ]]; then
  if (( $(file_age_seconds "$MANIFEST") < TTL_SECONDS )); then
    need_refresh=0
  fi
fi

if (( need_refresh )); then
  echo "Refreshing certified-orb content cache (fetches ~100 orb sources, ~1-2 min)..." >&2
  circleci orb list --json > "$MANIFEST"
  rm -f "${SOURCES_DIR:?}"/*.yml
  jq -r '.[].name' "$MANIFEST" | while read -r orb; do
    fname="$SOURCES_DIR/$(echo "$orb" | tr '/' '_').yml"
    if ! circleci orb source "$orb" > "$fname" 2>/dev/null; then
      rm -f "$fname" # orb has no published version yet — skip it
    fi
  done
  echo "Cached $(ls "$SOURCES_DIR"/*.yml 2>/dev/null | wc -l | tr -d ' ') certified orb sources." >&2
fi

matches=$(grep -lni -- "$keyword" "$SOURCES_DIR"/*.yml 2>/dev/null || true)
if [[ -z "$matches" ]]; then
  echo "NO_CONTENT_MATCHES"
else
  echo "$matches" | while read -r f; do
    orb_name=$(basename "$f" .yml | tr '_' '/')
    echo "=== $orb_name ==="
    # cut(1) truncates long lines (e.g. shell one-liners embedded in a YAML
    # `command:` block) so a single match doesn't blow up the skill's context
    grep -ni -- "$keyword" "$f" | cut -c1-200 | head -5
    echo
  done
fi
