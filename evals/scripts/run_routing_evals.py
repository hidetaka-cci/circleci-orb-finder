#!/usr/bin/env python3
"""Cheap, deterministic routing + frontmatter regression check.

Adapted from CircleCI-Public/skills' evals/circleci/scripts/run_routing_evals.py
(https://github.com/CircleCI-Public/skills). Same design intent: no LLM call,
no network access, pure phrase-overlap heuristic — safe to run on every commit
in CI. It answers a narrower question than "does the model actually pick this
skill" (that requires a real invocation, see ../../README.md) — it just catches
obvious regressions in the phrase/description design before they ship.

Unlike the upstream version (which assumes a directory of many skill folders
under a shared plugin root), this defaults to the personal skills root
(~/.claude/skills) so it also sanity-checks frontmatter for whatever other
skills happen to be installed there — a free side benefit, not the point.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.+?)\s*$")
NAME_RE = re.compile(r"^[a-z0-9-]+$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


@dataclass
class SkillFile:
    folder: str
    path: Path
    name: str
    description: str


def parse_frontmatter(skill_file: Path) -> dict[str, str]:
    text = skill_file.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("Missing YAML frontmatter fence")

    fields: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        kv = KV_RE.match(line)
        if not kv:
            continue  # multi-line values (e.g. `description: >-`) — skip, not our concern here
        key, value = kv.group(1), kv.group(2)
        fields[key] = value.strip().strip('"').strip("'")
    return fields


def discover_skills(skills_root: Path) -> tuple[list[SkillFile], list[str]]:
    skill_files: list[SkillFile] = []
    parse_errors: list[str] = []

    # Support two layouts: a root containing many `<skill>/SKILL.md`
    # subdirectories (e.g. ~/.claude/skills/), and a single skill's own repo
    # root where SKILL.md sits directly under skills_root (our CI case:
    # --skills-root . at the repo root of this very skill).
    candidates = []
    direct = skills_root / "SKILL.md"
    if direct.exists():
        candidates.append(direct)
    candidates.extend(sorted(skills_root.glob("*/SKILL.md")))

    for skill_md in candidates:
        folder = skill_md.parent.name
        try:
            fields = parse_frontmatter(skill_md)
        except ValueError as exc:
            parse_errors.append(f"{skill_md}: {exc}")
            continue
        name = fields.get("name", "")
        description = fields.get("description", "")
        skill_files.append(SkillFile(folder=folder, path=skill_md, name=name, description=description))
    return skill_files, parse_errors


def check_frontmatter(skill: SkillFile) -> list[str]:
    errors: list[str] = []
    if not skill.name:
        errors.append(f"{skill.path}: missing 'name' in frontmatter")
    elif not NAME_RE.match(skill.name):
        errors.append(f"{skill.path}: name '{skill.name}' must be lowercase letters/digits/hyphens only")
    elif len(skill.name) > MAX_NAME_LENGTH:
        errors.append(f"{skill.path}: name exceeds {MAX_NAME_LENGTH} characters")

    if not skill.description:
        errors.append(f"{skill.path}: missing 'description' in frontmatter")
    elif len(skill.description) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"{skill.path}: description exceeds {MAX_DESCRIPTION_LENGTH} characters")
    return errors


def tokenize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def predict_skill(prompt: str, skill_phrases: dict[str, list[str]]) -> str | None:
    norm = tokenize(prompt)

    # Explicit invocation should win immediately, e.g. "$circleci-orb-finder".
    for skill_name in skill_phrases:
        if f"${skill_name.lower()}" in norm:
            return skill_name

    best_name: str | None = None
    best_score = 0
    for skill_name, phrases in skill_phrases.items():
        score = sum(1 for phrase in phrases if tokenize(phrase) in norm)
        if score > best_score:
            best_score = score
            best_name = skill_name

    return best_name if best_score > 0 else None


def run_routing_eval(eval_data: dict[str, Any]) -> tuple[list[str], int, int]:
    skill_phrases = {name: list(meta.get("phrases", [])) for name, meta in eval_data.get("skills", {}).items()}
    cases = eval_data.get("cases", [])

    failures: list[str] = []
    passed = 0
    for i, case in enumerate(cases, start=1):
        prompt = str(case.get("prompt", "")).strip()
        expected = case.get("expected")
        predicted = predict_skill(prompt, skill_phrases)
        if predicted == expected:
            passed += 1
        else:
            failures.append(f"Case {i} ({case.get('id')}) failed: prompt={prompt!r} expected={expected!r} predicted={predicted!r}")

    return failures, passed, len(cases)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run circleci-orb-finder routing eval")
    parser.add_argument("--skills-root", default=str(Path.home() / ".claude" / "skills"))
    parser.add_argument(
        "--cases-file",
        default=str(Path(__file__).resolve().parents[1] / "cases" / "skill-routing-cases.json"),
    )
    args = parser.parse_args()

    skills_root = Path(args.skills_root).expanduser().resolve()
    cases_file = Path(args.cases_file).expanduser().resolve()

    if not skills_root.exists():
        print(f"ERROR: skills root not found: {skills_root}")
        return 2
    if not cases_file.exists():
        print(f"ERROR: cases file not found: {cases_file}")
        return 2

    errors: list[str] = []

    print("== Frontmatter checks ==")
    skills, parse_errors = discover_skills(skills_root)
    errors.extend(parse_errors)
    for err in parse_errors:
        print(f"- FAIL (unparseable): {err}")
    for skill in skills:
        skill_errors = check_frontmatter(skill)
        status = "PASS" if not skill_errors else "FAIL"
        print(f"- {skill.folder}: {status}")
        errors.extend(skill_errors)

    print("\n== Routing eval checks ==")
    eval_data = json.loads(cases_file.read_text(encoding="utf-8"))
    failures, passed, total = run_routing_eval(eval_data)
    print(f"- cases: {passed}/{total} passed")
    errors.extend(failures)

    if errors:
        print("\nFailures:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("\nAll routing evals passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
