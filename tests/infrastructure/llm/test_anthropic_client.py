"""Tests for the Anthropic LLM client, run against a mocked Anthropic API."""

import asyncio
import json
from collections.abc import Callable
from functools import partial
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from wukong_engine.app.data_extraction.elements.values import BatchStatus, TokenUsageMetrics
from wukong_engine.app.data_extraction.services import ConcurrentExtractionBatchSynchronizer
from wukong_engine.app.llm.elements import LLMBatchResult, LLMRequest
from wukong_engine.app.llm.elements.values import LLMPrompt, ReasoningEffort
from wukong_engine.app.llm.exceptions import LLMConfigurationError, LLMError, LLMResponseError, LLMTransientError
from wukong_engine.app.llm.model import LLM
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.infrastructure.llm.anthropic import AnthropicClient, AnthropicConfig
from wukong_engine.infrastructure.llm.anthropic import client as client_module
from wukong_engine.infrastructure.llm.anthropic.schema import MAX_OPTIONAL_PARAMETERS

MODEL = LLM(name='claude-haiku-5-5', provider=LLMProvider.ANTHROPIC)
SCHEMA = {
    'type': 'object',
    'properties': {'entities': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['entities'],
    'additionalProperties': False,
}
REQUEST = LLMRequest(
    prompt=LLMPrompt(
        content='Request-specific sentence.',
        instructions='Extract the entities.',
        schema=SCHEMA,
        shared_content='Shared context. ',
    ),
    reasoning_effort=ReasoningEffort.LOW,
    temperature=0.0,
)
EXPECTED_PARAMS = {
    'model': 'claude-haiku-5-5',
    'max_tokens': 16000,
    'system': 'Extract the entities.',
    'messages': [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'Shared context. ', 'cache_control': {'type': 'ephemeral'}},
                {'type': 'text', 'text': 'Request-specific sentence.'},
            ],
        },
    ],
    'output_config': {'effort': 'low', 'format': {'type': 'json_schema', 'schema': SCHEMA}},
}
BATCH_URL = 'https://api.anthropic.com/v1/messages/batches/msgbatch_1'


def _message(stop_reason: str = 'end_turn', text: str = '{"entities": []}') -> dict[str, Any]:
    """Build a Messages API response body, with a leading thinking block and cache usage."""
    return {
        'id': 'msg_1',
        'type': 'message',
        'role': 'assistant',
        'model': 'claude-haiku-5-5',
        'content': [
            {'type': 'thinking', 'thinking': '', 'signature': 'signature'},
            {'type': 'text', 'text': text},
        ],
        'stop_reason': stop_reason,
        'stop_sequence': None,
        'usage': {
            'input_tokens': 100,
            'cache_read_input_tokens': 800,
            'cache_creation_input_tokens': 50,
            'output_tokens': 300,
            'output_tokens_details': {'thinking_tokens': 200},
        },
    }


def _batch(processing_status: str) -> dict[str, Any]:
    """Build a Message Batches API batch body."""
    return {
        'id': 'msgbatch_1',
        'type': 'message_batch',
        'processing_status': processing_status,
        'request_counts': {'processing': 0, 'succeeded': 0, 'errored': 0, 'canceled': 0, 'expired': 0},
        'created_at': '2026-10-19T00:00:00Z',
        'expires_at': '2026-10-20T00:00:00Z',
        'ended_at': None,
        'archived_at': None,
        'cancel_initiated_at': None,
        'results_url': f'{BATCH_URL}/results' if processing_status == 'ended' else None,
    }


class MockAnthropicAPI:
    """Mocked Anthropic API that records the requests it receives and serves canned responses by URL path."""

    def __init__(self, responses: dict[str, httpx2.Response]) -> None:
        """Initialize the mocked API.

        Args:
            responses: Response served for each URL path.
        """
        self.responses = responses
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        """Record the request and serve the response for its path."""
        self.requests.append(request)
        return self.responses[request.url.path]

    def request_body(self, index: int = 0) -> Any:
        """Return the decoded JSON body of a recorded request."""
        return json.loads(self.requests[index].content)


