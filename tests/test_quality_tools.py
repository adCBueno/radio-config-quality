import json

from quality import propose_tests, traceability

REQS = [{"id": "R-1", "title": "a"}, {"id": "R-2", "title": "b"}, {"id": "R-3", "title": "c"}]


def test_traceability_statuses():
    results = {
        "t1": {"requirements": ["R-1"], "outcome": "passed"},
        "t2": {"requirements": ["R-2"], "outcome": "passed"},
        "t3": {"requirements": ["R-2"], "outcome": "failed"},
        "t4": {"requirements": ["R-9"], "outcome": "passed"},
    }
    statuses, unknown = traceability.build(REQS, results)
    assert [s.status for s in statuses] == ["verified", "failing", "untested"]
    assert unknown == ["R-9"]
    report = traceability.to_markdown(statuses, unknown)
    assert "1 verified, 1 failing, 1 untested" in report and "`t3`" in report


def test_traceability_exit_codes(tmp_path):
    reqs = tmp_path / "r.yaml"
    reqs.write_text("- id: R-1\n  title: a\n- id: R-2\n  title: b\n")
    results = tmp_path / "res.json"
    results.write_text(json.dumps({"t1": {"requirements": ["R-1"], "outcome": "passed"}}))
    args = ["--requirements", str(reqs), "--results", str(results), "--out", str(tmp_path / "o.md")]
    assert traceability.main(args) == 0
    assert traceability.main(args + ["--strict"]) == 1


def test_extract_code():
    assert propose_tests.extract_code("Here:\n```python\ndef test_x():\n    pass\n```\nDone") == "def test_x():\n    pass"
    assert propose_tests.extract_code("def test_y(): pass") == "def test_y(): pass"


def test_prompt_contains_requirement_and_api():
    prompt = propose_tests.build_prompt({"id": "REQ-RU-011", "title": "At most 4 carriers", "source": "product"})
    assert "REQ-RU-011" in prompt and "MAX_CARRIERS = 4" in prompt and "class CarrierConfig" in prompt


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"content": [{"type": "text", "text": "```python\n@pytest.mark.req('REQ-RU-011')\ndef test_five():\n    pass\n```"}]}


class FakeSession:
    def post(self, *args, **kwargs):
        self.sent = kwargs["json"]
        return FakeResponse()


def test_proposals_are_written_as_drafts(tmp_path, monkeypatch):
    results = tmp_path / "res.json"
    results.write_text(json.dumps({}))  # nothing tested -> every requirement gets a proposal
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    session = FakeSession()
    assert propose_tests.main(["--results", str(results), "--out", str(tmp_path / "p")], session=session) == 0
    draft = (tmp_path / "p" / "test_req_ru_011_draft.py").read_text()
    assert "DRAFT" in draft and "def test_five" in draft
    assert session.sent["model"] == propose_tests.DEFAULT_MODEL


def test_dry_run_without_key(tmp_path, monkeypatch, capsys):
    results = tmp_path / "res.json"
    results.write_text(json.dumps({}))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    propose_tests.main(["--results", str(results), "--out", str(tmp_path / "p")])
    assert "dry run" in capsys.readouterr().out
    assert not (tmp_path / "p").exists()
