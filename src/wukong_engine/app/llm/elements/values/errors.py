"""LLM Errors."""

from enum import Enum


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
