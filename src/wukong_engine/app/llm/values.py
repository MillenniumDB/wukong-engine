"""Value objects and enums used by the LLM layer."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any


# Request/Response Values
class ResponseFormatType(Enum):
    """Response format types for LLM outputs.

    Attributes:
        JSON: Structured output.
        TEXT: Free-form text.
    """

    JSON = 'json'
    TEXT = 'text'


@dataclass(frozen=True)
class ResponseFormat:
    """Defines the expected format of the LLM response."""

    type: ResponseFormatType = ResponseFormatType.TEXT
    schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class RetryPolicy:
    """Controls retry behavior at the transport level for LLM calls."""

    max_attempts: int = 10
    initial_delay: float = 1  # Seconds
    delay_multiplier: float = 2  # Seconds
    max_delay: float = 120  # Seconds

    def __post_init__(self) -> None:
        """Validate retry policy values at construction time."""
        if self.max_attempts <= 0:
            raise ValueError('max_attempts must be greater than 0')
        if self.initial_delay <= 0:
            raise ValueError('initial_delay must be greater than 0')
        if self.delay_multiplier < 1:
            raise ValueError('delay_multiplier must be greater than or equal to 1')
        if self.max_delay < self.initial_delay:
            raise ValueError('max_delay must be greater than or equal to initial_delay')

        for field_name, value in (
            ('initial_delay', self.initial_delay),
            ('delay_multiplier', self.delay_multiplier),
            ('max_delay', self.max_delay),
        ):
            if not isfinite(value):
                raise ValueError(f'{field_name} must be a finite number')


# Errors
class LLMError(Enum):
    """Common error types for LLM interactions.

    Attributes:
        TIMEOUT: The request to the LLM timed out.
        RATE_LIMIT: The LLM provider's rate limit was exceeded.
        NETWORK: A network error occurred during the request.
        PROVIDER_ERROR: The LLM provider returned an error response.
        INVALID_RESPONSE: The LLM returned a response that could not be parsed or was in an unexpected format.
    """

    TIMEOUT = 'timeout'
    RATE_LIMIT = 'rate_limit'
    NETWORK = 'network'
    PROVIDER_ERROR = 'provider_error'
    INVALID_RESPONSE = 'invalid_response'