type MockAPIInstaller = Callable[[dict[str, httpx2.Response]], MockAnthropicAPI]


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> MockAPIInstaller:
    """Return a function that routes the clients created afterwards to a mocked API serving the given responses."""

    def install(responses: dict[str, httpx2.Response]) -> MockAnthropicAPI:
        api = MockAnthropicAPI(responses)
        http_client = DefaultAsyncHttpxClient(transport=httpx2.MockTransport(api.handle))
        monkeypatch.setattr(client_module, 'AsyncAnthropic', partial(AsyncAnthropic, http_client=http_client))
        return api

    return install


def _client() -> AnthropicClient:
    """Build a client for the supported model, without SDK retries."""
    return AnthropicClient(AnthropicConfig(api_key='test-key', model=MODEL, max_retries=0))


def test_generate_sends_cache_breakpoint_effort_and_schema_without_temperature(mock_api: MockAPIInstaller) -> None:
    """Send the shared content as a cache breakpoint, the mapped effort and the schema, and no temperature."""
    api = mock_api({'/v1/messages': httpx2.Response(200, json=_message())})

    asyncio.run(_client().generate(REQUEST))

    assert api.request_body() == EXPECTED_PARAMS


def test_generate_returns_text_and_usage_parsed_into_non_overlapping_categories(mock_api: MockAPIInstaller) -> None:
    """Return the text blocks and usage that the app layer parses into non-overlapping token categories."""
    mock_api({'/v1/messages': httpx2.Response(200, json=_message())})

    response = asyncio.run(_client().generate(REQUEST))

    assert response.content == '{"entities": []}'
    assert response.model == 'claude-haiku-5-5'
    assert TokenUsageMetrics.from_usage(response.metrics) == TokenUsageMetrics(
        input_tokens=100,
        cached_tokens=800,
        cache_write_tokens=50,
        output_tokens=100,
        reasoning_tokens=200,
    )


@pytest.mark.parametrize('stop_reason', ['refusal', 'max_tokens'])
def test_generate_rejects_unfinished_responses(mock_api: MockAPIInstaller, stop_reason: str) -> None:
    """Raise a response error when the model refuses or stops before finishing its turn."""
    mock_api({'/v1/messages': httpx2.Response(200, json=_message(stop_reason))})

    with pytest.raises(LLMResponseError):
        asyncio.run(_client().generate(REQUEST))


@pytest.mark.parametrize(
    ('status_code', 'error_type', 'expected_error'),
    [
        (401, 'authentication_error', LLMConfigurationError),
        (400, 'invalid_request_error', LLMConfigurationError),
        (429, 'rate_limit_error', LLMTransientError),
        (529, 'overloaded_error', LLMTransientError),
    ],
)
def test_generate_translates_api_errors(
    mock_api: MockAPIInstaller,
    status_code: int,
    error_type: str,
    expected_error: type[LLMError],
) -> None:
    """Translate API errors into the LLM port exceptions."""
    body = {'type': 'error', 'error': {'type': error_type, 'message': 'Error message'}}
    mock_api({'/v1/messages': httpx2.Response(status_code, json=body)})

    with pytest.raises(expected_error):
        asyncio.run(_client().generate(REQUEST))


def test_create_batch_sends_one_request_per_job(mock_api: MockAPIInstaller) -> None:
    """Send one batch request per job, identified by the job ID, with the same parameters as a realtime call."""
    api = mock_api({'/v1/messages/batches': httpx2.Response(200, json=_batch('in_progress'))})

    response = asyncio.run(_client().create_batch([REQUEST, REQUEST], ['job1', 'job2']))

    assert response.batch_id == 'msgbatch_1'
    assert response.provider == LLMProvider.ANTHROPIC
    assert api.request_body() == {
        'requests': [
            {'custom_id': 'job1', 'params': EXPECTED_PARAMS},
            {'custom_id': 'job2', 'params': EXPECTED_PARAMS},
        ],
    }


