"""Minimal end-to-end runner for the first scaffold slice."""

from __future__ import annotations

from statistics import mean

from ai_quality_lab.adapters import AdapterName, ModelAdapter, case_to_request, get_adapter
from ai_quality_lab.models import CaseOutcome, CheckOutcome, EvalCase, EvalSuite, SuiteOutcome
from ai_quality_lab.scorers.simple import ScorerRegistry, default_registry


def run_suite(
    suite: EvalSuite,
    adapter: ModelAdapter | None = None,
    adapter_name: AdapterName = "dataset",
) -> SuiteOutcome:
    selected_adapter = adapter if adapter is not None else get_adapter(adapter_name)
    scorers = default_registry()
    cases = [_run_case(case, scorers, selected_adapter) for case in suite.cases]
    passed = sum(1 for case in cases if case.passed)
    total = len(cases)
    average = mean([case.score for case in cases]) if cases else 0.0
    return SuiteOutcome(
        suite_name=suite.suite_name,
        total_cases=total,
        passed_cases=passed,
        pass_rate=(passed / total) if total else 0.0,
        average_score=average,
        cases=cases,
    )


def _run_case(case: EvalCase, scorers: ScorerRegistry, adapter: ModelAdapter) -> CaseOutcome:
    request = case_to_request(case)
    adapter_output = adapter.generate(request)
    prediction = (
        adapter_output
        if adapter_output is not None
        else (case.prediction if case.prediction is not None else case.expected.reference_value())
    )
    check_outcomes: list[CheckOutcome] = []
    for check in case.checks:
        check_outcomes.append(scorers.score_check(case, prediction, check.type, check.config))
    passed = all(check.passed for check in check_outcomes)
    score = mean([check.score for check in check_outcomes]) if check_outcomes else 0.0
    return CaseOutcome(
        case_id=case.id,
        task=case.task,
        passed=passed,
        score=score,
        prediction=prediction,
        checks=check_outcomes,
    )


def run_simple_suite(
    suite: EvalSuite,
    adapter: ModelAdapter | None = None,
    adapter_name: AdapterName = "dataset",
) -> SuiteOutcome:
    """Backward-compatible alias for older naming."""
    return run_suite(suite=suite, adapter=adapter, adapter_name=adapter_name)
