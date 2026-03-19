"""OpenAI adapter implementing the LLM client port."""

import json
import time
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, OpenAIError, RateLimitError

from wukong_engine.app.llm.client import LLMClient
from wukong_engine.app.llm.models import LLMRequest, LLMResponse
from wukong_engine.app.llm.values import LLMError, ResponseFormatType
from wukong_engine.infrastructure.config.settings import Config

DEFAULT_MODEL = 'gpt-4.1-mini'
DEFAULT_TIMEOUT_SECONDS = 120


class OpenAIClient(LLMClient):
    """Adapter that executes LLM requests against the OpenAI Chat Completions API."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: OpenAI | None = None,
    ) -> None:
        """Create an OpenAI-backed LLM adapter.

        Args:
            model: OpenAI model identifier used for calls.
            timeout_seconds: Per-request timeout in seconds.
            client: Optional injected OpenAI client for testing.
        """
        self._model = model
        self._timeout_seconds = timeout_seconds

        if client is None:
            self._client = OpenAI(api_key=Config().get_env('OPENAI_API_KEY'))
        else:
            self._client = client

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate an LLM response from the given request."""
        retry_policy = request.retry_policy
        max_attempts = retry_policy.max_attempts if retry_policy is not None else 1
        delay = retry_policy.initial_delay if retry_policy is not None else 0.0

        for attempt in range(1, max_attempts + 1):
            try:
                completion = self._client.chat.completions.create(**self._build_request_payload(request))
                return self._build_success_response(completion, request)
            except APITimeoutError:
                mapped_error = LLMError.TIMEOUT
                message = 'OpenAI request timed out'
            except RateLimitError:
                mapped_error = LLMError.RATE_LIMIT
                message = 'OpenAI rate limit exceeded'
            except APIConnectionError:
                mapped_error = LLMError.NETWORK
                message = 'Network error calling OpenAI'
            except APIError:
                mapped_error = LLMError.PROVIDER_ERROR
                message = 'OpenAI provider returned an API error'
            except OpenAIError:
                mapped_error = LLMError.PROVIDER_ERROR
                message = 'OpenAI client error'
            except (TypeError, ValueError):
                mapped_error = LLMError.PROVIDER_ERROR
                message = 'Unexpected error calling OpenAI'

            if attempt >= max_attempts:
                return LLMResponse(success=False, content=message, error=mapped_error)

            if retry_policy is not None:
                time.sleep(delay)
                delay = min(delay * retry_policy.delay_multiplier, retry_policy.max_delay)

        return LLMResponse(success=False, content='Unreachable retry state', error=LLMError.PROVIDER_ERROR)

    def _build_request_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Build OpenAI API arguments from a port-level request."""
        payload: dict[str, Any] = {
            'model': self._model,
            'messages': self._build_messages(request),
            'temperature': request.temperature,
            'max_tokens': request.max_output_tokens,
            'timeout': self._timeout_seconds,
        }

        response_format = self._build_response_format(request)
        if response_format is not None:
            payload['response_format'] = response_format

        return payload

    def _build_messages(self, request: LLMRequest) -> list[dict[str, str]]:
        """Construct OpenAI chat messages from the LLM request."""
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({'role': 'system', 'content': request.system_prompt})
        messages.append({'role': 'user', 'content': request.prompt})
        return messages

    def _build_response_format(self, request: LLMRequest) -> dict[str, Any] | None:
        """Translate the response format abstraction to OpenAI arguments."""
        if request.response_format.type is ResponseFormatType.TEXT:
            return None

        if request.response_format.schema is None:
            return {'type': 'json_object'}

        return {
            'type': 'json_schema',
            'json_schema': {
                'name': 'structured_response',
                'schema': request.response_format.schema,
            },
        }

    def _build_success_response(self, completion: Any, request: LLMRequest) -> LLMResponse:
        """Build a successful LLMResponse envelope from OpenAI output."""
        try:
            content = completion.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            return LLMResponse(
                success=False,
                content='OpenAI returned an invalid response payload',
                error=LLMError.INVALID_RESPONSE,
            )

        if content is None:
            return LLMResponse(
                success=False,
                content='OpenAI returned an empty response',
                error=LLMError.INVALID_RESPONSE,
            )

        if request.response_format.type is ResponseFormatType.JSON:
            try:
                return LLMResponse(success=True, content=content, structured=json.loads(content))
            except json.JSONDecodeError:
                return LLMResponse(
                    success=False,
                    content='OpenAI returned non-JSON content for a JSON request',
                    error=LLMError.INVALID_RESPONSE,
                )

        return LLMResponse(success=True, content=content)
