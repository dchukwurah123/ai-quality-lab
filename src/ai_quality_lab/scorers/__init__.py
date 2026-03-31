"""Public scorer API."""

from ai_quality_lab.scorers.simple import ScorerRegistry, default_registry, recommended_scorers_for_task

__all__ = [
    "ScorerRegistry",
    "default_registry",
    "recommended_scorers_for_task",
]
