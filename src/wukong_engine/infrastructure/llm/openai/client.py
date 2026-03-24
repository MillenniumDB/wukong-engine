"""OpenAI adapter implementing the LLM client port."""

import json
import time
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, OpenAIError, RateLimitError

from wukong_engine.app.llm.client import LLMClient
from wukong_engine.app.llm.models import LLMRequest, LLMResponse
from wukong_engine.app.llm.values import LLMError, ResponseFormat, ResponseFormatType


@dataclass(frozen=True)
class OpenAIConfig:
    """Configuration parameters for the OpenAI client."""

    api_key: str
    model: str = 'gpt-4.1-mini'
    timeout: float = 120.0
    max_retries: int = 10


class OpenAIClient(LLMClient):
    """Adapter that executes LLM requests against the OpenAI Chat Completions API."""

    def __init__(self, config: OpenAIConfig) -> None:
        """Create an OpenAI-backed LLM adapter.

        Args:
            config: OpenAIConfig dataclass with API key and settings.
        """
        self._config = config
        self._client = OpenAI(api_key=config.api_key)

    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self._call_llm(request)
            return self._map_response(response, request)

        except Exception as e:
            return self._handle_error(e, request)

    def _call_llm(self, request: LLMRequest) -> Any:
        request_params = self._build_request_params(request)
        return self._client.responses.create(**request_params)

    def _map_response(self, response: Any, request: LLMRequest) -> LLMResponse:
        try:
            content = self._extract_content(response)

            return LLMResponse(
                success=True,
                content=content,
                model=response.model,
                usage=self._extract_usage(response),
                raw=response,
                error=None,
            )

        except Exception as e:
            return LLMResponse(
                success=False,
                content=None,
                model=request.model or self._config.model,
                usage=None,
                raw=response,
                error=str(e),
            )

    def _handle_error(self, error: Exception, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            success=False,
            content=None,
            model=self._config.model,
            usage=None,
            raw=None,
            error=str(error),
        )

    def _build_request_params(self, request: LLMRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            'model': self._config.model,
            'input': request.prompt,
        }

        if request.temperature is not None:
            params['temperature'] = request.temperature

        if request.max_output_tokens is not None:
            params['max_output_tokens'] = request.max_output_tokens

        if request.response_format:
            params['response_format'] = self._map_response_format(request.response_format)

        return params

    def _map_response_format(self, fmt: ResponseFormat) -> dict[str, Any]:
        if fmt.type == 'json':
            return {'type': 'json_object'}
        if fmt.type == 'text':
            return {'type': 'text'}
        raise ValueError(f'Unsupported response format: {fmt.type}')

    def _extract_content(self, response: Any) -> str:
        # OpenAI Responses API structure
        return response.output[0].content[0].text

    def _extract_usage(self, response: Any) -> dict[str, int] | None:
        if not hasattr(response, 'usage') or response.usage is None:
            return None

        return {
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens,
            'total_tokens': response.usage.total_tokens,
        }

    # def generate(self, request: LLMRequest) -> LLMResponse:
    #     """Generate an LLM response from the given request."""
    #     retry_policy = request.retry_policy
    #     max_attempts = retry_policy.max_attempts if retry_policy is not None else 1
    #     delay = retry_policy.initial_delay if retry_policy is not None else 0.0

    #     for attempt in range(1, max_attempts + 1):
    #         try:
    #             completion = self._client.chat.completions.create(**self._build_request_payload(request))
    #             return self._build_success_response(completion, request)
    #         except APITimeoutError:
    #             mapped_error = LLMError.TIMEOUT
    #             message = 'OpenAI request timed out'
    #         except RateLimitError:
    #             mapped_error = LLMError.RATE_LIMIT
    #             message = 'OpenAI rate limit exceeded'
    #         except APIConnectionError:
    #             mapped_error = LLMError.NETWORK
    #             message = 'Network error calling OpenAI'
    #         except APIError:
    #             mapped_error = LLMError.PROVIDER_ERROR
    #             message = 'OpenAI provider returned an API error'
    #         except OpenAIError:
    #             mapped_error = LLMError.PROVIDER_ERROR
    #             message = 'OpenAI client error'
    #         except (TypeError, ValueError):
    #             mapped_error = LLMError.PROVIDER_ERROR
    #             message = 'Unexpected error calling OpenAI'

    #         if attempt >= max_attempts:
    #             return LLMResponse(success=False, content=message, error=mapped_error)

    #         if retry_policy is not None:
    #             time.sleep(delay)
    #             delay = min(delay * retry_policy.delay_multiplier, retry_policy.max_delay)

    #     return LLMResponse(success=False, content='Unreachable retry state', error=LLMError.PROVIDER_ERROR)

    # def _build_request_payload(self, request: LLMRequest) -> dict[str, Any]:
    #     """Build OpenAI API arguments from a port-level request."""
    #     payload: dict[str, Any] = {
    #         'model': self._model,
    #         'messages': self._build_messages(request),
    #         'temperature': request.temperature,
    #         'max_tokens': request.max_output_tokens,
    #         'timeout': self._timeout_seconds,
    #     }

    #     response_format = self._build_response_format(request)
    #     if response_format is not None:
    #         payload['response_format'] = response_format

    #     return payload

    # def _build_messages(self, request: LLMRequest) -> list[dict[str, str]]:
    #     """Construct OpenAI chat messages from the LLM request."""
    #     messages: list[dict[str, str]] = []
    #     if request.system_prompt:
    #         messages.append({'role': 'system', 'content': request.system_prompt})
    #     messages.append({'role': 'user', 'content': request.prompt})
    #     return messages

    # def _build_response_format(self, request: LLMRequest) -> dict[str, Any] | None:
    #     """Translate the response format abstraction to OpenAI arguments."""
    #     if request.response_format.type is ResponseFormatType.TEXT:
    #         return None

    #     if request.response_format.schema is None:
    #         return {'type': 'json_object'}

    #     return {
    #         'type': 'json_schema',
    #         'json_schema': {
    #             'name': 'structured_response',
    #             'schema': request.response_format.schema,
    #         },
    #     }

    # def _build_success_response(self, completion: Any, request: LLMRequest) -> LLMResponse:
    #     """Build a successful LLMResponse envelope from OpenAI output."""
    #     try:
    #         content = completion.choices[0].message.content
    #     except (AttributeError, IndexError, TypeError):
    #         return LLMResponse(
    #             success=False,
    #             content='OpenAI returned an invalid response payload',
    #             error=LLMError.INVALID_RESPONSE,
    #         )

    #     if content is None:
    #         return LLMResponse(
    #             success=False,
    #             content='OpenAI returned an empty response',
    #             error=LLMError.INVALID_RESPONSE,
    #         )

    #     if request.response_format.type is ResponseFormatType.JSON:
    #         try:
    #             return LLMResponse(success=True, content=content, structured=json.loads(content))
    #         except json.JSONDecodeError:
    #             return LLMResponse(
    #                 success=False,
    #                 content='OpenAI returned non-JSON content for a JSON request',
    #                 error=LLMError.INVALID_RESPONSE,
    #             )

    #     return LLMResponse(success=True, content=content)
