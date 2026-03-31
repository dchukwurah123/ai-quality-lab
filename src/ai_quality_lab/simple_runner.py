"""Backward-compatible wrapper for renamed runner module."""

from ai_quality_lab.runner import run_suite


def run_simple_suite(*args, **kwargs):
    """Backward-compatible alias for older naming."""
    return run_suite(*args, **kwargs)
