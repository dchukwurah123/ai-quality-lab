"""Simple pluggable adapter interface for local/offline evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ai_quality_lab.models import EvalCase

AdapterName = Literal["dataset", "echo", "mock"]


@dataclass(slots=True)
class ModelRequest:
    """Provider-agnostic request envelope produced from dataset cases."""

    case_id: str
    task: str
    input: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(Protocol):
    """Adapter contract. Returns prediction payload or None."""

    name: str

    def generate(self, request: ModelRequest) -> Any | None:
        """Generate model output for one request."""


class DatasetAdapter:
    """Offline adapter that defers to dataset-provided prediction fallback."""

    name = "dataset"

    def generate(self, request: ModelRequest) -> Any | None:
        # Returning None lets runner use case.prediction -> expected fallback.
        return None


class EchoAdapter:
    """Local dev adapter that echoes text-like input content."""

    name = "echo"

    def generate(self, request: ModelRequest) -> Any | None:
        return _extract_text(request.input)


class MockTaskAdapter:
    """Deterministic task heuristics for local integration testing."""

    name = "mock"

    def generate(self, request: ModelRequest) -> Any | None:
        text = _extract_text(request.input)
        if request.task == "summarization":
            return text.split(".")[0].strip()
        if request.task == "classification":
            lower = text.lower()
            if "refund" in lower or "cancel" in lower:
                return "support"
            if "invoice" in lower or "billing" in lower:
                return "billing"
            return "general"
        if request.task == "extraction":
            match = re.search(r"[\w.+\'-]+@[\w.-]+\.\w+", text)
            return {"email": match.group(0) if match else ""}
        if request.task == "compliance":
            lower = text.lower()
            banned = ("guaranteed cure", "always works", "100% certain")
            return "non-compliant" if any(term in lower for term in banned) else "compliant"
        return text


def case_to_request(case: EvalCase) -> ModelRequest:
    return ModelRequest(
        case_id=case.id,
        task=case.task,
        input=case.input,
        metadata=case.metadata,
    )


def get_adapter(name: AdapterName) -> ModelAdapter:
    adapters: dict[str, ModelAdapter] = {
        "dataset": DatasetAdapter(),
        "echo": EchoAdapter(),
        "mock": MockTaskAdapter(),
    }
    try:
        return adapters[name]
    except KeyError as exc:
        raise ValueError(f"Unknown adapter: {name}") from exc


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "prompt", "content"):
            nested = value.get(key)
            if isinstance(nested, str):
                return nested
    return str(value)
