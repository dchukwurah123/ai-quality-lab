"""Test config."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def write_suite_file(tmp_path: Path):
    """Write a suite payload as JSON or YAML and return path."""

    def _write(filename: str, payload: dict[str, Any]) -> Path:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            path.write_text(json.dumps(payload), encoding="utf-8")
        elif path.suffix.lower() in {".yaml", ".yml"}:
            path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        else:
            raise ValueError("filename must end in .json, .yaml, or .yml")
        return path

    return _write


@pytest.fixture
def minimal_suite_payload() -> dict[str, Any]:
    """Small deterministic suite payload used across loader/CLI tests."""
    return {
        "suite_name": "fixture_suite",
        "description": "fixture dataset",
        "cases": [
            {
                "id": "case-1",
                "task": "summarization",
                "input": {"text": "A fake project update."},
                "expected": "A fake project update.",
                "prediction": "A fake project update.",
                "checks": [{"type": "exact_match", "config": {"case_sensitive": True}}],
            }
        ],
    }
