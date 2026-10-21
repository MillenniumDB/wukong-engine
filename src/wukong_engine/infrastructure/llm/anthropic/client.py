"""Anthropic adapter implementing the LLM client port."""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from anthropic import AsyncAnthropic, BadRequestError
from anthropic.types import Message, OutputConfigParam, TextBlockParam, Usage
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages import MessageBatchIndividualResponse
from anthropic.types.messages.batch_create_params import Request
from wukong_engine.app.config.llm import LLMRegistry
from wukong_engine.app.llm.elements import LLMBatchCreationResponse, LLMBatchResult, LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.llm.elements.values import LLMPrompt
from wukong_engine.app.llm.exceptions import LLMResponseError, LLMTransientError, LLMTruncatedResponseError
from wukong_engine.app.llm.model.values import LLMProvider

from .config import AnthropicConfig
from .decorators import translate_anthropic_errors
from .schema import adapt_schema

# Logging
logger = logging.getLogger(__name__)

# Constants
UNENFORCED_SCHEMA_INSTRUCTIONS = (
    'Respond only with a JSON object that follows this JSON schema, without code fences or any other text:\n{schema}'
)
CACHE_ENTRY_LIFETIME = 270  # Seconds a prompt cache entry is assumed to live unused (the API's 5 minutes, with margin)


def _schema_key(schema: dict[str, Any]) -> str:
    """Identify a JSON schema by its content.

    Args:
        schema: JSON schema to identify.

    Returns:
        A digest that is equal for schemas with the same content.
    """
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()


@dataclass
class _CacheWarmup:
    """State of the prompt cache entry of a prefix, as far as the client knows.

    Attributes:
        written: Set once the request writing the entry has been answered.
        last_used: Monotonic time the entry was last written or read, in seconds.
    """

    written: asyncio.Event = field(default_factory=asyncio.Event)
    last_used: float = 0.0

    def is_expired(self) -> bool:
        """Check whether the entry was written but may have expired since it was last used."""
        return self.written.is_set() and time.monotonic() - self.last_used > CACHE_ENTRY_LIFETIME

    def is_warm(self) -> bool:
        """Check whether the entry was written and can still be read."""
        return self.written.is_set() and not self.is_expired()


