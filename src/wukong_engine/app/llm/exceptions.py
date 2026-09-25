"""LLM Exceptions."""

from wukong_engine.app.shared.exceptions import ApplicationError


class LLMError(ApplicationError):
    """Base error for LLM-related issues."""


class LLMConfigurationError(LLMError):
    """Configuration issues with the LLM client."""


class LLMTransientError(LLMError):
    """Transient errors that may succeed on retry."""


class LLMResponseError(LLMError):
    """Errors related to the LLM response, such as incomplete responses or refusals."""


class LLMInternalError(LLMError):
    """Internal errors that indicate an unexpected problem within the LLM client or processing."""
