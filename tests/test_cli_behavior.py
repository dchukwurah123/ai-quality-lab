import json
import copy
from pathlib import Path

import pytest

from ai_quality_lab.cli import main


def test_cli_eval_single_dataset_outputs_json_and_markdown(
    write_suite_file, minimal_suite_payload: dict, tmp_path: Path
) -> None:
    dataset_path = write_suite_file("suite.json", minimal_suite_payload)
    out_dir = tmp_path / "eval_out"
    code = main(
        [
            "eval",
            "--dataset",
            str(dataset_path),
            "--adapter",
            "dataset",
            "--out-dir",
            str(out_dir),
            "--min-pass-rate",
            "1.0",
            "--min-average-score",
            "1.0",
        ]
    )
    assert code == 0
    payload = json.loads((out_dir / "eval_results.json").read_text(encoding="utf-8"))
    assert payload["summary"]["all_suites_meet_thresholds"] is True
    assert payload["summary"]["suite_count"] == 1
    assert payload["suites"][0]["result"]["suite_name"] == "fixture_suite"
    markdown = (out_dir / "eval_summary.md").read_text(encoding="utf-8")
    assert "| Suite Name | Task Type(s) | Total Cases | Pass Count | Fail Count | Average Score | Top Failure Reasons | Status |" in markdown


@pytest.mark.parametrize(
    ("pass_prediction", "fail_prediction", "expected_exit"),
    [
        ("match", "mismatch", 2),
        ("match", "match", 0),
    ],
)
def test_cli_eval_threshold_behavior_for_directory(
    write_suite_file,
    minimal_suite_payload: dict,
    tmp_path: Path,
    pass_prediction: str,
    fail_prediction: str,
    expected_exit: int,
) -> None:
    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    pass_payload = copy.deepcopy(minimal_suite_payload)
    fail_payload = copy.deepcopy(minimal_suite_payload)
    pass_payload["suite_name"] = "pass_suite"
    fail_payload["suite_name"] = "fail_suite"
    pass_payload["cases"][0]["expected"] = "match"
    fail_payload["cases"][0]["expected"] = "match"
    pass_payload["cases"][0]["prediction"] = pass_prediction
    fail_payload["cases"][0]["prediction"] = fail_prediction

    write_suite_file(str(Path("datasets") / "pass.json"), pass_payload)
    write_suite_file(str(Path("datasets") / "fail.json"), fail_payload)

    out_dir = tmp_path / "eval_dir_out"
    code = main(
        [
            "eval",
            "--datasets-dir",
            str(datasets_dir),
            "--adapter",
            "dataset",
            "--out-dir",
            str(out_dir),
            "--min-pass-rate",
            "1.0",
            "--min-average-score",
            "1.0",
        ]
    )
    assert code == expected_exit
    payload = json.loads((out_dir / "eval_results.json").read_text(encoding="utf-8"))
    if expected_exit == 2:
        assert payload["summary"]["all_suites_meet_thresholds"] is False
    else:
        assert payload["summary"]["all_suites_meet_thresholds"] is True


def test_cli_eval_returns_one_for_empty_dataset_directory(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_datasets"
    empty_dir.mkdir()
    out_dir = tmp_path / "out"
    code = main(["eval", "--datasets-dir", str(empty_dir), "--out-dir", str(out_dir)])
    assert code == 1


def test_cli_eval_rejects_invalid_threshold_values(
    write_suite_file, minimal_suite_payload: dict
) -> None:
    dataset_path = write_suite_file("suite.json", minimal_suite_payload)
    code_a = main(["eval", "--dataset", str(dataset_path), "--min-pass-rate", "1.2"])
    code_b = main(["eval", "--dataset", str(dataset_path), "--min-average-score", "-0.1"])
    assert code_a == 1
    assert code_b == 1


def test_cli_eval_rejects_unknown_adapter(write_suite_file, minimal_suite_payload: dict) -> None:
    dataset_path = write_suite_file("suite.json", minimal_suite_payload)
    with pytest.raises(SystemExit):
        main(["eval", "--dataset", str(dataset_path), "--adapter", "unknown"])