class AnthropicClient(LLMClient):
    """Client that executes LLM requests against the Anthropic API."""

    # Anthropic batch processing statuses translated into the status names the batch synchronizer maps (must stay in
    # sync with it). An ended batch is completed even if some of its requests failed, which surface per result.
    _BATCH_STATUSES: ClassVar[dict[str, str]] = {
        'in_progress': 'in_progress',
        'canceling': 'cancelling',
        'ended': 'completed',
    }

    # Native effort names, as given by the LLM registry, typed as the effort levels the API accepts ("none" is handled
    # separately, as disabled thinking)
    _EFFORTS: ClassVar[dict[str, Literal['low', 'medium', 'high', 'xhigh', 'max']]] = {
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'xhigh': 'xhigh',
        'max': 'max',
    }

    def __init__(self, config: AnthropicConfig) -> None:
        """Initialize the Anthropic client with the given configuration.

        Args:
            config: Client configuration with credentials, model, output limit, timeout and retry settings.
        """
        self._config = config
        self._client = AsyncAnthropic(api_key=config.api_key, timeout=config.timeout, max_retries=config.max_retries)
        self._provider = LLMProvider.ANTHROPIC
        self._unenforced_schemas: set[str] = set()  # Keys of the schemas sent as instructions instead of enforced
        self._cache_warmups: dict[str, _CacheWarmup] = {}  # Keyed by cached prefix

    @staticmethod
    def _build_content(prompt: LLMPrompt, *, explicit_caching: bool) -> list[TextBlockParam]:
        """Build the user message content, marking the end of the shared content as a cache breakpoint if supported.

        Args:
            prompt: Prompt whose shared content (if any) and request-specific content form the user message.
            explicit_caching: Whether to mark the shared content block as a prompt cache breakpoint.

        Returns:
            The shared block (if any) followed by the request-specific block.
        """
        content: list[TextBlockParam] = []
        if prompt.shared_content:
            shared_block: TextBlockParam = {'type': 'text', 'text': prompt.shared_content}
            if explicit_caching:
                shared_block['cache_control'] = {'type': 'ephemeral'}
            content.append(shared_block)
        content.append({'type': 'text', 'text': prompt.content})
        return content

    def _build_request_params(
        self,
        request: LLMRequest,
        *,
        enforce_schema: bool = True,
    ) -> MessageCreateParamsNonStreaming:
        """Build the Messages API parameters for a request.

        Adds a prompt cache breakpoint and reasoning effort only when the configured model supports them. A prompt
        schema is adapted to the structured output limits and enforced as the output format, unless it can't fit them
        or was already rejected by the API, in which case it is appended to the instructions without being enforced.
        The request's temperature is never sent, since the supported models only accept the default one.

        Args:
            request: LLM request to translate into API parameters.
            enforce_schema: Whether to try enforcing the prompt schema. If False, it is sent as instructions.

        Returns:
            The parameters of a non-streaming Messages API call.
        """
        # Base parameters for the API call
        model = self._config.model
        explicit_caching = LLMRegistry.supports_explicit_caching(model)
        params: MessageCreateParamsNonStreaming = {
            'model': model.name,
            'max_tokens': self._config.max_output_tokens,
            'messages': [
                {'role': 'user', 'content': self._build_content(request.prompt, explicit_caching=explicit_caching)},
            ],
        }
        # Set reasoning effort if supported by the model
        output_config: OutputConfigParam = {}
        reasoning_effort = (
            LLMRegistry.reasoning_effort(model, request.reasoning_effort)
            if request.reasoning_effort is not None
            else LLMRegistry.default_reasoning_effort(model)
        )
        if LLMRegistry.is_reasoning_model(model) and reasoning_effort == 'none':
            # The API has no "none" effort, and only accepts disabled thinking at an effort of high or below
            params['thinking'] = {'type': 'disabled'}
            output_config['effort'] = 'low'
        elif LLMRegistry.is_reasoning_model(model) and reasoning_effort is not None:
            output_config['effort'] = self._EFFORTS[reasoning_effort]

        # Include structured response schema if provided, enforced when possible or as instructions if not
        instructions = request.prompt.instructions
        schema = request.prompt.schema
        if schema is not None:
            enforceable = enforce_schema and _schema_key(schema) not in self._unenforced_schemas
            adapted_schema = adapt_schema(schema) if enforceable else None
            if enforceable and adapted_schema is None:
                self._mark_unenforced(schema, 'it exceeds the structured output limits of the Anthropic API')
            if adapted_schema is not None:
                output_config['format'] = {'type': 'json_schema', 'schema': adapted_schema}
            else:
                schema_instructions = UNENFORCED_SCHEMA_INSTRUCTIONS.format(schema=json.dumps(schema))
                instructions = f'{instructions}\n\n{schema_instructions}' if instructions else schema_instructions

        if instructions:
            params['system'] = instructions
        if output_config:
            params['output_config'] = output_config
        return params

    def _mark_unenforced(self, schema: dict[str, Any], reason: str) -> None:
        """Send a schema as instructions from now on, warning the first time.

        Args:
            schema: Schema that won't be enforced.
            reason: Why the schema can't be enforced, completing "since ...".
        """
        key = _schema_key(schema)
        if key not in self._unenforced_schemas:
            self._unenforced_schemas.add(key)
            logger.warning(
                f'A response schema is sent as instructions without being enforced, since {reason}. Responses that '
                'are not valid JSON are retried, and items that do not match their type are discarded.',
            )

    @classmethod
    def _ensure_successful_response(cls, message: Message) -> None:
        """Ensure the LLM response indicates a successful generation.

        Args:
            message: Message returned by the Anthropic API.

        Raises:
            LLMTruncatedResponseError: If the response was cut off by the output token limit or the context window.
            LLMResponseError: If the model refused to respond or stopped before finishing its turn for another reason.
        """
        metrics = cls._build_metrics(message.usage)

        # Refusal (if the model refused to generate a response, e.g. due to its safety classifiers)
        if message.stop_reason == 'refusal':
            raise LLMResponseError('The LLM refused to generate a response', metrics=metrics)

        # Truncated response, which the same request would truncate again
        if message.stop_reason in {'max_tokens', 'model_context_window_exceeded'}:
            raise LLMTruncatedResponseError(
                f'The LLM response was cut off before its end (stop reason "{message.stop_reason}")',
                metrics=metrics,
            )

        # Incomplete response for any other reason
        if message.stop_reason != 'end_turn':
            raise LLMResponseError(
                f'The LLM response stop reason was "{message.stop_reason}", indicating a generation failure',
                metrics=metrics,
            )

    @staticmethod
    def _build_metrics(usage: Usage) -> dict[str, Any]:
        """Build the usage metrics in the shape of the OpenAI usage payload, which is the one the app layer parses.

        Unlike OpenAI, Anthropic excludes cache reads and writes from its input token count, so they are added back.

        Args:
            usage: Usage reported by the Anthropic API.

        Returns:
            The usage metrics, with ``input_tokens``, ``output_tokens`` and their ``input_tokens_details`` and
            ``output_tokens_details`` breakdowns.
        """
        cache_read_tokens = usage.cache_read_input_tokens or 0
        cache_write_tokens = usage.cache_creation_input_tokens or 0
        metrics: dict[str, Any] = {
            'input_tokens': usage.input_tokens + cache_read_tokens + cache_write_tokens,
            'input_tokens_details': {'cached_tokens': cache_read_tokens, 'cache_write_tokens': cache_write_tokens},
            'output_tokens': usage.output_tokens,
        }
        if usage.output_tokens_details is not None:
            metrics['output_tokens_details'] = {'reasoning_tokens': usage.output_tokens_details.thinking_tokens}
        return metrics

    @classmethod
    def _build_llm_response(cls, message: Message) -> LLMResponse:
        """Build an LLMResponse from the API response.

        Args:
            message: Successful message returned by the Anthropic API.

        Returns:
            The message's text, unwrapped from a code fence if it has one, model name and usage metrics.
        """
        return LLMResponse(
            content=cls._strip_code_fence(''.join(block.text for block in message.content if block.type == 'text')),
            model=message.model,
            metrics=cls._build_metrics(message.usage),
        )

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """Unwrap a text from a surrounding Markdown code fence.

        Responses whose schema is not enforced may still wrap their JSON in a fence despite the instructions.

        Args:
            text: Response text.

        Returns:
            The fenced content without the fence lines, or the text unchanged if it is not fenced.
        """
        stripped = text.strip()
        if not stripped.startswith('```') or not stripped.endswith('```') or '\n' not in stripped:
            return text
        return stripped.split('\n', 1)[1].removesuffix('```').strip()

    @classmethod
    def _parse_batch_result(cls, item: MessageBatchIndividualResponse) -> LLMBatchResult:
        """Parse a single result of a batch.

        Args:
            item: Batch result for one request.

        Returns:
            A successful result, or an error result: with the response error (and its usage) if the response was
            unsuccessful, or with a transient error if the request failed, was canceled or expired.
        """
        result = item.result
        match result.type:
            case 'succeeded':
                try:
                    cls._ensure_successful_response(result.message)
                except LLMResponseError as exc:
                    return LLMBatchResult(job_id=item.custom_id, response=None, error=exc)
                return LLMBatchResult(job_id=item.custom_id, response=cls._build_llm_response(result.message))
            case 'errored':
                message = f'Batch request failed: {result.error.error.message}'
            case 'canceled':
                message = 'Batch request was canceled before processing'
            case 'expired':
                message = 'Batch request expired before processing'
        return LLMBatchResult(job_id=item.custom_id, response=None, error=LLMTransientError(message))

    @translate_anthropic_errors
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request.

        Args:
            request: LLM request with the prompt and optional generation parameters.

        Returns:
            The generated response with its content, model and usage metrics.

        Raises:
            LLMResponseError: If the model refused to respond or stopped before finishing its turn.
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
            LLMInternalError: If any other unexpected provider error occurs.
        """
        # A cache entry can only be read once the request writing it has been answered, so concurrent requests sharing
        # a prefix would all write it at 1.25x the input rate. Instead, the first one writes it while the rest wait,
        # and the parameters are rebuilt after waiting, since the first request may have found the schema unenforceable.
        while True:
            params = self._build_request_params(request)
            prefix_key = self._cache_prefix_key(request, params)
            warmup = self._cache_warmups.get(prefix_key) if prefix_key is not None else None
            if prefix_key is None or (warmup is not None and warmup.is_warm()):
                if warmup is not None:
                    warmup.last_used = time.monotonic()
                return await self._generate_with_schema_fallback(request, params)
            if warmup is None or warmup.is_expired():
                return await self._generate_writing_cache(request, params, prefix_key)
            await warmup.written.wait()

    async def _generate_writing_cache(
        self,
        request: LLMRequest,
        params: MessageCreateParamsNonStreaming,
        prefix_key: str,
    ) -> LLMResponse:
        """Send the request that writes the cache entry of a prefix, holding the other requests sharing it meanwhile.

        Args:
            request: LLM request the parameters were built from.
            params: Parameters of the request.
            prefix_key: Key of the request's cached prefix.

        Returns:
            The generated response.
        """
        warmup = self._cache_warmups[prefix_key] = _CacheWarmup()
        try:
            response = await self._generate_with_schema_fallback(request, params)
        except BaseException:
            # Lets one of the held requests write the entry instead
            self._cache_warmups.pop(prefix_key, None)
            warmup.written.set()
            raise
        warmup.last_used = time.monotonic()
        warmup.written.set()
        return response

    async def _generate_with_schema_fallback(
        self,
        request: LLMRequest,
        params: MessageCreateParamsNonStreaming,
    ) -> LLMResponse:
        """Send a request, resending it with its schema as instructions if the API rejects the enforced schema.

        The API reports schema rejections without a machine-readable error code, so the schema is confirmed as the
        cause by resending the request without enforcing it: any other invalid request fails again, and its original
        error is raised.

        Args:
            request: LLM request the parameters were built from.
            params: Parameters of the request.

        Returns:
            The generated response.

        Raises:
            BadRequestError: If the request is invalid for a reason other than its enforced schema.
        """
        try:
            return await self._generate_from_params(params)
        except BadRequestError as exc:
            schema = request.prompt.schema
            if schema is None or 'format' not in params.get('output_config', {}):
                raise
            try:
                response = await self._generate_from_params(self._build_request_params(request, enforce_schema=False))
            except BadRequestError:
                raise exc from None
            self._mark_unenforced(schema, f'the Anthropic API rejected it ({exc.message})')
            return response

    async def _generate_from_params(self, params: MessageCreateParamsNonStreaming) -> LLMResponse:
        """Send a Messages API request and build the response.

        Args:
            params: Parameters of the request.

        Returns:
            The generated response with its content, model and usage metrics.

        Raises:
            LLMResponseError: If the model refused to respond or stopped before finishing its turn.
        """
        message = await self._client.messages.create(**params)
        self._ensure_successful_response(message)
        return self._build_llm_response(message)

    def _cache_prefix_key(self, request: LLMRequest, params: MessageCreateParamsNonStreaming) -> str | None:
        """Identify the cached prefix of a request.

        Args:
            request: LLM request the parameters were built from.
            params: Parameters built for the request.

        Returns:
            A key that is equal for requests sharing the prefix up to their cache breakpoint, or None if the request
            has no cache breakpoint.
        """
        if not request.prompt.shared_content or not LLMRegistry.supports_explicit_caching(self._config.model):
            return None
        prefix = {key: params.get(key) for key in ('model', 'system', 'thinking', 'output_config')}
        prefix_json = json.dumps(prefix | {'shared_content': request.prompt.shared_content}, sort_keys=True)
        return hashlib.sha256(prefix_json.encode()).hexdigest()

    @translate_anthropic_errors
    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Create a batch for asynchronous request processing.

        Args:
            requests: LLM requests to include in the batch.
            job_ids: Job identifiers used as the custom ID of each request, in the same order as ``requests``.

        Returns:
            The provider's batch identifier together with the provider.

        Raises:
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
            LLMInternalError: If any other unexpected provider error occurs.
        """
        batch_requests: list[Request] = [
            {'custom_id': job_id, 'params': self._build_request_params(request)}
            for request, job_id in zip(requests, job_ids, strict=True)
        ]
        batch = await self._client.messages.batches.create(requests=batch_requests)
        return LLMBatchCreationResponse(batch_id=batch.id, provider=self._provider)

    @translate_anthropic_errors
    async def get_batch_status(self, batch_id: str) -> str:
        """Get the current status of a batch.

        Args:
            batch_id: Provider identifier of the batch.

        Returns:
            The batch status, translated into the status names shared with the other providers (e.g. ``completed``).

        Raises:
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
            LLMInternalError: If any other unexpected provider error occurs.
        """
        provider_batch = await self._client.messages.batches.retrieve(batch_id)
        return self._BATCH_STATUSES[provider_batch.processing_status]

    @translate_anthropic_errors
    async def get_batch_results(self, batch_id: str) -> tuple[LLMBatchResult, ...]:
        """Get the results of a completed batch.

        Args:
            batch_id: Provider identifier of the batch.

        Returns:
            One result per request of the batch, holding either its response or an error.

        Raises:
            LLMResponseError: If the batch has not ended.
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
            LLMInternalError: If any other unexpected provider error occurs.
        """
        # Ensure the batch has ended before attempting to retrieve results
        provider_batch = await self._client.messages.batches.retrieve(batch_id)
        if provider_batch.processing_status != 'ended':
            raise LLMResponseError(
                f'Cannot retrieve results for batch {batch_id} with current status "{provider_batch.processing_status}"',
            )

        # Retrieve and parse the results of every request
        results = await self._client.messages.batches.results(batch_id)
        return tuple([self._parse_batch_result(item) async for item in results])
