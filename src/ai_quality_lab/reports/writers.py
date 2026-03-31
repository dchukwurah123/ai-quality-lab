"""Simple report output functions."""

from __future__ import annotations

import json
from pathlib import Path

from ai_quality_lab.models import SuiteOutcome


def write_json_report(result: SuiteOutcome, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path


def write_markdown_report(result: SuiteOutcome, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Eval Report: {result.suite_name}",
        "",
        f"- Total: {result.total_cases}",
        f"- Passed: {result.passed_cases}",
        f"- Pass rate: {result.pass_rate:.2%}",
        f"- Average score: {result.average_score:.2f}",
        "",
        "## Cases",
    ]
    for case in result.cases:
        status = "PASS" if case.passed else "FAIL"
        lines.append(f"- {case.case_id} ({case.task}) [{status}] score={case.score:.2f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
