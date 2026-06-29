"""Response model for LLM interactions."""

from dataclasses import dataclass
from typing import Any

from wukong_engine.app.llm.model.values import LLMProvider


@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    content: str
    model: str
    metrics: dict[str, Any]


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
