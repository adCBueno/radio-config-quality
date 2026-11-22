"""AI-assisted test design: propose test cases for untested requirements.

For each requirement without tests, an LLM gets the requirement, the public
API of the radio unit and an example of an existing test, and proposes test
cases. The output is a draft file for an engineer to review, never added to
the suite automatically: a generated test can be wrong in the same way the
code is wrong, so a human decides what the expected behaviour is.

  python -m quality.propose_tests                 # dry run: prints the prompt
  ANTHROPIC_API_KEY=... python -m quality.propose_tests --out proposals/
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
from pathlib import Path

import requests

from quality.traceability import ROOT, build, load_requirements

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"

PROMPT = """You are a test engineer for radio unit software. Propose pytest test cases for this requirement.

Requirement {id}: {title} (source: {source})

Public API:
```python
{api}
```

Example of an existing test in this suite:
```python
{example}
```

Rules:
- Tag every test with @pytest.mark.req("{id}").
- Cover the normal case, the boundaries and at least one invalid input.
- Use only the public API above.
- Answer with one Python code block containing the tests and nothing else."""


def api_summary() -> str:
    from rusim import radio_unit

    parts = [inspect.getsource(radio_unit.CarrierConfig), inspect.getsource(radio_unit.Violation)]
    parts.append("class RadioUnit:\n" + inspect.getsource(radio_unit.RadioUnit.apply).split('"""')[0] + "...")
    parts.append(f"MAX_POWER_DBM = {radio_unit.MAX_POWER_DBM}\nMAX_CARRIERS = {radio_unit.MAX_CARRIERS}")
    return "\n".join(parts)


EXAMPLE = '''@pytest.mark.req("REQ-RU-007")
@pytest.mark.parametrize("power", [-0.1, 46.1, 60])
def test_power_out_of_range(power):
    assert rejected_requirements([carrier(power=power)]) == {"REQ-RU-007"}'''


def build_prompt(req: dict) -> str:
    return PROMPT.format(id=req["id"], title=req["title"], source=req.get("source", ""),
                         api=api_summary(), example=EXAMPLE)


def extract_code(text: str) -> str:
    if "```" not in text:
        return text.strip()
    block = text.split("```", 2)[1]
    return block.removeprefix("python").strip()


def ask(prompt: str, api_key: str, model: str, session=None) -> str:
    http = session or requests.Session()
    resp = http.post(
        API_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    resp.raise_for_status()
    return "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")


HEADER = '''"""DRAFT tests proposed by an LLM for {id}: {title}.

Review every expected value against the requirement before moving these
into tests/. Generated tests can encode wrong behaviour.
"""
import pytest

from tests.test_radio_unit import carrier, rejected_requirements  # noqa: F401
from rusim import CarrierConfig, ConfigRejected, RadioUnit  # noqa: F401

'''


def main(argv: list[str] | None = None, session=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=ROOT / "reports" / "test-results.json", type=Path)
    parser.add_argument("--out", default=ROOT / "proposals", type=Path)
    args = parser.parse_args(argv)

    requirements = load_requirements(ROOT / "requirements" / "radio-unit.yaml")
    statuses, _ = build(requirements, json.loads(args.results.read_text()))
    untested = [r for r, s in zip(requirements, statuses, strict=True) if s.status == "untested"]
    if not untested:
        print("Every requirement has at least one test.")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    for req in untested:
        prompt = build_prompt(req)
        if not api_key:
            print(f"--- dry run for {req['id']} (set ANTHROPIC_API_KEY to call the model) ---\n{prompt}\n")
            continue
        code = extract_code(ask(prompt, api_key, os.environ.get("AI_MODEL", DEFAULT_MODEL), session))
        args.out.mkdir(parents=True, exist_ok=True)
        target = args.out / f"test_{req['id'].lower().replace('-', '_')}_draft.py"
        target.write_text(HEADER.format(**req) + code + "\n", encoding="utf-8")
        print(f"{req['id']}: draft written to {target}, review it before using it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
