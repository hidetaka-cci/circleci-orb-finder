#!/usr/bin/env bash
# Runs the skill's search scripts against real, previously-verified keywords
# and asserts on their actual output.
#
# This is deterministic (no LLM call, no grading needed) because the skill's
# core value is a deterministic script, not free-form generation — unlike
# CircleCI-Public/skills' "trace" evals, which need to capture and grade a
# real model run since their skills produce free-form output. That's also
# exactly why this does NOT belong in a CI job: it hits the live network
# (circleci CLI against the real orb registry, gh against GitHub) and takes
# ~1-2 minutes on a cold cache. Run it locally after touching search_by_*.sh.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CASES_FILE="${SCRIPT_DIR}/../cases/functional-cases.json"

pass=0
fail=0

total=$(jq '.cases | length' "$CASES_FILE")
for i in $(seq 0 $((total - 1))); do
  case_json=$(jq -c ".cases[$i]" "$CASES_FILE")
  id=$(echo "$case_json" | jq -r '.id')
  keyword=$(echo "$case_json" | jq -r '.keyword')
  script=$(echo "$case_json" | jq -r '.script')
  expect=$(echo "$case_json" | jq -r '.expect_contains')

  output=$("${SKILL_DIR}/scripts/${script}" "$keyword" 2>/dev/null)
  if echo "$output" | grep -qF -- "$expect"; then
    echo "PASS  $id"
    pass=$((pass + 1))
  else
    echo "FAIL  $id  (keyword=$keyword script=$script expected to contain: $expect)"
    echo "$output" | head -3 | sed 's/^/        /'
    fail=$((fail + 1))
  fi
done

echo
echo "${pass}/$((pass + fail)) functional cases passed"
[[ "$fail" -eq 0 ]]
