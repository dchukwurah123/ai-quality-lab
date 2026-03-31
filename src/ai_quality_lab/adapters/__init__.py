"""Optional and local model adapters."""

from ai_quality_lab.adapters.simple import (
    AdapterName,
    ModelAdapter,
    ModelRequest,
    case_to_request,
    get_adapter,
)

__all__ = [
    "AdapterName",
    "ModelAdapter",
    "ModelRequest",
    "case_to_request",
    "get_adapter",
]
