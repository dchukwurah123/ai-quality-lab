from ai_quality_lab.loaders import load_suite
from ai_quality_lab.runner import run_suite


def test_all_task_example_suites_run_end_to_end() -> None:
    paths = [
        "datasets/summarization_examples.json",
        "datasets/classification_examples.yaml",
        "datasets/extraction_examples.json",
        "datasets/compliance_examples.yaml",
    ]
    results = [run_suite(load_suite(path), adapter_name="mock") for path in paths]
    assert len(results) == 4
    assert all(result.total_cases > 0 for result in results)


def test_failed_checks_include_explanations() -> None:
    suite = load_suite("datasets/minimal_suite.json")
    suite.cases[0].prediction = "clearly wrong"
    result = run_suite(suite, adapter_name="dataset")
    failed_checks = [
        check
        for case in result.cases
        for check in case.checks
        if not check.passed
    ]
    assert failed_checks
    assert all(check.explanation.strip() for check in failed_checks)
