"""Optional OpenAI adapter kept isolated from core harness code.

This module is intentionally optional: core evaluation must run without it.
"""

from __future__ import annotations

import os
from typing import Any

from ai_quality_lab.adapters.simple import ModelAdapter, ModelRequest


class OpenAIAdapter(ModelAdapter):
    """Optional adapter stub for future provider integration."""

    name = "openai"

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError(
                "OpenAI adapter requires the optional 'openai' package and API credentials."
            ) from exc
        self._client = OpenAI(api_key=self.api_key)

    @classmethod
    def from_env(cls) -> "OpenAIAdapter":
        """Build adapter from environment variables.

        Required:
        - OPENAI_API_KEY

        Optional:
        - AI_QUALITY_LAB_OPENAI_MODEL (default: gpt-4o-mini)
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required to use OpenAIAdapter.")
        model = os.getenv("AI_QUALITY_LAB_OPENAI_MODEL", "gpt-4o-mini")
        return cls(model=model, api_key=api_key)

    def generate(self, request: ModelRequest) -> Any | None:
        response = self._client.responses.create(
            model=self.model,
            input=f"Task: {request.task}\nInput: {request.input}",
        )
        return response.output_text
