"""Requirements traceability: which requirements are verified, failing or untested.

Reads requirements/radio-unit.yaml and the reports/test-results.json written
by the pytest run, and prints a markdown matrix.

  python -m quality.traceability            # report only
  python -m quality.traceability --strict   # also fail if a requirement has no test
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class RequirementStatus:
    id: str
    title: str
    source: str
    tests: list[str]
    failing: list[str]

    @property
    def status(self) -> str:
        if not self.tests:
            return "untested"
        return "failing" if self.failing else "verified"


def load_requirements(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build(requirements: list[dict], results: dict[str, dict]) -> tuple[list[RequirementStatus], list[str]]:
    known = {r["id"] for r in requirements}
    statuses = []
    for req in requirements:
        tests = [node for node, r in results.items() if req["id"] in r["requirements"]]
        failing = [node for node in tests if results[node]["outcome"] not in ("passed", "skipped")]
        statuses.append(RequirementStatus(req["id"], req["title"], req.get("source", ""), tests, failing))
    unknown = sorted({rid for r in results.values() for rid in r["requirements"]} - known)
    return statuses, unknown


ICONS = {"verified": "✅ verified", "failing": "❌ failing", "untested": "⚠️ untested"}


def to_markdown(statuses: list[RequirementStatus], unknown: list[str]) -> str:
    counts = {k: sum(s.status == k for s in statuses) for k in ICONS}
    lines = [
        f"**{counts['verified']} verified, {counts['failing']} failing, {counts['untested']} untested** "
        f"out of {len(statuses)} requirements.",
        "",
        "| Requirement | Title | Source | Tests | Status |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for s in statuses:
        lines.append(f"| {s.id} | {s.title} | {s.source} | {len(s.tests)} | {ICONS[s.status]} |")
    for s in statuses:
        for node in s.failing:
            lines.append(f"\n- {s.id} failing test: `{node}`")
    if unknown:
        lines.append(f"\nTests reference unknown requirement ids: {', '.join(unknown)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", default=ROOT / "requirements" / "radio-unit.yaml", type=Path)
    parser.add_argument("--results", default=ROOT / "reports" / "test-results.json", type=Path)
    parser.add_argument("--out", default=ROOT / "reports" / "traceability.md", type=Path)
    parser.add_argument("--strict", action="store_true", help="exit with an error if a requirement is untested")
    args = parser.parse_args(argv)

    statuses, unknown = build(load_requirements(args.requirements), json.loads(args.results.read_text()))
    report = to_markdown(statuses, unknown)
    args.out.write_text("# Requirements traceability\n\n" + report, encoding="utf-8")
    print(report)

    if any(s.status == "failing" for s in statuses) or unknown:
        return 1
    if args.strict and any(s.status == "untested" for s in statuses):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
