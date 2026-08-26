# circleci-orb-finder

A [Claude Code Agent Skill](https://code.claude.com/docs/en/skills) that answers
"does a CircleCI orb exist for X?" precisely — including the case a naive name
search misses: functionality embedded *inside* a broader orb rather than
published as its own (e.g. the `uv` Python package manager has no orb of its
own; it's a `pkg-manager: uv` option inside `circleci/python`).

See [`SKILL.md`](./SKILL.md) for the full procedure Claude follows.

## Why

Orb name search alone gives false negatives (a tool can be supported as a
parameter inside a bigger orb) and short keywords false-positive on unrelated
substrings (`uv` naively matches `villeneuve`, `bouvier`, `trouva`, ...). This
skill fixes both by combining name search, GitHub search, and a full-content
grep across every certified orb's source — deterministically, without needing
to already know which orb might be relevant.

## Install

Using the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add hidetaka-cci/circleci-orb-finder --agent claude-code
```

Or copy this directory into your personal or project skills folder directly:

```bash
git clone https://github.com/hidetaka-cci/circleci-orb-finder.git \
  ~/.claude/skills/circleci-orb-finder
```

Requires `circleci`, `gh`, and `jq` on `PATH`, with `circleci` and `gh`
authenticated.

## Structure

```
SKILL.md                  # instructions Claude follows
scripts/
  search_by_name.sh        # orb name search (certified + uncertified)
  search_github.sh         # GitHub code/repo search
  search_by_content.sh     # full-content grep across certified orb sources (cached)
  verify_orb.sh             # metadata + source peek for a specific candidate
evals/                     # see evals/README.md
  cases/
    skill-routing-cases.json   # cheap phrase-based routing regression (no LLM, no network)
    functional-cases.json      # real search-script output regression (live network)
  scripts/
    run_routing_evals.py       # runs in CI — see .circleci/config.yml
    run_functional_evals.sh    # local-only, see evals/README.md for why
```

## Design inspiration

- [anthropics/skills](https://github.com/anthropics/skills)'s `skill-creator`
  for the Agent Skills authoring format and progressive-disclosure model.
- [CircleCI-Public/skills](https://github.com/CircleCI-Public/skills)'s eval
  layering: cheap deterministic checks run in CI, checks that need a real
  invocation or live network stay local-only.

## License

MIT — see [LICENSE](./LICENSE).
