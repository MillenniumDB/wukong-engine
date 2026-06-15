"""Response model for LLM interactions."""

from dataclasses import dataclass

from .values import LLMResponseMetrics


@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    content: str
    model: str
    metrics: LLMResponseMetrics
