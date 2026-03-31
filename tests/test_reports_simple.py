import json
from pathlib import Path

from ai_quality_lab.loaders import load_suite
from ai_quality_lab.reports.writers import write_json_report, write_markdown_report
from ai_quality_lab.runner import run_suite


def test_report_generation_json_and_markdown(tmp_path: Path) -> None:
    suite = load_suite("datasets/minimal_suite.json")
    result = run_suite(suite, adapter_name="dataset")

    json_path = write_json_report(result, tmp_path / "simple_report.json")
    md_path = write_markdown_report(result, tmp_path / "simple_report.md")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["suite_name"] == "minimal_first_slice"
    assert payload["cases"][0]["checks"][0]["check_type"] == "exact_match"
    assert "# Eval Report: minimal_first_slice" in markdown
    assert "## Cases" in markdown


def test_markdown_report_includes_failing_case_status(tmp_path: Path) -> None:
    suite = load_suite("datasets/minimal_suite.json")
    suite.cases[0].prediction = "wrong output"
    result = run_suite(suite, adapter_name="dataset")
    md_path = write_markdown_report(result, tmp_path / "simple_report.md")
    markdown = md_path.read_text(encoding="utf-8")
    assert "[FAIL]" in markdown