@pytest.mark.parametrize(
    ('processing_status', 'expected_status'),
    [
        ('in_progress', BatchStatus.IN_PROGRESS),
        ('canceling', BatchStatus.IN_PROGRESS),
        ('ended', BatchStatus.COMPLETED),
    ],
)
def test_batch_statuses_are_understood_by_the_batch_synchronizer(
    mock_api: MockAPIInstaller,
    processing_status: str,
    expected_status: BatchStatus,
) -> None:
    """Return batch statuses that the batch synchronizer maps to the expected local status."""
    mock_api({'/v1/messages/batches/msgbatch_1': httpx2.Response(200, json=_batch(processing_status))})

    status = asyncio.run(_client().get_batch_status('msgbatch_1'))

    assert ConcurrentExtractionBatchSynchronizer._map_batch_status(status) == expected_status


def test_get_batch_results_parses_every_result_type(mock_api: MockAPIInstaller) -> None:
    """Parse succeeded results into responses and every unsuccessful result into an error."""
    error = {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Invalid schema'}}
    lines = [
        {'custom_id': 'succeeded', 'result': {'type': 'succeeded', 'message': _message()}},
        {'custom_id': 'refused', 'result': {'type': 'succeeded', 'message': _message('refusal')}},
        {'custom_id': 'errored', 'result': {'type': 'errored', 'error': error}},
        {'custom_id': 'canceled', 'result': {'type': 'canceled'}},
        {'custom_id': 'expired', 'result': {'type': 'expired'}},
    ]
    mock_api(
        {
            '/v1/messages/batches/msgbatch_1': httpx2.Response(200, json=_batch('ended')),
            '/v1/messages/batches/msgbatch_1/results': httpx2.Response(
                200,
                text='\n'.join(json.dumps(line) for line in lines),
            ),
        },
    )

    results = {result.job_id: result for result in asyncio.run(_client().get_batch_results('msgbatch_1'))}

    succeeded = results.pop('succeeded')
    assert succeeded.error is None
    assert succeeded.response is not None
    assert succeeded.response.content == '{"entities": []}'
    assert results == {
        'refused': LLMBatchResult('refused', response=None, error='The LLM refused to generate a response'),
        'errored': LLMBatchResult('errored', response=None, error='Batch request failed: Invalid schema'),
        'canceled': LLMBatchResult('canceled', response=None, error='Batch request was canceled before processing'),
        'expired': LLMBatchResult('expired', response=None, error='Batch request expired before processing'),
    }


def test_get_batch_results_rejects_unfinished_batch(mock_api: MockAPIInstaller) -> None:
    """Raise a response error when retrieving the results of a batch that has not ended."""
    mock_api({'/v1/messages/batches/msgbatch_1': httpx2.Response(200, json=_batch('in_progress'))})

    with pytest.raises(LLMResponseError):
        asyncio.run(_client().get_batch_results('msgbatch_1'))


def test_generate_sends_schema_over_the_limits_as_instructions_and_warns_once(
    mock_api: MockAPIInstaller,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Send a schema that can't fit the structured output limits as instructions, warning only on the first request."""
    fields = {f'field_{i}': {'type': ['string', 'null']} for i in range(MAX_OPTIONAL_PARAMETERS + 1)}
    schema = {
        'type': 'object',
        'properties': {'entities': {'type': 'array', 'items': {'type': 'object', 'properties': fields}}},
    }
    request = LLMRequest(prompt=LLMPrompt(content='Sentence.', instructions='Extract the entities.', schema=schema))
    api = mock_api({'/v1/messages': httpx2.Response(200, json=_message())})
    client = _client()

    asyncio.run(client.generate(request))
    asyncio.run(client.generate(request))

    body = api.request_body()
    assert body['output_config'] == {'effort': 'low'}
    assert body['system'].startswith('Extract the entities.\n\nRespond only with a JSON object')
    assert body['system'].endswith(json.dumps(schema))
    assert len([record for record in caplog.records if record.levelname == 'WARNING']) == 1


def test_generate_unwraps_code_fenced_json(mock_api: MockAPIInstaller) -> None:
    """Unwrap a JSON response wrapped in a Markdown code fence."""
    mock_api({'/v1/messages': httpx2.Response(200, json=_message(text='```json\n{"entities": []}\n```'))})

    response = asyncio.run(_client().generate(REQUEST))

    assert response.content == '{"entities": []}'
