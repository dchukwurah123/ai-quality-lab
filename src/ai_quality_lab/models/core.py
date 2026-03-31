"""Core evaluation models with task-specific expected outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TaskType = Literal["summarization", "classification", "extraction", "compliance"]


@dataclass(slots=True)
class ExpectedOutput:
    """Base expected-output model for all tasks."""

    kind: str

    def reference_value(self) -> Any:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SummarizationExpected(ExpectedOutput):
    summary: str

    def __init__(self, summary: str) -> None:
        super().__init__(kind="summarization")
        self.summary = summary

    def reference_value(self) -> str:
        return self.summary


@dataclass(slots=True)
class ClassificationExpected(ExpectedOutput):
    label: str
    allowed_labels: list[str] = field(default_factory=list)

    def __init__(self, label: str, allowed_labels: list[str] | None = None) -> None:
        super().__init__(kind="classification")
        self.label = label
        self.allowed_labels = allowed_labels or []

    def reference_value(self) -> str:
        return self.label


@dataclass(slots=True)
class ExtractionExpected(ExpectedOutput):
    fields: dict[str, Any]
    required_fields: list[str] = field(default_factory=list)

    def __init__(self, fields: dict[str, Any], required_fields: list[str] | None = None) -> None:
        super().__init__(kind="extraction")
        self.fields = fields
        self.required_fields = required_fields or list(fields.keys())

    def reference_value(self) -> dict[str, Any]:
        return self.fields


@dataclass(slots=True)
class ComplianceExpected(ExpectedOutput):
    verdict: Literal["compliant", "non-compliant"]
    policy_id: str | None = None
    required_terms: list[str] = field(default_factory=list)

    def __init__(
        self,
        verdict: Literal["compliant", "non-compliant"],
        policy_id: str | None = None,
        required_terms: list[str] | None = None,
    ) -> None:
        super().__init__(kind="compliance")
        self.verdict = verdict
        self.policy_id = policy_id
        self.required_terms = required_terms or []

    def reference_value(self) -> str:
        return self.verdict


ExpectedOutputType = (
    SummarizationExpected | ClassificationExpected | ExtractionExpected | ComplianceExpected
)


@dataclass(slots=True)
class EvalCheck:
    type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvalCase:
    id: str
    task: TaskType
    input: Any
    expected: ExpectedOutputType
    checks: list[EvalCheck]
    prediction: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "input": self.input,
            "expected": self.expected.to_dict(),
            "checks": [asdict(check) for check in self.checks],
            "prediction": self.prediction,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class EvalSuite:
    suite_name: str
    description: str
    cases: list[EvalCase]

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "description": self.description,
            "cases": [case.to_dict() for case in self.cases],
        }


@dataclass(slots=True)
class CheckOutcome:
    check_type: str
    passed: bool
    score: float
    explanation: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CaseOutcome:
    case_id: str
    task: str
    passed: bool
    score: float
    prediction: Any
    checks: list[CheckOutcome]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "task": self.task,
            "passed": self.passed,
            "score": self.score,
            "prediction": self.prediction,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(slots=True)
class SuiteOutcome:
    suite_name: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    average_score: float
    cases: list[CaseOutcome]

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": self.pass_rate,
            "average_score": self.average_score,
            "cases": [case.to_dict() for case in self.cases],
        }


def parse_expected(task: TaskType, raw_expected: Any) -> ExpectedOutputType:
    """Parse raw dataset expected value into a typed expected model."""
    if task == "summarization":
        if isinstance(raw_expected, str):
            return SummarizationExpected(summary=raw_expected)
        if isinstance(raw_expected, dict) and isinstance(raw_expected.get("summary"), str):
            return SummarizationExpected(summary=raw_expected["summary"])
        raise ValueError("summarization expected must be string or object with 'summary'.")

    if task == "classification":
        if isinstance(raw_expected, str):
            return ClassificationExpected(label=raw_expected)
        if isinstance(raw_expected, dict) and isinstance(raw_expected.get("label"), str):
            labels = raw_expected.get("allowed_labels", [])
            if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
                raise ValueError("classification 'allowed_labels' must be list[str].")
            return ClassificationExpected(label=raw_expected["label"], allowed_labels=labels)
        raise ValueError("classification expected must be string or object with 'label'.")

    if task == "extraction":
        if isinstance(raw_expected, dict):
            if "fields" in raw_expected:
                fields = raw_expected.get("fields")
                required = raw_expected.get("required_fields", [])
                if not isinstance(fields, dict):
                    raise ValueError("extraction expected 'fields' must be object.")
                if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
                    raise ValueError("extraction 'required_fields' must be list[str].")
                return ExtractionExpected(fields=fields, required_fields=required)
            # Concise form: expected itself is fields object.
            return ExtractionExpected(fields=raw_expected)
        raise ValueError("extraction expected must be an object.")

    if task == "compliance":
        if isinstance(raw_expected, str):
            if raw_expected not in {"compliant", "non-compliant"}:
                raise ValueError("compliance expected string must be compliant/non-compliant.")
            return ComplianceExpected(verdict=raw_expected)
        if isinstance(raw_expected, dict):
            verdict = raw_expected.get("verdict")
            if verdict not in {"compliant", "non-compliant"}:
                raise ValueError("compliance expected object requires valid 'verdict'.")
            policy_id = raw_expected.get("policy_id")
            required_terms = raw_expected.get("required_terms", [])
            if policy_id is not None and not isinstance(policy_id, str):
                raise ValueError("compliance 'policy_id' must be string if provided.")
            if not isinstance(required_terms, list) or not all(
                isinstance(x, str) for x in required_terms
            ):
                raise ValueError("compliance 'required_terms' must be list[str].")
            return ComplianceExpected(
                verdict=verdict,
                policy_id=policy_id,
                required_terms=required_terms,
            )
        raise ValueError("compliance expected must be string or object.")

    raise ValueError(f"Unsupported task type: {task}")
