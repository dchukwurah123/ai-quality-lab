"""Command line interface for ai-quality-lab."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_quality_lab.adapters import AdapterName
from ai_quality_lab.loaders import DatasetError, load_suite
from ai_quality_lab.models import SuiteOutcome
from ai_quality_lab.runner import run_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-quality-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run deterministic evaluation for one dataset file or a dataset directory.",
    )
    source_group = eval_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--dataset", help="Path to one dataset file (.json/.yaml/.yml).")
    source_group.add_argument(
        "--datasets-dir",
        help="Path to a directory containing dataset files.",
    )
    eval_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search dataset directory.",
    )
    eval_parser.add_argument(
        "--out-dir",
        default="reports",
        help="Directory where JSON and markdown reports are written.",
    )
    eval_parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=0.0,
        help="Threshold in [0,1]. Exit non-zero if any suite pass_rate is below this value.",
    )
    eval_parser.add_argument(
        "--min-average-score",
        type=float,
        default=0.0,
        help="Threshold in [0,1]. Exit non-zero if any suite average_score is below this value.",
    )
    eval_parser.add_argument(
        "--adapter",
        choices=["dataset", "echo", "mock"],
        default="dataset",
        help="Adapter used to generate predictions (default: dataset).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "eval":
            return _eval(
                dataset=args.dataset,
                datasets_dir=args.datasets_dir,
                recursive=args.recursive,
                out_dir=args.out_dir,
                min_pass_rate=args.min_pass_rate,
                min_average_score=args.min_average_score,
                adapter_name=args.adapter,
            )
        parser.print_help()
        return 1
    except (ValueError, FileNotFoundError, DatasetError) as exc:
        print(f"ERROR: {exc}")
        return 1


def _eval(
    dataset: str | None,
    datasets_dir: str | None,
    recursive: bool,
    out_dir: str,
    min_pass_rate: float,
    min_average_score: float,
    adapter_name: AdapterName,
) -> int:
    if not (0.0 <= min_pass_rate <= 1.0):
        raise ValueError("--min-pass-rate must be between 0 and 1.")
    if not (0.0 <= min_average_score <= 1.0):
        raise ValueError("--min-average-score must be between 0 and 1.")

    dataset_paths = _resolve_dataset_paths(dataset, datasets_dir, recursive)
    if not dataset_paths:
        print("No dataset files found.")
        return 1

    suite_results = []
    suite_summaries = []
    total_cases = 0
    for dataset_path in dataset_paths:
        suite = load_suite(dataset_path)
        outcome = run_suite(suite, adapter_name=adapter_name)
        total_cases += outcome.total_cases
        task_types = sorted({case.task for case in outcome.cases})
        pass_count = outcome.passed_cases
        fail_count = outcome.total_cases - pass_count
        top_failure_reasons = _top_failure_reasons(outcome)
        suite_results.append(
            {
                "dataset_path": str(dataset_path),
                "result": outcome.to_dict(),
            }
        )
        meets = _suite_meets_thresholds(
            outcome.pass_rate,
            outcome.average_score,
            min_pass_rate,
            min_average_score,
        )
        suite_summaries.append(
            {
                "suite_name": outcome.suite_name,
                "dataset_path": str(dataset_path),
                "task_types": task_types,
                "total_cases": outcome.total_cases,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "pass_rate": outcome.pass_rate,
                "average_score": outcome.average_score,
                "top_failure_reasons": top_failure_reasons,
                "meets_thresholds": meets,
            }
        )

    all_meet_thresholds = all(summary["meets_thresholds"] for summary in suite_summaries)
    summary_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": {
            "min_pass_rate": min_pass_rate,
            "min_average_score": min_average_score,
        },
        "summary": {
            "suite_count": len(suite_results),
            "total_cases": total_cases,
            "suites_meeting_thresholds": sum(
                1 for summary in suite_summaries if summary["meets_thresholds"]
            ),
            "all_suites_meet_thresholds": all_meet_thresholds,
        },
        "suites": suite_results,
    }

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "eval_results.json"
    md_path = output_dir / "eval_summary.md"
    json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    md_path.write_text(
        _build_markdown_summary(
            suite_summaries,
            min_pass_rate,
            min_average_score,
            all_meet_thresholds,
        ),
        encoding="utf-8",
    )

    _print_console_summary(suite_summaries, min_pass_rate, min_average_score, json_path, md_path)
    return 0 if all_meet_thresholds else 2


def _resolve_dataset_paths(
    dataset: str | None, datasets_dir: str | None, recursive: bool
) -> list[Path]:
    if dataset:
        return [Path(dataset)]
    if datasets_dir is None:
        return []
    base = Path(datasets_dir)
    if not base.exists():
        raise FileNotFoundError(f"Dataset directory not found: {base}")
    pattern = "**/*" if recursive else "*"
    paths = [
        path
        for path in sorted(base.glob(pattern))
        if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml"}
    ]
    return paths


def _suite_meets_thresholds(
    pass_rate: float, average_score: float, min_pass_rate: float, min_average_score: float
) -> bool:
    return pass_rate >= min_pass_rate and average_score >= min_average_score


def _build_markdown_summary(
    suite_summaries: list[dict[str, Any]],
    min_pass_rate: float,
    min_average_score: float,
    all_meet_thresholds: bool,
) -> str:
    total_cases = sum(int(suite["total_cases"]) for suite in suite_summaries)
    suites_meeting = sum(1 for suite in suite_summaries if suite["meets_thresholds"])
    table_header = (
        "| Suite Name | Task Type(s) | Total Cases | Pass Count | "
        "Fail Count | Average Score | Top Failure Reasons | Status |"
    )
    lines = [
        "# Evaluation Summary",
        "",
        f"- Min pass rate threshold: {min_pass_rate:.2f}",
        f"- Min average score threshold: {min_average_score:.2f}",
        f"- Threshold status: {'PASS' if all_meet_thresholds else 'FAIL'}",
        f"- Suites processed: {len(suite_summaries)}",
        f"- Total cases: {total_cases}",
        f"- Suites meeting thresholds: {suites_meeting}/{len(suite_summaries)}",
        "",
        "## Suite Summary",
        "",
        table_header,
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for suite in suite_summaries:
        status = "PASS" if suite["meets_thresholds"] else "FAIL"
        if suite["task_types"]:
            task_types = ", ".join(str(task) for task in suite["task_types"])
        else:
            task_types = "-"
        failure_reasons = suite["top_failure_reasons"]
        if isinstance(failure_reasons, list) and failure_reasons:
            reasons_text = "; ".join(str(reason) for reason in failure_reasons)
        else:
            reasons_text = "None"
        lines.append(
            f"| {suite['suite_name']} | {task_types} | {int(suite['total_cases'])} | "
            f"{int(suite['pass_count'])} | {int(suite['fail_count'])} | "
            f"{float(suite['average_score']):.2f} | {reasons_text} | {status} |"
        )
    lines.extend(["", "## Datasets", ""])
    for suite in suite_summaries:
        lines.append(f"- `{suite['suite_name']}`: `{suite['dataset_path']}`")
    return "\n".join(lines) + "\n"


def _print_console_summary(
    suite_summaries: list[dict[str, Any]],
    min_pass_rate: float,
    min_average_score: float,
    json_path: Path,
    md_path: Path,
) -> None:
    print(
        "Thresholds: "
        f"min_pass_rate={min_pass_rate:.2f}, min_average_score={min_average_score:.2f}"
    )
    for suite in suite_summaries:
        status = "PASS" if suite["meets_thresholds"] else "FAIL"
        print(
            f"[{status}] {suite['suite_name']}: "
            f"cases={int(suite['total_cases'])}, "
            f"pass={int(suite['pass_count'])}, "
            f"fail={int(suite['fail_count'])}, "
            f"avg_score={float(suite['average_score']):.2f} "
            f"({suite['dataset_path']})"
        )
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")


def _top_failure_reasons(suite_result: SuiteOutcome, max_reasons: int = 3) -> list[str]:
    cases = suite_result.cases
    counter: Counter[str] = Counter()
    for case in cases:
        if case.passed:
            continue
        for check in case.checks:
            if check.passed:
                continue
            if isinstance(check.explanation, str) and check.explanation.strip():
                key = f"{check.check_type}: {check.explanation.strip()}"
            else:
                key = str(check.check_type)
            counter[key] += 1
    return [reason for reason, _ in counter.most_common(max_reasons)]


if __name__ == "__main__":
    raise SystemExit(main())
