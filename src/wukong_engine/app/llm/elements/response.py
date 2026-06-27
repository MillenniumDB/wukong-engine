"""Response model for LLM interactions."""

from dataclasses import dataclass

from wukong_engine.app.data_extraction.elements.values import TokenUsageMetrics
from wukong_engine.app.llm.model.values import LLMProvider


@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    content: str
    model: str
    metrics: TokenUsageMetrics


@dataclass(frozen=True)
class LLMBatchCreationResponse:
    """Response envelope returned by an LLM client for batch creation."""

    batch_id: str
    provider: LLMProvider


@dataclass(frozen=True)
class LLMBatchResult:
    """Response envelope returned by an LLM client for individual batch results."""

    job_id: str
    response: LLMResponse | None
    error: str | None = None
