"""OpenAI adapter implementing the LLM client port."""

import contextlib
import json
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from openai import AsyncOpenAI
from openai.types.responses import Response as OpenAIResponse
from openai.types.responses import ResponseOutputRefusal
from wukong_engine.app.config.llm import LLMRegistry
from wukong_engine.app.data_extraction.elements import ExtractionBatch
from wukong_engine.app.data_extraction.elements.values import BatchStatus, TokenUsageMetrics
from wukong_engine.app.llm.elements import (
    LLMBatchCreationResponse,
    LLMBatchResult,
    LLMClient,
    LLMRequest,
    LLMResponse,
)
from wukong_engine.app.llm.exceptions import LLMInternalError, LLMResponseError
from wukong_engine.app.llm.model.values import LLMProvider

from .config import OpenAIConfig
from .decorators import translate_openai_errors

# TODO: Remove this later together with the test code from create_batch
TEST_BATCH_IDS = [
    'batch_6a3e546f64a08190b9d7988f3340d831',
    'batch_6a3fa6e01d6481908400fb92bd136f44',
    'batch_6a3fa6e01f7c81908c920d02f22d2281',
]


# TODO: Remove test code from create_batch
class OpenAIClient(LLMClient):
    """Client that executes LLM requests against the OpenAI API."""

    def __init__(self, config: OpenAIConfig) -> None:
        """Initialize the OpenAI client with the given configuration."""
        self._config = config
        self._client = AsyncOpenAI(api_key=config.api_key, timeout=config.timeout, max_retries=config.max_retries)
        self._provider = LLMProvider.OPENAI

    def _build_request_payload(self, request: LLMRequest) -> dict[str, Any]:
        # Base parameters for the API call
        model = self._config.model
        payload = {
            'model': model.name,
            'instructions': request.prompt.instructions,
            'input': request.prompt.content,
            'max_output_tokens': self._config.max_output_tokens,
        }

        # Set reasoning effort if supported by the model
        reasoning_effort = (
            request.reasoning_effort
            if request.reasoning_effort is not None
            else LLMRegistry.get_reasoning_effort(model)
        )
        if LLMRegistry.is_reasoning_model(model) and reasoning_effort is not None:
            payload['reasoning'] = {'effort': reasoning_effort.value}

        # Set temperature if supported by the model
        temperature = request.temperature if request.temperature is not None else 0.0
        if LLMRegistry.is_supported_model(model) and not LLMRegistry.is_reasoning_model(model):
            payload['temperature'] = temperature

        # Include structured response schema if provided
        schema = request.prompt.schema
        if schema is not None:
            payload['text'] = {
                'format': {
                    'type': 'json_schema',
                    'name': 'schema',
                    'strict': True,
                    'schema': schema,
                },
            }

        return payload

    @staticmethod
    def _ensure_successful_response(response: OpenAIResponse) -> None:
        """Ensure the LLM response indicates a successful generation."""
        # Incomplete response
        if response.status != 'completed':
            raise LLMResponseError(f'The LLM response status was {response.status}, indicating a generation failure')

        # Refusal (if the model refused to generate a response, e.g. due to content moderation)
        refusal_item: ResponseOutputRefusal | None = next(
            (item for item in response.output if isinstance(item, ResponseOutputRefusal)),
            None,
        )
        if refusal_item is not None:
            raise LLMResponseError('The LLM refused to generate a response')

    @staticmethod
    def _build_llm_response(response: OpenAIResponse) -> LLMResponse:
        """Build an LLMResponse from the API response."""
        return LLMResponse(
            content=response.output_text,
            model=response.model,
            metrics=TokenUsageMetrics.from_usage(response.usage.model_dump() if response.usage else {}),
        )

    @staticmethod
    def _map_batch_status(provider_status: str) -> BatchStatus:
        """Map the provider-specific batch status to a BatchStatus state."""
        status_mapping = {
            'validating': BatchStatus.SUBMITTED,
            'in_progress': BatchStatus.IN_PROGRESS,
            'finalizing': BatchStatus.IN_PROGRESS,
            'cancelling': BatchStatus.IN_PROGRESS,
            'completed': BatchStatus.COMPLETED,
            'failed': BatchStatus.FAILED,
            'expired': BatchStatus.FAILED,
            'cancelled': BatchStatus.CANCELLED,
        }
        try:
            return status_mapping[provider_status]
        except KeyError as exc:
            raise LLMInternalError(f'Unknown batch status returned by provider: {provider_status}') from exc

    def _parse_batch_result(self, line: str) -> LLMBatchResult | None:
        """Parse a single line of the batch result file."""
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
            return LLMBatchResult(job_id=custom_id, response=self._build_llm_response(provider_response))

        except ValidationError, json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError:
            # If parsing fails, return an error result (if job ID is available)
            if custom_id is not None:
                return LLMBatchResult(
                    job_id=custom_id,
                    response=None,
                    error=f'Failed to parse returned batch result: {line}',
                )
            return None

    def _parse_batch_error(self, line: str) -> LLMBatchResult | None:
        """Parse a single line of the batch error file."""
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
            error = f'Batch request failed: {error_msg}'
            return LLMBatchResult(job_id=custom_id, response=None, error=error)

        except json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError:
            # If parsing fails, return a generic error result (if job ID is available)
            if custom_id is not None:
                return LLMBatchResult(
                    job_id=custom_id,
                    response=None,
                    error=f'Failed to parse returned batch error result: {line}',
                )
            return None

    @translate_openai_errors
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request."""
        # Build the request payload for the API
        payload = self._build_request_payload(request)

        # Send API request and await response
        response: OpenAIResponse = await self._client.responses.create(**payload)
        self._ensure_successful_response(response)

        # Return the response in the expected format
        return self._build_llm_response(response)

    @translate_openai_errors
    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Create a batch for asynchronous request processing."""
        # TODO: Test code
        import uuid

        fake_id = f'fake_batch_id_{uuid.uuid7().hex}'
        if TEST_BATCH_IDS:
            fake_id = TEST_BATCH_IDS.pop()
        return LLMBatchCreationResponse(batch_id=fake_id, provider=self._provider)

        # Build the JSONL payload for the batch
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

    @translate_openai_errors
    async def get_batch_status(self, batch: ExtractionBatch) -> BatchStatus:
        """Get the current status of a batch."""
        provider_batch = await self._client.batches.retrieve(batch.provider_id)
        return self._map_batch_status(provider_batch.status)

    @translate_openai_errors
    async def get_batch_results(self, batch: ExtractionBatch) -> tuple[LLMBatchResult, ...]:
        """Get the results of a completed batch."""
        # Retrieve the batch from the provider
        provider_batch = await self._client.batches.retrieve(batch.provider_id)

        # Ensure the batch is completed before attempting to retrieve results
        if provider_batch.status != 'completed':
            raise LLMResponseError(
                f'Cannot retrieve results for batch {batch.id}. Current status: {provider_batch.status}',
            )

        # Ensure the batch has an output file before attempting to retrieve results
        if provider_batch.output_file_id is None:
            raise LLMInternalError(f'Completed batch {batch.id} has no output file!')

        # Retrieve the output file and parse successful results
        results: list[LLMBatchResult] = []
        output_file = await self._client.files.content(provider_batch.output_file_id)
        for line in output_file.text.splitlines():
            parsed_result = self._parse_batch_result(line)
            if parsed_result is not None:
                results.append(parsed_result)

        # Retrieve the error file and parse failed results (if any)
        errors: list[LLMBatchResult] = []
        with contextlib.suppress(Exception):
            if provider_batch.error_file_id is not None:
                error_file = await self._client.files.content(provider_batch.error_file_id)
                for line in error_file.text.splitlines():
                    parsed_error = self._parse_batch_error(line)
                    if parsed_error is not None:
                        errors.append(parsed_error)

        # Return all results (successful and failed)
        return tuple(results + errors)
