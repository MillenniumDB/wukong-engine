"""Anthropic adapter implementing the LLM client port."""

import json
import logging
from collections.abc import Iterable
from typing import Any, ClassVar, Literal

from anthropic import AsyncAnthropic
from anthropic.types import Message, OutputConfigParam, TextBlockParam, Usage
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages import MessageBatchIndividualResponse
from anthropic.types.messages.batch_create_params import Request
from wukong_engine.app.config.llm import LLMRegistry
from wukong_engine.app.llm.elements import LLMBatchCreationResponse, LLMBatchResult, LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.llm.elements.values import LLMPrompt
from wukong_engine.app.llm.exceptions import LLMResponseError
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


class AnthropicClient(LLMClient):
    """Client that executes LLM requests against the Anthropic API."""

    # Anthropic batch processing statuses translated into the status names the batch synchronizer maps (must stay in
    # sync with it). An ended batch is completed even if some of its requests failed, which surface per result.
    _BATCH_STATUSES: ClassVar[dict[str, str]] = {
        'in_progress': 'in_progress',
        'canceling': 'cancelling',
        'ended': 'completed',
    }

    # Native effort names, as given by the LLM registry, typed as the effort levels the API accepts
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
        self._warned_unenforced_schema = False

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

    def _build_request_params(self, request: LLMRequest) -> MessageCreateParamsNonStreaming:
        """Build the Messages API parameters for a request.

        Adds a prompt cache breakpoint and reasoning effort only when the configured model supports them. A prompt
        schema is adapted to the structured output limits and enforced as the output format, or, if it can't fit them,
        appended to the instructions without being enforced. The request's temperature is never sent, since the
        supported models only accept the default one.

        Args:
            request: LLM request to translate into API parameters.

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
        if LLMRegistry.is_reasoning_model(model) and reasoning_effort is not None:
            output_config['effort'] = self._EFFORTS[reasoning_effort]

        # Include structured response schema if provided, enforced when it fits the API limits or as instructions if not
        instructions = request.prompt.instructions
        schema = request.prompt.schema
        if schema is not None:
            adapted_schema = adapt_schema(schema)
            if adapted_schema is not None:
                output_config['format'] = {'type': 'json_schema', 'schema': adapted_schema}
            else:
                self._warn_unenforced_schema()
                schema_instructions = UNENFORCED_SCHEMA_INSTRUCTIONS.format(schema=json.dumps(schema))
                instructions = f'{instructions}\n\n{schema_instructions}' if instructions else schema_instructions

        if instructions:
            params['system'] = instructions
        if output_config:
            params['output_config'] = output_config
        return params

    def _warn_unenforced_schema(self) -> None:
        """Warn, once per client, that a response schema exceeds the API limits and won't be enforced."""
        if not self._warned_unenforced_schema:
            logger.warning(
                'The response schema exceeds the structured output limits of the Anthropic API, so it is sent as '
                'instructions and not enforced. Responses that do not follow it are discarded or retried.',
            )
            self._warned_unenforced_schema = True

    @staticmethod
    def _ensure_successful_response(message: Message) -> None:
        """Ensure the LLM response indicates a successful generation.

        Args:
            message: Message returned by the Anthropic API.

        Raises:
            LLMResponseError: If the model refused to respond or stopped before finishing its turn.
        """
        # Refusal (if the model refused to generate a response, e.g. due to its safety classifiers)
        if message.stop_reason == 'refusal':
            raise LLMResponseError('The LLM refused to generate a response')

        # Incomplete response (e.g. the output token limit was reached)
        if message.stop_reason != 'end_turn':
            raise LLMResponseError(
                f'The LLM response stop reason was "{message.stop_reason}", indicating a generation failure',
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
            A successful result, or an error result if the request failed, was canceled or expired, or its response
            was unsuccessful.
        """
        result = item.result
        match result.type:
            case 'succeeded':
                try:
                    cls._ensure_successful_response(result.message)
                except LLMResponseError as exc:
                    return LLMBatchResult(job_id=item.custom_id, response=None, error=str(exc))
                return LLMBatchResult(job_id=item.custom_id, response=cls._build_llm_response(result.message))
            case 'errored':
                error = f'Batch request failed: {result.error.error.message}'
            case 'canceled':
                error = 'Batch request was canceled before processing'
            case 'expired':
                error = 'Batch request expired before processing'
        return LLMBatchResult(job_id=item.custom_id, response=None, error=error)

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
        message = await self._client.messages.create(**self._build_request_params(request))
        self._ensure_successful_response(message)
        return self._build_llm_response(message)

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
