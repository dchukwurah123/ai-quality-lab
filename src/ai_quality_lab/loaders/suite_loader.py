"""JSON/YAML dataset loader with task-specific expected parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ai_quality_lab.models import EvalCase, EvalCheck, EvalSuite, TaskType, parse_expected

SUPPORTED_CHECK_TYPES = {
    "exact_match",
    "allowed_labels",
    "regex_constraints",
    "schema_validation",
    "field_extraction",
    "rubric",
}


class DatasetError(ValueError):
    """Raised when dataset shape is invalid."""


def load_suite(path: str | Path) -> EvalSuite:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset not found: {file_path}")
    suffix = file_path.suffix.lower()
    raw = file_path.read_text(encoding="utf-8")
    if suffix == ".json":
        data = json.loads(raw)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(raw)
    else:
        raise DatasetError("Dataset extension must be .json, .yaml, or .yml.")
    return _parse_suite(data)


def _parse_suite(data: dict[str, Any]) -> EvalSuite:
    if not isinstance(data, dict):
        raise DatasetError("Dataset root must be an object.")

    suite_name = _required_str(data, "suite_name")
    description = data.get("description", "")
    if not isinstance(description, str):
        raise DatasetError("'description' must be a string.")

    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise DatasetError("'cases' must be a non-empty list.")

    cases: list[EvalCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise DatasetError("Each case must be an object.")
        checks = raw_case.get("checks", [])
        if not isinstance(checks, list) or not checks:
            raise DatasetError("Each case must define non-empty 'checks'.")
        parsed_checks = [_parse_check(check) for check in checks]
        task = _required_task(raw_case)
        if "expected" not in raw_case:
            raise DatasetError("Each case must define 'expected'.")
        try:
            expected = parse_expected(task, raw_case["expected"])
        except ValueError as exc:
            case_id = raw_case.get("id", "<unknown>")
            raise DatasetError(f"Invalid expected shape for case '{case_id}': {exc}") from exc
        cases.append(
            EvalCase(
                id=_required_str(raw_case, "id"),
                task=task,
                input=raw_case.get("input"),
                expected=expected,
                checks=parsed_checks,
                prediction=raw_case.get("prediction"),
                metadata=_optional_object(raw_case, "metadata"),
            )
        )
    return EvalSuite(suite_name=suite_name, description=description, cases=cases)


def _parse_check(raw: Any) -> EvalCheck:
    if not isinstance(raw, dict):
        raise DatasetError("Each check must be an object.")
    check_type = _required_str(raw, "type")
    if check_type not in SUPPORTED_CHECK_TYPES:
        raise DatasetError(
            f"Unsupported check type '{check_type}'. Expected one of {sorted(SUPPORTED_CHECK_TYPES)}."
        )
    config = raw.get("config", {})
    if not isinstance(config, dict):
        raise DatasetError("'config' must be an object when provided.")
    return EvalCheck(type=check_type, config=config)


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise DatasetError(f"'{key}' must be a non-empty string.")
    return value


def _required_task(data: dict[str, Any]) -> TaskType:
    task = _required_str(data, "task")
    valid = {"summarization", "classification", "extraction", "compliance"}
    if task not in valid:
        raise DatasetError(f"'task' must be one of {sorted(valid)}.")
    return task  # type: ignore[return-value]


def _optional_object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise DatasetError(f"'{key}' must be an object when provided.")
    return value
