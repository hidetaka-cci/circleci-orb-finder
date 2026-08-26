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
import time
import xml.etree.ElementTree as ET
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


def discover_skills(skills_root: Path) -> tuple[list[SkillFile], list[tuple[Path, str]]]:
    skill_files: list[SkillFile] = []
    parse_errors: list[tuple[Path, str]] = []

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
            parse_errors.append((skill_md, str(exc)))
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


def run_routing_eval(eval_data: dict[str, Any]) -> list[tuple[str, bool, str]]:
    skill_phrases = {name: list(meta.get("phrases", [])) for name, meta in eval_data.get("skills", {}).items()}
    cases = eval_data.get("cases", [])

    results: list[tuple[str, bool, str]] = []
    for i, case in enumerate(cases, start=1):
        prompt = str(case.get("prompt", "")).strip()
        expected = case.get("expected")
        predicted = predict_skill(prompt, skill_phrases)
        case_id = str(case.get("id", i))
        passed = predicted == expected
        message = "" if passed else f"prompt={prompt!r} expected={expected!r} predicted={predicted!r}"
        results.append((case_id, passed, message))

    return results


def write_junit_report(path: Path, testsuites: list[tuple[str, list[tuple[str, bool, str]]]], elapsed: float) -> None:
    root = ET.Element("testsuites")
    for suite_name, cases in testsuites:
        failures = sum(1 for _, passed, _ in cases if not passed)
        suite_el = ET.SubElement(
            root,
            "testsuite",
            {"name": suite_name, "tests": str(len(cases)), "failures": str(failures), "time": f"{elapsed:.3f}"},
        )
        for name, passed, message in cases:
            case_el = ET.SubElement(suite_el, "testcase", {"classname": suite_name, "name": name, "time": "0"})
            if not passed:
                ET.SubElement(case_el, "failure", {"message": message}).text = message

    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run circleci-orb-finder routing eval")
    parser.add_argument("--skills-root", default=str(Path.home() / ".claude" / "skills"))
    parser.add_argument(
        "--cases-file",
        default=str(Path(__file__).resolve().parents[1] / "cases" / "skill-routing-cases.json"),
    )
    parser.add_argument(
        "--junit-xml",
        default=str(Path("test-results") / "routing-evals" / "junit.xml"),
        help="Where to write a JUnit XML report (for CircleCI's store_test_results)",
    )
    args = parser.parse_args()

    start = time.perf_counter()
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
    frontmatter_cases: list[tuple[str, bool, str]] = []
    for skill_md, exc in parse_errors:
        message = f"{skill_md}: {exc}"
        errors.append(message)
        frontmatter_cases.append((skill_md.parent.name, False, message))
        print(f"- FAIL (unparseable): {message}")
    for skill in skills:
        skill_errors = check_frontmatter(skill)
        status = "PASS" if not skill_errors else "FAIL"
        print(f"- {skill.folder}: {status}")
        errors.extend(skill_errors)
        frontmatter_cases.append((skill.folder, not skill_errors, "; ".join(skill_errors)))

    print("\n== Routing eval checks ==")
    eval_data = json.loads(cases_file.read_text(encoding="utf-8"))
    routing_results = run_routing_eval(eval_data)
    passed = sum(1 for _, ok, _ in routing_results if ok)
    total = len(routing_results)
    print(f"- cases: {passed}/{total} passed")
    for i, (case_id, ok, message) in enumerate(routing_results, start=1):
        if not ok:
            errors.append(f"Case {i} ({case_id}) failed: {message}")

    write_junit_report(
        Path(args.junit_xml),
        [
            ("frontmatter", frontmatter_cases),
            ("routing_eval", [(case_id, ok, message) for case_id, ok, message in routing_results]),
        ],
        time.perf_counter() - start,
    )

    if errors:
        print("\nFailures:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("\nAll routing evals passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
