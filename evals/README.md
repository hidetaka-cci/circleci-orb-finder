# Evals for circleci-orb-finder

Structure and split modeled on [CircleCI-Public/skills](https://github.com/CircleCI-Public/skills)'s
`evals/circleci/`: cheap deterministic checks are separated from checks that need
a live network/real invocation, and only the cheap ones are meant to run in CI.

## `cases/skill-routing-cases.json` + `scripts/run_routing_evals.py`

Phrase-overlap heuristic, no LLM call, no network. Checks:
1. Frontmatter sanity (`name`/`description` present and well-formed) for every
   skill under `~/.claude/skills/`.
2. Whether a set of example prompts (positive **and** negative controls, in
   both English and Japanese since that's how this skill is actually used)
   would route to `circleci-orb-finder` under a simple keyword-overlap
   approximation of real routing.

This is a regression check on the *phrase design*, not proof the real model
will route correctly — it's a cheap early warning, same caveat upstream's
version carries.

```bash
python3 scripts/run_routing_evals.py
```

## `cases/functional-cases.json` + `scripts/run_functional_evals.sh`

Runs the skill's actual `search_by_name.sh` / `search_by_content.sh` against
keywords already verified by hand in this skill's development (uv, fivetran,
pnpm, terraform, aws-cli, evals) and asserts on the real output. This is the
part that would have caught the `villeneuve`/`bouvier`/`trouva` substring
false-positive bug in `search_by_name.sh` if it had existed at the time.

Deliberately **not** part of any CI job: it needs a working `circleci` CLI
session and `gh` auth, hits the live orb registry, and takes ~1-2 minutes on
a cold content-search cache. Run it locally after changing any `scripts/*.sh`:

```bash
bash scripts/run_functional_evals.sh
```

## CI (`.circleci/config.yml`)

This repo's actual CircleCI config is a single job that runs the
routing+frontmatter script — nothing else. It doesn't need `pyyaml` or any
other dependency, since `run_routing_evals.py` uses only the standard
library, so the job runs directly on `cimg/base` (pinned to a dated tag, not
the floating `:current`, so the environment doesn't drift under us):

```yaml
version: 2.1

jobs:
  skill-evals:
    docker:
      - image: cimg/base:2026.03
    resource_class: small
    steps:
      - checkout
      - run:
          name: Run circleci-orb-finder routing evals
          command: python3 evals/scripts/run_routing_evals.py --skills-root .

workflows:
  evals:
    jobs:
      - skill-evals
```

`run_functional_evals.sh` intentionally has no CI job here, for the same
reason upstream keeps their invocation-smoke/trace evals local-only: it needs
credentials and live network access a generic CI container shouldn't be
trusted with by default.
