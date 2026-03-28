"""Response model for LLM interactions."""

from dataclasses import dataclass
from typing import Any

from .values import LLMError


@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    success: bool
    content: str
    structured: dict[str, Any] | None = None
    error: LLMError | None = None
