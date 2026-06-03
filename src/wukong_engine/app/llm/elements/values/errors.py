"""LLM Errors."""


class LLMError(Exception):
    """Base error for LLM-related issues."""


class LLMConfigurationError(LLMError):
    """Configuration issues with the LLM client."""


class LLMTransientError(LLMError):
    """Transient errors that may succeed on retry."""


class LLMResponseError(LLMError):
    """Errors from the LLM response."""
