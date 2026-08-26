---
name: circleci-orb-finder
description: >-
  Finds out whether a CircleCI orb already exists for a given tool or task
  (e.g. "is there a CircleCI orb for uv / fivetran / aws-cli?") by checking
  orb names, GitHub, and the full content of certified orb sources — so
  functionality embedded inside a broader orb (like `uv` support living
  inside `circleci/python`) isn't missed just because it has no orb of its
  own. Use before writing custom install/setup/caching steps in a
  .circleci/config.yml, when the user asks whether an orb covers a tool, or
  when searching the CircleCI orb registry for something.
version: 1.0.0
---

# CircleCI Orb Finder

Answers "does an orb exist for X?" precisely — including the "no dedicated
orb, but it's built into orb Y" case that a naive name search misses.

## Why name search alone is not enough

A tool can be supported three different ways in the orb ecosystem:

1. **Its own orb** — e.g. `circleci/aws-cli`. Name search finds this.
2. **A parameter/option inside a broader orb** — e.g. the `uv` package
   manager is not its own orb; it's a `pkg-manager: uv` option inside
   `circleci/python`. Name search returns nothing here even though support
   exists. Only reading orb *content* finds it.
3. **Nothing published** — e.g. Fivetran has no CircleCI orb at all (only a
   Fivetran-side connector that ingests CircleCI data, which is the reverse
   direction). Absence has to be confirmed across name search, content
   search, and GitHub before saying "no orb exists" — treat a single empty
   result as a lead, not a conclusion.

Also watch out for **short-keyword false positives** in plain substring
matching: searching for `uv` against raw orb names naively matches
`bouvier`, `trouva`, `villeneuve`, `neuvector`, etc. `search_by_name.sh`
already guards against this by requiring the keyword to sit on a `/` or `-`
boundary, but keep it in mind if you ever grep orb data manually.

## Procedure

Run these in order. Stop as soon as you have a confident answer — you don't
need every step for a clear positive hit (e.g. `aws-cli` name-matches
immediately).

### 1. Name search (fast, broad, but literal)

```bash
scripts/search_by_name.sh "<keyword>"
```

Searches every orb name in the registry (certified + uncertified) for the
keyword as a delimited segment. Prints `NO_NAME_MATCHES` if nothing hits.

A hit here is a strong signal but not final — a same-named orb can be
abandoned/unofficial. Check `latest_version` (empty means never published)
and cross-check with step 4 (`verify_orb.sh`) before recommending it.

### 2. GitHub search (catches unlisted/experimental orbs and doc mentions)

```bash
scripts/search_github.sh "<keyword>"
```

Wraps `gh search code` / `gh search repos`. Useful for orbs not yet in the
registry, or finding that a keyword is unrelated to CircleCI entirely
(e.g. most "fivetran" hits are dbt packages, not orbs — that's a signal the
keyword lives in a different ecosystem, not evidence of an orb).

### 3. Content search across certified orbs (catches embedded functionality)

```bash
scripts/search_by_content.sh "<keyword>"
```

This is the step that finds case 2 above. It fetches the source YAML of
every **certified** orb (a bounded set, roughly ~100 orbs, cached for a
week under `$TMPDIR/circleci_orb_finder_cache/`) and greps the full content
— parameters, enum options, embedded shell scripts, comments. It does not
require knowing which orb might be relevant; it checks all of them.

Pass `--refresh` as a second argument to force a fresh fetch if you suspect
the cache is stale (new orb version published, etc).

This does **not** cover uncertified/community orbs (tens of thousands) —
that pool is too large to fetch in full. If steps 1/2 pointed at a specific
uncertified orb, verify that one directly with step 4 instead of expecting
this script to find it.

### 4. Verify a specific candidate

```bash
scripts/verify_orb.sh "<namespace>/<orb>[@version]"
```

Once you have a candidate (from any step above), confirm it's real and
healthy: is it certified, how many versions has it had, recent usage stats,
and a peek at the actual source. Use this before recommending an orb to the
user, not just a name match.

## Answering the user

State the finding precisely, matching one of these three shapes:

- **Dedicated orb exists**: name it, give the latest version, and note
  whether it's `circleci/`-certified or community-maintained.
- **Built into a broader orb**: name the parent orb and the specific
  parameter/option that provides the functionality (this is the case a
  careless search would report as "no orb found" — don't do that).
- **No orb exists**: say so plainly once name search, content search, and
  GitHub search have all come back empty, and suggest the closest
  workaround (e.g. a generic `curl`/API call, or writing a small custom
  command).
