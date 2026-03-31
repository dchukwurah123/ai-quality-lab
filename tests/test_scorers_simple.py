import pytest

from ai_quality_lab.models import (
    ClassificationExpected,
    ComplianceExpected,
    EvalCase,
    EvalCheck,
    ExtractionExpected,
    SummarizationExpected,
)
from ai_quality_lab.scorers.simple import default_registry, recommended_scorers_for_task


@pytest.mark.parametrize(
    ("prediction", "config", "passed", "score"),
    [
        ("Hello", {"case_sensitive": True}, True, 1.0),
        ("hello", {"case_sensitive": True}, False, 0.0),
        ("hello", {"case_sensitive": False}, True, 1.0),
    ],
)
def test_exact_match_variants(prediction: str, config: dict, passed: bool, score: float) -> None:
    case = EvalCase(
        id="sum",
        task="summarization",
        input={"text": "x"},
        expected=SummarizationExpected("Hello"),
        checks=[EvalCheck(type="exact_match")],
    )
    result = default_registry().score_check(case, prediction, "exact_match", config)
    assert result.passed is passed
    assert result.score == score


def test_allowed_labels_partial_score() -> None:
    case = EvalCase(
        id="cls",
        task="classification",
        input={"text": "x"},
        expected=ClassificationExpected("support", ["support", "billing"]),
        checks=[EvalCheck(type="allowed_labels")],
    )
    result = default_registry().score_check(case, "billing", "allowed_labels", {})
    assert result.passed is False
    assert result.score == 0.5
    assert "allowed" in result.explanation.lower()


def test_regex_constraints_partial_score() -> None:
    case = EvalCase(
        id="cmp",
        task="compliance",
        input={"text": "x"},
        expected=ComplianceExpected("compliant"),
        checks=[EvalCheck(type="regex_constraints")],
    )
    result = default_registry().score_check(
        case,
        "short answer",
        "regex_constraints",
        {"required_terms": ["must-have"], "min_length": 20},
    )
    assert result.passed is False
    assert 0.0 < result.score < 1.0


def test_schema_validation_and_field_extraction() -> None:
    case = EvalCase(
        id="ext",
        task="extraction",
        input={"text": "x"},
        expected=ExtractionExpected({"email": "a@b.com", "plan": "starter"}, ["email", "plan"]),
        checks=[EvalCheck(type="schema_validation"), EvalCheck(type="field_extraction")],
    )
    registry = default_registry()
    schema_result = registry.score_check(
        case,
        {"email": "a@b.com", "plan": "pro"},
        "schema_validation",
        {
            "schema": {
                "type": "object",
                "required": ["email", "plan"],
                "properties": {
                    "email": {"type": "string"},
                    "plan": {"type": "string"},
                },
            }
        },
    )
    field_result = registry.score_check(
        case,
        {"email": "a@b.com", "plan": "pro"},
        "field_extraction",
        {"passing_score": 0.6},
    )
    assert schema_result.passed is True
    assert field_result.passed is False
    assert field_result.score == 0.5


def test_rubric_weighted_scoring() -> None:
    case = EvalCase(
        id="sum-rubric",
        task="summarization",
        input={"text": "x"},
        expected=SummarizationExpected("n/a"),
        checks=[EvalCheck(type="rubric")],
    )
    result = default_registry().score_check(
        case,
        "mentions timeline only",
        "rubric",
        {
            "passing_score": 0.7,
            "criteria": [
                {"name": "timeline", "weight": 2, "required_terms": ["timeline"]},
                {"name": "risk", "weight": 1, "required_terms": ["risk"]},
            ],
        },
    )
    assert result.passed is False
    assert result.score == 0.6667


def test_task_mapping_is_explicit_and_predictable() -> None:
    assert recommended_scorers_for_task("summarization") == [
        "rubric",
        "regex_constraints",
        "exact_match",
    ]
    assert recommended_scorers_for_task("classification") == ["allowed_labels", "exact_match"]


def test_unknown_scorer_type_raises_clear_error() -> None:
    case = EvalCase(
        id="unknown",
        task="summarization",
        input={"text": "x"},
        expected=SummarizationExpected("x"),
        checks=[EvalCheck(type="does_not_exist")],
    )
    with pytest.raises(KeyError, match="Unknown scorer type"):
        default_registry().score_check(case, "x", "does_not_exist", {})


def test_rubric_rejects_invalid_weight() -> None:
    case = EvalCase(
        id="sum-bad-rubric",
        task="summarization",
        input={"text": "x"},
        expected=SummarizationExpected("n/a"),
        checks=[EvalCheck(type="rubric")],
    )
    with pytest.raises(ValueError, match="weight must be > 0"):
        default_registry().score_check(
            case,
            "anything",
            "rubric",
            {"criteria": [{"name": "bad", "weight": 0, "required_terms": []}]},
        )
