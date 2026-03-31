from pathlib import Path

import pytest

from ai_quality_lab.loaders import DatasetError, load_suite
from ai_quality_lab.models import (
    ClassificationExpected,
    ComplianceExpected,
    ExtractionExpected,
    SummarizationExpected,
)


@pytest.mark.parametrize("filename", ["suite.json", "suite.yaml"])
def test_load_suite_supports_json_and_yaml(
    write_suite_file, minimal_suite_payload: dict, filename: str
) -> None:
    path = write_suite_file(filename, minimal_suite_payload)
    suite = load_suite(path)
    assert suite.suite_name == "fixture_suite"
    assert len(suite.cases) == 1


@pytest.mark.parametrize(
    ("task", "raw_expected", "expected_type"),
    [
        ("summarization", "short summary", SummarizationExpected),
        ("classification", {"label": "support", "allowed_labels": ["support", "billing"]}, ClassificationExpected),
        ("extraction", {"fields": {"email": "a@b.com"}, "required_fields": ["email"]}, ExtractionExpected),
        ("compliance", {"verdict": "compliant", "policy_id": "p1"}, ComplianceExpected),
    ],
)
def test_loader_parses_task_specific_expected_shapes(
    write_suite_file, task: str, raw_expected: object, expected_type: type
) -> None:
    payload = {
        "suite_name": "typed_expected_suite",
        "description": "typed expected suite",
        "cases": [
            {
                "id": "c1",
                "task": task,
                "input": {"text": "synthetic"},
                "expected": raw_expected,
                "checks": [{"type": "exact_match", "config": {}}],
            }
        ],
    }
    path = write_suite_file("typed.json", payload)
    suite = load_suite(path)
    assert isinstance(suite.cases[0].expected, expected_type)


def test_loader_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "suite.txt"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(DatasetError, match="extension"):
        load_suite(path)


def test_loader_rejects_missing_checks(write_suite_file, minimal_suite_payload: dict) -> None:
    broken = dict(minimal_suite_payload)
    broken["cases"] = [dict(minimal_suite_payload["cases"][0])]
    broken["cases"][0].pop("checks")
    path = write_suite_file("broken.json", broken)
    with pytest.raises(DatasetError, match="non-empty 'checks'"):
        load_suite(path)


def test_loader_rejects_invalid_task(write_suite_file, minimal_suite_payload: dict) -> None:
    broken = dict(minimal_suite_payload)
    broken["cases"] = [dict(minimal_suite_payload["cases"][0])]
    broken["cases"][0]["task"] = "translation"
    path = write_suite_file("invalid_task.json", broken)
    with pytest.raises(DatasetError, match="must be one of"):
        load_suite(path)


def test_loader_rejects_bad_expected_shape_for_task(
    write_suite_file, minimal_suite_payload: dict
) -> None:
    broken = dict(minimal_suite_payload)
    broken["cases"] = [dict(minimal_suite_payload["cases"][0])]
    broken["cases"][0]["task"] = "compliance"
    broken["cases"][0]["expected"] = {"verdict": "maybe"}
    path = write_suite_file("bad_expected.yaml", broken)
    with pytest.raises(DatasetError, match="Invalid expected shape"):
        load_suite(path)
