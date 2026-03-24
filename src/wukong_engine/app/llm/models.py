"""Request and response models for LLM interactions."""

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from .values import LLMError, ResponseFormat, RetryPolicy


@dataclass(frozen=True)
class LLMRequest:
    """Fully rendered request to be executed by an LLM provider."""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.0  # Default: Most deterministic
    max_output_tokens: int = 32768  # Default: Output limit for GPT-4.1 mini
    response_format: ResponseFormat = field(default_factory=ResponseFormat)  # Default: Free-form text response
    retry_policy: RetryPolicy | None = None  # Default: Use the provider's default retry policy

    def __post_init__(self) -> None:
        """Validate request values at construction time."""
        if not isfinite(self.temperature):
            raise ValueError('temperature must be a finite number')
        if self.temperature < 0:
            raise ValueError('temperature must be greater than or equal to 0')
        if self.max_output_tokens <= 0:
            raise ValueError('max_output_tokens must be greater than 0')


@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    success: bool
    content: str
    structured: dict[str, Any] | None = None
    error: LLMError | None = None
