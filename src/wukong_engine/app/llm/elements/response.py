"""Response model for LLM interactions."""

from dataclasses import dataclass

from wukong_engine.app.data_extraction.elements.values import TokenUsageMetrics


@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    content: str
    model: str
    metrics: TokenUsageMetrics
