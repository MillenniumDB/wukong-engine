"""Decorators for translating OpenAI SDK errors into LLM port exceptions."""

from collections.abc import Awaitable, Callable
from functools import wraps

from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)


def translate_openai_errors[T](fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Translate OpenAI API errors into custom LLM exceptions.

    Authentication and invalid-request errors become ``LLMConfigurationError``; rate limits, timeouts, connection
    failures and server-side errors become ``LLMTransientError``; ``LLMResponseError`` is propagated unchanged; any
    other error becomes ``LLMInternalError``.

    Args:
        fn: Async function whose errors are translated.

    Returns:
        An async wrapper around ``fn`` that raises only LLM port exceptions.
    """

    @wraps(fn)
    async def wrapper(*args: object, **kwargs: object) -> T:
        """Await the wrapped function and translate any error it raises."""
        try:
            return await fn(*args, **kwargs)
        except AuthenticationError as exc:
            raise LLMConfigurationError(f'Authentication with the LLM provider failed: {exc}') from exc
        except RateLimitError as exc:
            raise LLMTransientError(f'The LLM provider rate limit was exceeded: {exc}') from exc
        except APITimeoutError as exc:
            raise LLMTransientError(f'The LLM request timed out: {exc}') from exc
        except APIConnectionError as exc:
            raise LLMTransientError(f'Failed to connect to the LLM provider: {exc}') from exc
        except APIStatusError as exc:
            if exc.status_code in {400, 401, 403, 404, 422}:
                raise LLMConfigurationError(f'Invalid request for the LLM provider: {exc}') from exc
            if exc.status_code >= 500:  # noqa: PLR2004
                raise LLMTransientError(f'The LLM provider returned a server-side error: {exc}') from exc
            raise LLMInternalError(f'Unexpected LLM provider status error: {exc}') from exc
        except LLMResponseError:
            raise
        except Exception as exc:
            raise LLMInternalError(
                f'An unexpected error occurred while interacting with the LLM provider: {exc}',
            ) from exc

    return wrapper
