"""OpenAI adapter implementing the LLM client port."""

import contextlib
import hashlib
import json
import logging
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from openai import AsyncOpenAI, BadRequestError
from openai.types.responses import Response as OpenAIResponse
from openai.types.responses import ResponseOutputRefusal
from wukong_engine.app.config.llm import LLMRegistry
from wukong_engine.app.llm.elements import LLMBatchCreationResponse, LLMBatchResult, LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.llm.elements.values import LLMPrompt
from wukong_engine.app.llm.exceptions import (
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
    LLMTruncatedResponseError,
)
from wukong_engine.app.llm.model.values import LLMProvider

from .config import OpenAIConfig
from .decorators import translate_openai_errors
from .schema import fits_limits

# Logging
logger = logging.getLogger(__name__)

# Constants
UNENFORCED_SCHEMA_INSTRUCTIONS = 'Respond only with a JSON object that follows this JSON schema:\n{schema}'
SCHEMA_CHECK_INPUT = 'Respond with the JSON object.'  # Input of the token counting requests checking batch schemas


def _schema_key(schema: dict[str, Any]) -> str:
    """Identify a JSON schema by its content.

    Args:
        schema: JSON schema to identify.

    Returns:
        A digest that is equal for schemas with the same content.
    """
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()


class OpenAIClient(LLMClient):
    """Client that executes LLM requests against the OpenAI API."""

    def __init__(self, config: OpenAIConfig) -> None:
        """Initialize the OpenAI client with the given configuration.

        Args:
            config: Client configuration with credentials, model, output limit, timeout and retry settings.
        """
        self._config = config
        self._client = AsyncOpenAI(api_key=config.api_key, timeout=config.timeout, max_retries=config.max_retries)
        self._provider = LLMProvider.OPENAI
        self._unenforced_schemas: set[str] = set()  # Keys of the schemas sent as instructions instead of enforced
        self._checked_schemas: set[str] = set()  # Keys of the schemas the API accepted for batches

    @staticmethod
    def _build_input(prompt: LLMPrompt, *, explicit_caching: bool) -> list[dict[str, Any]]:
        """Build the input message, marking the end of the shared content as a cache breakpoint if supported.

        Args:
            prompt: Prompt whose shared content (if any) and request-specific content form the user message.
            explicit_caching: Whether to mark the shared content block as an explicit prompt cache breakpoint.

        Returns:
            A single-element list with the user message, whose content holds the shared block (if any) followed by
            the request-specific block.
        """
        content: list[dict[str, Any]] = []
        if prompt.shared_content:
            shared_block: dict[str, Any] = {'type': 'input_text', 'text': prompt.shared_content}
            if explicit_caching:
                shared_block['prompt_cache_breakpoint'] = {'mode': 'explicit'}
            content.append(shared_block)
        content.append({'type': 'input_text', 'text': prompt.content})
        return [{'role': 'user', 'content': content}]

    def _build_request_payload(self, request: LLMRequest, *, enforce_schema: bool = True) -> dict[str, Any]:
        """Build the Responses API payload for a request.

        Adds explicit prompt caching options, reasoning effort and temperature only when the configured model
        supports them. A prompt schema is enforced as a strict JSON schema response format, unless it exceeds the
        structured output limits or was already rejected by the API, in which case it leads the input as instructions
        and only valid JSON is enforced.

        Args:
            request: LLM request to translate into an API payload.
            enforce_schema: Whether to try enforcing the prompt schema. If False, it is sent as instructions.

        Returns:
            The keyword arguments for a Responses API call, including a ``prompt_cache_options`` entry when explicit
            caching is supported.
        """
        # Base parameters for the API call
        model = self._config.model
        explicit_caching = LLMRegistry.supports_explicit_caching(model)
        payload = {
            'model': model.name,
            'instructions': request.prompt.instructions,
            'input': self._build_input(request.prompt, explicit_caching=explicit_caching),
            'max_output_tokens': self._config.max_output_tokens,
        }

        # Cache only at the explicit breakpoint: implicit mode would instead write the whole prompt, including the
        # request-specific tail that no other request can reuse, and cache writes cost 1.25x the input rate
        if explicit_caching:
            payload['prompt_cache_options'] = {'mode': 'explicit'}

        # Set reasoning effort if supported by the model
        reasoning_effort = (
            LLMRegistry.reasoning_effort(model, request.reasoning_effort)
            if request.reasoning_effort is not None
            else LLMRegistry.default_reasoning_effort(model)
        )
        if LLMRegistry.is_reasoning_model(model) and reasoning_effort is not None:
            payload['reasoning'] = {'effort': reasoning_effort}

        # Set temperature if supported by the model
        temperature = request.temperature if request.temperature is not None else 0.0
        if LLMRegistry.is_supported_model(model) and not LLMRegistry.is_reasoning_model(model):
            payload['temperature'] = temperature

        # Include structured response schema if provided, enforced when possible or as instructions if not
        schema = request.prompt.schema
        if schema is not None:
            enforceable = enforce_schema and _schema_key(schema) not in self._unenforced_schemas
            if enforceable and not fits_limits(schema):
                self._mark_unenforced(schema, 'it exceeds the structured output limits of the OpenAI API')
                enforceable = False
            if enforceable:
                payload['text'] = {
                    'format': {
                        'type': 'json_schema',
                        'name': 'schema',
                        'strict': True,
                        'schema': schema,
                    },
                }
            else:
                # JSON mode requires the input messages, not the instructions, to mention JSON. Leading the input, the
                # schema also stays inside the prefix cached for the requests that share it.
                schema_block = {
                    'type': 'input_text',
                    'text': UNENFORCED_SCHEMA_INSTRUCTIONS.format(schema=json.dumps(schema)),
                }
                payload['input'][0]['content'].insert(0, schema_block)
                payload['text'] = {'format': {'type': 'json_object'}}

        return payload

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
                f'A response schema is sent as instructions without being enforced, since {reason}. Responses are '
                'still valid JSON, and items that do not match their type are discarded.',
            )

    @staticmethod
    def _ensure_successful_response(response: OpenAIResponse) -> None:
        """Ensure the LLM response indicates a successful generation.

        Args:
            response: Response returned by the OpenAI API.

        Raises:
            LLMTruncatedResponseError: If the response was cut off by the output token limit.
            LLMResponseError: If the response is not completed for another reason, or contains a refusal.
        """
        metrics = response.usage.model_dump() if response.usage else None

        # Truncated response, which the same request would truncate again
        incomplete_reason = response.incomplete_details.reason if response.incomplete_details else None
        if response.status == 'incomplete' and incomplete_reason == 'max_output_tokens':
            raise LLMTruncatedResponseError('The LLM response was cut off by the output token limit', metrics=metrics)

        # Incomplete response for any other reason
        if response.status != 'completed':
            raise LLMResponseError(
                f'The LLM response status was "{response.status}", indicating a generation failure',
                metrics=metrics,
            )

        # Refusal (if the model refused to generate a response, e.g. due to content moderation)
        refusal_item: ResponseOutputRefusal | None = next(
            (item for item in response.output if isinstance(item, ResponseOutputRefusal)),
            None,
        )
        if refusal_item is not None:
            raise LLMResponseError('The LLM refused to generate a response', metrics=metrics)

    @staticmethod
    def _build_llm_response(response: OpenAIResponse) -> LLMResponse:
        """Build an LLMResponse from the API response.

        Args:
            response: Successful response returned by the OpenAI API.

        Returns:
            The response's output text, model name and usage metrics (empty if usage is unavailable).
        """
        return LLMResponse(
            content=response.output_text,
            model=response.model,
            metrics=response.usage.model_dump() if response.usage else {},
        )

    def _parse_batch_result(self, line: str) -> LLMBatchResult | None:
        """Parse a single line of the batch result file.

        Args:
            line: JSONL line of the batch output file.

        Returns:
            A successful result, an error result (with the response error and its usage if the response was
            unsuccessful, or an internal error if it could not be parsed), or None if the line carries no job
            identifier.
        """
        try:
            # Parse the JSON line and extract the item and job ID
            custom_id: str | None = None
            item = json.loads(line)
            custom_id = item.get('custom_id')

            # If no job ID is present, cannot associate result with a job
            if custom_id is None:
                return None

            # Parse the successful response
            provider_response = OpenAIResponse.model_validate(item['response']['body'])
            self._ensure_successful_response(provider_response)
            return LLMBatchResult(job_id=custom_id, response=self._build_llm_response(provider_response))

        except LLMResponseError as exc:
            # If the response indicates a refusal or is incomplete, return an error result instead
            if custom_id is not None:
                return LLMBatchResult(job_id=custom_id, response=None, error=exc)
            return None
        except ValidationError, json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError:
            # If parsing fails, return an error result (if job ID is available)
            if custom_id is not None:
                return LLMBatchResult(
                    job_id=custom_id,
                    response=None,
                    error=LLMInternalError(f'Failed to parse returned batch result: {line}'),
                )
            return None

    def _parse_batch_error(self, line: str) -> LLMBatchResult | None:
        """Parse a single line of the batch error file.

        Args:
            line: JSONL line of the batch error file.

        Returns:
            An error result with a transient error holding the provider's error message (or an internal error if the
            line could not be parsed), or None if the line carries no job identifier.
        """
        try:
            # Parse the JSON line and extract the item and job ID
            custom_id: str | None = None
            item: dict[str, Any] = json.loads(line)
            custom_id = item.get('custom_id')

            # If no job ID is present, cannot associate result with a job
            if custom_id is None:
                return None

            # Look for an API/HTTP endpoint error message
            error_msg = item.get('response', {}).get('body', {}).get('error', {}).get('message')

            # If no API error, look for a top-level Batch/System error or fallback to a generic message
            if error_msg is None:
                error_msg = item.get('error', {}).get('message', 'Unknown API error.')

            # Return the error result
            error = LLMTransientError(f'Batch request failed: {error_msg}')
            return LLMBatchResult(job_id=custom_id, response=None, error=error)

        except json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError:
            # If parsing fails, return a generic error result (if job ID is available)
            if custom_id is not None:
                return LLMBatchResult(
                    job_id=custom_id,
                    response=None,
                    error=LLMInternalError(f'Failed to parse returned batch error result: {line}'),
                )
            return None

    @translate_openai_errors
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request.

        Args:
            request: LLM request with the prompt and optional generation parameters.

        Returns:
            The generated response with its content, model and usage metrics.

        Raises:
            LLMResponseError: If the response is not completed or the model refused to respond.
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
            LLMInternalError: If any other unexpected provider error occurs.
        """
        # Send the request, resending it with its schema as instructions if the API rejects the schema
        try:
            response = await self._send(self._build_request_payload(request))
        except BadRequestError as exc:
            if request.prompt.schema is None or exc.code != 'invalid_json_schema':
                raise
            self._mark_unenforced(request.prompt.schema, f'the OpenAI API rejected it ({exc.message})')
            response = await self._send(self._build_request_payload(request, enforce_schema=False))
        self._ensure_successful_response(response)

        # Return the response in the expected format
        return self._build_llm_response(response)

    async def _send(self, payload: dict[str, Any]) -> OpenAIResponse:
        """Send a Responses API request.

        Args:
            payload: Keyword arguments of the call, as built by ``_build_request_payload``.

        Returns:
            The response returned by the API.
        """
        # The SDK has no typed parameter for the prompt caching options yet
        extra_body = (
            {'prompt_cache_options': payload.pop('prompt_cache_options')} if 'prompt_cache_options' in payload else None
        )
        return await self._client.responses.create(**payload, extra_body=extra_body)

    @translate_openai_errors
    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Create a batch for asynchronous request processing.

        The requests are uploaded as a JSONL file and submitted as a 24-hour Responses API batch; the uploaded file
        is deleted if batch creation fails. The schemas of the requests are checked first (see
        ``_check_batch_schema``), so that a schema the API rejects is sent as instructions instead of failing every
        request that uses it.

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
        # Check the schemas of the requests, then build the JSONL payload for the batch
        requests = tuple(requests)
        for request in requests:
            await self._check_batch_schema(request)
        lines = []
        for request, job_id in zip(requests, job_ids, strict=True):
            payload = self._build_request_payload(request)
            json_request = json.dumps(
                {'custom_id': job_id, 'method': 'POST', 'url': '/v1/responses', 'body': payload},
            )
            lines.append(json_request)
        jsonl = '\n'.join(lines)

        # Submit payload and return the batch creation response
        file_id: str | None = None
        try:
            # Upload the JSONL file to the API
            file = await self._client.files.create(file=('batch.jsonl', jsonl.encode()), purpose='batch')
            file_id = file.id

            # Send the batch creation request to the API
            batch = await self._client.batches.create(
                input_file_id=file.id,
                endpoint='/v1/responses',
                completion_window='24h',
            )

            # Return the batch creation response
            return LLMBatchCreationResponse(batch_id=batch.id, provider=self._provider)

        except Exception:
            # Clean up the uploaded file on failure
            if file_id is not None:
                with contextlib.suppress(Exception):
                    await self._client.files.delete(file_id)
            raise

    async def _check_batch_schema(self, request: LLMRequest) -> None:
        """Check, once per schema, whether the API accepts the enforced schema of a batch request.

        In a batch, a rejected schema would only surface as an error of each request using it. Instead, the schema is
        first validated through the free input token counting endpoint, which rejects invalid schemas like generation
        does, and a rejected schema is sent as instructions from now on.

        Args:
            request: LLM request whose schema to check.

        Raises:
            BadRequestError: If the check is invalid for a reason other than its schema.
        """
        schema = request.prompt.schema
        text_format = self._build_request_payload(request).get('text', {})
        if schema is None or text_format.get('format', {}).get('type') != 'json_schema':
            return
        if _schema_key(schema) in self._checked_schemas:
            return
        check = {'model': self._config.model.name, 'input': SCHEMA_CHECK_INPUT, 'text': text_format}
        try:
            # The SDK has no typed method for the input token counting endpoint yet
            await self._client.post('/responses/input_tokens', cast_to=object, body=check)
        except BadRequestError as exc:
            if exc.code != 'invalid_json_schema':
                raise
            self._mark_unenforced(schema, f'the OpenAI API rejected it ({exc.message})')
        else:
            self._checked_schemas.add(_schema_key(schema))

    @translate_openai_errors
    async def get_batch_status(self, batch_id: str) -> str:
        """Get the current status of a batch.

        Args:
            batch_id: Provider identifier of the batch.

        Returns:
            The provider's batch status string (e.g. ``completed``).

        Raises:
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
            LLMInternalError: If any other unexpected provider error occurs.
        """
        provider_batch = await self._client.batches.retrieve(batch_id)
        return provider_batch.status

    @translate_openai_errors
    async def get_batch_results(self, batch_id: str) -> tuple[LLMBatchResult, ...]:
        """Get the results of an ended batch, which for an expired or cancelled one are those of its finished requests.

        The output file holds the successful results and is absent when every request failed; the error file holds
        the failed ones. Failures to read the error file are ignored when there is an output file, so that its results
        are still returned.

        Args:
            batch_id: Provider identifier of the batch.

        Returns:
            The parsed results from the output file followed by the parsed error results from the error file.

        Raises:
            LLMResponseError: If the batch has not ended, or failed without running.
            LLMInternalError: If the ended batch has neither an output nor an error file, or any other unexpected
                provider error occurs.
            LLMConfigurationError: If authentication fails or the provider rejects the request as invalid.
            LLMTransientError: If the provider is rate limited, times out, is unreachable or fails server-side.
        """
        # Retrieve the batch from the provider
        provider_batch = await self._client.batches.retrieve(batch_id)

        # Ensure the batch has ended with results to retrieve (expired and cancelled batches keep those of the requests
        # they finished, while failed ones never ran)
        if provider_batch.status not in {'completed', 'expired', 'cancelled'}:
            raise LLMResponseError(
                f'Cannot retrieve results for batch {batch_id} with current status "{provider_batch.status}"',
            )

        # Ensure the batch has results to retrieve
        output_file_id, error_file_id = provider_batch.output_file_id, provider_batch.error_file_id
        if output_file_id is None and error_file_id is None:
            raise LLMInternalError(f'Completed batch {batch_id} has neither an output nor an error file')

        # Retrieve the output file (absent when every request failed) and parse successful results
        results: list[LLMBatchResult] = []
        if output_file_id is not None:
            output_file = await self._client.files.content(output_file_id)
            for line in output_file.text.splitlines():
                parsed_result = self._parse_batch_result(line)
                if parsed_result is not None:
                    results.append(parsed_result)

        # Retrieve the error file and parse failed results (if any), which are all the results without an output file
        errors: list[LLMBatchResult] = []
        if error_file_id is not None and output_file_id is None:
            errors = await self._read_batch_errors(error_file_id)
        elif error_file_id is not None:
            with contextlib.suppress(Exception):
                errors = await self._read_batch_errors(error_file_id)

        # Return all results (successful and failed)
        return tuple(results + errors)

    async def _read_batch_errors(self, error_file_id: str) -> list[LLMBatchResult]:
        """Read and parse the error file of a batch.

        Args:
            error_file_id: Provider identifier of the batch's error file.

        Returns:
            The error results parsed from the file, skipping lines that can't be matched to a job.
        """
        error_file = await self._client.files.content(error_file_id)
        parsed_errors = (self._parse_batch_error(line) for line in error_file.text.splitlines())
        return [error for error in parsed_errors if error is not None]
