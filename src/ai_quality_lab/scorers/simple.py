"""Deterministic scorer implementations and lightweight dispatch."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from ai_quality_lab.models import CheckOutcome, EvalCase, ExtractionExpected


class Scorer(Protocol):
    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        """Score one case deterministically."""


def _ensure_list_of_str(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list[str].")
    return value


def _ensure_score_threshold(value: Any, field_name: str) -> float:
    threshold = float(value)
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0.")
    return threshold


class ExactMatchScorer:
    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        case_sensitive = bool(config.get("case_sensitive", True))
        expected = case.expected.reference_value()
        actual = prediction
        if isinstance(expected, str) and isinstance(actual, str) and not case_sensitive:
            expected = expected.lower()
            actual = actual.lower()
        passed = expected == actual
        return CheckOutcome(
            check_type="exact_match",
            passed=passed,
            score=1.0 if passed else 0.0,
            explanation="Prediction matches expected exactly." if passed else "Prediction differs from expected.",
            details={"expected": case.expected.reference_value(), "actual": prediction},
        )


class AllowedLabelScorer:
    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        expected_label = case.expected.reference_value()
        allowed = config.get("allowed_labels")
        if not isinstance(allowed, list):
            expected_allowed = getattr(case.expected, "allowed_labels", [])
            allowed = expected_allowed if isinstance(expected_allowed, list) else []
        allowed = _ensure_list_of_str(allowed, "allowed_labels")
        if not allowed:
            raise ValueError("allowed_labels cannot be empty.")

        is_allowed = isinstance(prediction, str) and prediction in allowed
        matches_expected = prediction == expected_label
        passed = is_allowed and matches_expected
        score = 1.0 if passed else (0.5 if is_allowed else 0.0)
        if passed:
            explanation = "Prediction is in allowed labels and matches expected label."
        elif is_allowed:
            explanation = "Prediction is allowed but does not match expected label."
        else:
            explanation = "Prediction is outside the allowed label set."
        return CheckOutcome(
            check_type="allowed_labels",
            passed=passed,
            score=score,
            explanation=explanation,
            details={"allowed_labels": allowed, "expected": expected_label, "actual": prediction},
        )


class RegexConstraintsScorer:
    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        text = prediction if isinstance(prediction, str) else str(prediction)
        patterns = _ensure_list_of_str(config.get("patterns", []), "patterns")
        required_terms = _ensure_list_of_str(config.get("required_terms", []), "required_terms")
        forbidden_terms = _ensure_list_of_str(config.get("forbidden_terms", []), "forbidden_terms")
        min_length = int(config.get("min_length", 0))
        max_length = int(config["max_length"]) if "max_length" in config else None
        if min_length < 0:
            raise ValueError("min_length must be >= 0.")
        if max_length is not None and max_length < min_length:
            raise ValueError("max_length must be >= min_length.")

        missing_patterns: list[str] = []
        invalid_patterns: list[str] = []
        for pattern in patterns:
            try:
                if re.search(pattern, text) is None:
                    missing_patterns.append(pattern)
            except re.error:
                invalid_patterns.append(pattern)
        missing_terms = [t for t in required_terms if t not in text]
        forbidden_hits = [t for t in forbidden_terms if t in text]
        length_ok = len(text) >= min_length and (max_length is None or len(text) <= max_length)

        total_checks = max(1, len(patterns) + len(required_terms) + len(forbidden_terms) + 1)
        failures = len(missing_patterns) + len(invalid_patterns) + len(missing_terms) + len(forbidden_hits) + (
            0 if length_ok else 1
        )
        score = max(0.0, 1.0 - failures / total_checks)
        passed = failures == 0

        if passed:
            explanation = "Prediction satisfies all regex and constraint checks."
        else:
            explanation = (
                f"Constraint failures: patterns={len(missing_patterns)}, "
                f"invalid_patterns={len(invalid_patterns)}, "
                f"required_terms={len(missing_terms)}, forbidden_terms={len(forbidden_hits)}, "
                f"length_ok={length_ok}."
            )

        return CheckOutcome(
            check_type="regex_constraints",
            passed=passed,
            score=round(score, 4),
            explanation=explanation,
            details={
                "missing_patterns": missing_patterns,
                "invalid_patterns": invalid_patterns,
                "missing_terms": missing_terms,
                "forbidden_hits": forbidden_hits,
                "length": len(text),
                "min_length": min_length,
                "max_length": max_length,
            },
        )


class SchemaValidationScorer:
    _TYPE_MAP = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }

    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        schema = config.get("schema")
        if not isinstance(schema, dict):
            raise ValueError("schema_validation requires a 'schema' object.")
        value = _coerce_json(prediction)
        errors = self._validate(schema, value, "$")
        passed = len(errors) == 0
        return CheckOutcome(
            check_type="schema_validation",
            passed=passed,
            score=1.0 if passed else 0.0,
            explanation="Schema is valid." if passed else f"Schema validation failed with {len(errors)} error(s).",
            details={"errors": errors, "actual": value},
        )

    def _validate(self, schema: dict[str, Any], value: Any, path: str) -> list[str]:
        errors: list[str] = []
        expected_type = schema.get("type")
        if isinstance(expected_type, str):
            py_type = self._TYPE_MAP.get(expected_type)
            if py_type is None:
                errors.append(f"{path}: unsupported type '{expected_type}'.")
                return errors
            if not _is_schema_type_match(expected_type, value, py_type):
                errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}.")
                return errors

        if schema.get("type") == "object":
            props = schema.get("properties", {})
            required = schema.get("required", [])
            if not isinstance(props, dict):
                errors.append(f"{path}: properties must be object.")
                return errors
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required key '{key}'.")
            for key, child in props.items():
                if key in value and isinstance(child, dict):
                    errors.extend(self._validate(child, value[key], f"{path}.{key}"))

        if schema.get("type") == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                for idx, item in enumerate(value):
                    errors.extend(self._validate(items, item, f"{path}[{idx}]"))

        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and value not in enum_values:
            errors.append(f"{path}: value '{value}' not in enum {enum_values}.")
        return errors


class FieldExtractionScorer:
    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        if not isinstance(case.expected, ExtractionExpected):
            raise ValueError("field_extraction scorer requires extraction expected output.")
        expected_fields = case.expected.fields
        required_fields = config.get("required_fields", case.expected.required_fields)
        required_fields = _ensure_list_of_str(required_fields, "required_fields")
        if not required_fields:
            raise ValueError("required_fields cannot be empty.")

        actual = _coerce_json(prediction)
        if not isinstance(actual, dict):
            return CheckOutcome(
                check_type="field_extraction",
                passed=False,
                score=0.0,
                explanation="Prediction is not a structured object.",
                details={"actual": actual},
            )

        matches = 0
        mismatches: dict[str, dict[str, Any]] = {}
        for field in required_fields:
            if actual.get(field) == expected_fields.get(field):
                matches += 1
            else:
                mismatches[field] = {
                    "expected": expected_fields.get(field),
                    "actual": actual.get(field),
                }

        total = len(required_fields)
        score = (matches / total) if total else 0.0
        passing_score = _ensure_score_threshold(config.get("passing_score", 1.0), "passing_score")
        passed = score >= passing_score
        explanation = (
            "All required fields match expected values."
            if passed
            else f"{matches}/{total} required fields matched."
        )
        return CheckOutcome(
            check_type="field_extraction",
            passed=passed,
            score=round(score, 4),
            explanation=explanation,
            details={
                "matched_fields": matches,
                "total_required_fields": total,
                "mismatches": mismatches,
            },
        )


class RubricScorer:
    def score(self, case: EvalCase, prediction: Any, config: dict[str, Any]) -> CheckOutcome:
        criteria = config.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError("rubric requires non-empty 'criteria' list.")
        text = prediction if isinstance(prediction, str) else str(prediction)
        passing_score = _ensure_score_threshold(config.get("passing_score", 0.7), "passing_score")

        total_weight = 0.0
        earned_weight = 0.0
        criterion_results: list[dict[str, Any]] = []
        for item in criteria:
            if not isinstance(item, dict):
                raise ValueError("each rubric criterion must be an object.")
            name = str(item.get("name", "criterion"))
            weight = float(item.get("weight", 1.0))
            if weight <= 0:
                raise ValueError("rubric criterion weight must be > 0.")
            required_terms = item.get("required_terms", [])
            forbidden_terms = item.get("forbidden_terms", [])
            required_terms = _ensure_list_of_str(required_terms, "rubric.required_terms")
            forbidden_terms = _ensure_list_of_str(forbidden_terms, "rubric.forbidden_terms")

            has_required = all(term in text for term in required_terms)
            avoids_forbidden = all(term not in text for term in forbidden_terms)
            criterion_passed = has_required and avoids_forbidden
            total_weight += weight
            if criterion_passed:
                earned_weight += weight
            criterion_results.append(
                {"name": name, "weight": weight, "passed": criterion_passed}
            )

        score = (earned_weight / total_weight) if total_weight else 0.0
        passed = score >= passing_score
        explanation = (
            f"Rubric score {score:.2f} meets threshold {passing_score:.2f}."
            if passed
            else f"Rubric score {score:.2f} below threshold {passing_score:.2f}."
        )
        return CheckOutcome(
            check_type="rubric",
            passed=passed,
            score=round(score, 4),
            explanation=explanation,
            details={"criteria": criterion_results, "passing_score": passing_score},
        )


@dataclass(slots=True)
class ScorerRegistry:
    scorers: dict[str, Scorer]

    def get(self, check_type: str) -> Scorer:
        scorer = self.scorers.get(check_type)
        if scorer is None:
            raise KeyError(f"Unknown scorer type: {check_type}")
        return scorer

    def score_check(self, case: EvalCase, prediction: Any, check_type: str, config: dict[str, Any]) -> CheckOutcome:
        scorer = self.get(check_type)
        return scorer.score(case, prediction, config)


def recommended_scorers_for_task(task: str) -> list[str]:
    task_map: dict[str, list[str]] = {
        "summarization": ["rubric", "regex_constraints", "exact_match"],
        "classification": ["allowed_labels", "exact_match"],
        "extraction": ["schema_validation", "field_extraction"],
        "compliance": ["allowed_labels", "regex_constraints", "rubric"],
    }
    return task_map.get(task, ["exact_match"])


def default_registry() -> ScorerRegistry:
    return ScorerRegistry(
        scorers={
            "exact_match": ExactMatchScorer(),
            "allowed_labels": AllowedLabelScorer(),
            "regex_constraints": RegexConstraintsScorer(),
            "schema_validation": SchemaValidationScorer(),
            "field_extraction": FieldExtractionScorer(),
            "rubric": RubricScorer(),
        }
    )


def _coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _is_schema_type_match(expected_type: str, value: Any, py_type: type[Any] | tuple[type[Any], ...]) -> bool:
    # Avoid bool passing as integer/number because bool is subclass of int.
    if expected_type in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, py_type)
