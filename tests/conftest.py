"""Collects which requirement each test verifies and how it ended.

Writes reports/test-results.json at the end of the run; quality/traceability.py
turns it into a requirements coverage report.
"""

import json
from pathlib import Path

RESULTS: dict[str, dict] = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "req(*ids): requirement ids this test verifies")


def pytest_collection_modifyitems(items):
    for item in items:
        reqs = [r for marker in item.iter_markers("req") for r in marker.args]
        RESULTS[item.nodeid] = {"requirements": reqs, "outcome": "not run"}


def pytest_runtest_logreport(report):
    entry = RESULTS.get(report.nodeid)
    if entry is None:
        return
    if report.when == "call" or report.outcome != "passed":
        # a failure in setup/teardown also counts as a failure
        if not (report.when != "call" and entry["outcome"] == "failed"):
            entry["outcome"] = report.outcome


def pytest_sessionfinish(session):
    out = Path(session.config.rootpath) / "reports" / "test-results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(RESULTS, indent=2))
