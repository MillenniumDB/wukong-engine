"""Tests for the Anthropic LLM client, run against a mocked Anthropic API."""

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from functools import partial
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from wukong_engine.app.data_extraction.elements.values import BatchStatus, TokenUsageMetrics
from wukong_engine.app.data_extraction.services import ConcurrentExtractionBatchSynchronizer
from wukong_engine.app.llm.elements import LLMRequest
from wukong_engine.app.llm.elements.values import LLMPrompt, ReasoningEffort
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMResponseError,
    LLMTransientError,
    LLMTruncatedResponseError,
)
from wukong_engine.app.llm.model import LLM
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.infrastructure.llm.anthropic import AnthropicClient, AnthropicConfig
from wukong_engine.infrastructure.llm.anthropic import client as client_module
from wukong_engine.infrastructure.llm.anthropic import config as config_module
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
    'thinking': {'type': 'disabled'},
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

    def __init__(self, responses: dict[str, MockResponses]) -> None:
        """Initialize the mocked API.

        Args:
            responses: Response served for each URL path, or responses served in turn (one per request).
        """
        self.responses = responses
        self.requests: list[httpx2.Request] = []
        self.gate: asyncio.Event | None = None  # When set, responses are held until the event is set
        self.delay = 0.0  # Seconds each response takes, so that overlapping requests can be observed
        self.in_flight = 0
        self.max_in_flight = 0

    async def handle(self, request: httpx2.Request) -> httpx2.Response:
        """Record the request and serve the response for its path, once the gate (if any) opens."""
        self.requests.append(request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.gate is not None:
                await self.gate.wait()
            await asyncio.sleep(self.delay)
            response = self.responses[request.url.path]
            return response.pop(0) if isinstance(response, list) else response
        finally:
            self.in_flight -= 1

    def request_body(self, index: int = 0) -> Any:
        """Return the decoded JSON body of a recorded request."""
        return json.loads(self.requests[index].content)


type MockResponses = httpx2.Response | list[httpx2.Response]
type MockAPIInstaller = Callable[[dict[str, MockResponses]], MockAnthropicAPI]


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> MockAPIInstaller:
    """Return a function that routes the clients created afterwards to a mocked API serving the given responses."""

    def install(responses: dict[str, MockResponses]) -> MockAnthropicAPI:
        api = MockAnthropicAPI(responses)
        http_client = DefaultAsyncHttpxClient(transport=httpx2.MockTransport(api.handle))
        monkeypatch.setattr(client_module, 'AsyncAnthropic', partial(AsyncAnthropic, http_client=http_client))
        return api

    return install


def _client() -> AnthropicClient:
    """Build a client for the supported model, without SDK retries."""
    return AnthropicClient(AnthropicConfig(api_key='test-key', model=MODEL, max_retries=0))


def test_generate_sends_cache_breakpoint_low_effort_without_thinking_and_schema(mock_api: MockAPIInstaller) -> None:
    """Send the shared content as a cache breakpoint, low effort without thinking and the schema, and no temperature."""
    api = mock_api({'/v1/messages': httpx2.Response(200, json=_message())})

    asyncio.run(_client().generate(REQUEST))

    assert api.request_body() == EXPECTED_PARAMS


def test_generate_keeps_thinking_for_efforts_above_low(mock_api: MockAPIInstaller) -> None:
    """Send the native effort level, leaving thinking on, for effort levels above low."""
    api = mock_api({'/v1/messages': httpx2.Response(200, json=_message())})

    asyncio.run(_client().generate(replace(REQUEST, reasoning_effort=ReasoningEffort.MEDIUM)))

    body = api.request_body()
    assert 'thinking' not in body
    assert body['output_config']['effort'] == 'medium'


def test_generate_sends_requests_sharing_a_cached_prefix_once_the_first_one_is_answered(
    mock_api: MockAPIInstaller,
) -> None:
    """Hold requests sharing a cached prefix until the first one is answered, without holding other prefixes."""
    api = mock_api({'/v1/messages': httpx2.Response(200, json=_message())})
    other_prefix_request = replace(REQUEST, prompt=replace(REQUEST.prompt, shared_content='Other shared context. '))

    async def run() -> list[str]:
        client = _client()
        api.gate = asyncio.Event()
        requests = (REQUEST, REQUEST, REQUEST, other_prefix_request)
        tasks = [asyncio.ensure_future(client.generate(request)) for request in requests]
        await asyncio.sleep(0.1)  # Lets every request that isn't held reach the API
        sent_while_unanswered = [
            api.request_body(i)['messages'][0]['content'][0]['text'] for i in range(len(api.requests))
        ]
        api.gate.set()
        await asyncio.gather(*tasks)
        return sent_while_unanswered

    sent_while_unanswered = asyncio.run(run())

    assert sorted(sent_while_unanswered) == ['Other shared context. ', 'Shared context. ']
    assert len(api.requests) == 4


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


@pytest.mark.parametrize(
    ('stop_reason', 'expected_error'),
    [
        ('refusal', LLMResponseError),
        ('max_tokens', LLMTruncatedResponseError),
        ('model_context_window_exceeded', LLMTruncatedResponseError),
    ],
)
def test_generate_rejects_unfinished_responses_with_their_usage(
    mock_api: MockAPIInstaller,
    stop_reason: str,
    expected_error: type[LLMResponseError],
) -> None:
    """Raise a response error carrying the usage, telling truncated responses apart, when the turn is unfinished."""
    mock_api({'/v1/messages': httpx2.Response(200, json=_message(stop_reason))})

    with pytest.raises(LLMResponseError) as exc_info:
        asyncio.run(_client().generate(REQUEST))

    assert type(exc_info.value) is expected_error
    assert TokenUsageMetrics.from_usage(exc_info.value.metrics or {}).reasoning_tokens == 200


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


def test_create_batch_checks_each_schema_once_and_sends_one_request_per_job(mock_api: MockAPIInstaller) -> None:
    """Check a shared schema once with a one-token request, then send one batch request per job."""
    api = mock_api(
        {
            '/v1/messages': httpx2.Response(200, json=_message('max_tokens')),
            '/v1/messages/batches': httpx2.Response(200, json=_batch('in_progress')),
        },
    )

    response = asyncio.run(_client().create_batch([REQUEST, REQUEST], ['job1', 'job2']))

    assert response.batch_id == 'msgbatch_1'
    assert response.provider == LLMProvider.ANTHROPIC
    assert [request.url.path for request in api.requests] == ['/v1/messages', '/v1/messages/batches']
    check = api.request_body(0)
    assert check['max_tokens'] == 1
    assert check['output_config'] == {'format': EXPECTED_PARAMS['output_config']['format']}
    assert api.request_body(1) == {
        'requests': [
            {'custom_id': 'job1', 'params': EXPECTED_PARAMS},
            {'custom_id': 'job2', 'params': EXPECTED_PARAMS},
        ],
    }


def test_create_batch_sends_a_rejected_schema_as_instructions(mock_api: MockAPIInstaller) -> None:
    """Send the batch with a schema the API rejects as instructions, without checking it again."""
    rejection = _error(400, 'invalid_request_error', 'Schemas contains too many parameters with union types')
    api = mock_api(
        {
            '/v1/messages': [rejection, httpx2.Response(200, json=_message('max_tokens'))],
            '/v1/messages/batches': httpx2.Response(200, json=_batch('in_progress')),
        },
    )
    client = _client()

    asyncio.run(client.create_batch([REQUEST], ['job1']))
    asyncio.run(client.create_batch([REQUEST], ['job2']))

    paths = [request.url.path for request in api.requests]
    assert paths == ['/v1/messages', '/v1/messages', '/v1/messages/batches', '/v1/messages/batches']
    assert 'output_config' not in api.request_body(1)
    for index in (2, 3):
        [batch_request] = api.request_body(index)['requests']
        assert 'format' not in batch_request['params']['output_config']
        assert batch_request['params']['system'].endswith(json.dumps(SCHEMA))


def test_create_batch_raises_when_the_check_is_invalid_for_another_reason(mock_api: MockAPIInstaller) -> None:
    """Raise the check's configuration error, without creating the batch, when it also fails without the schema."""
    api = mock_api(
        {
            '/v1/messages': [
                _error(400, 'invalid_request_error', 'Invalid model'),
                _error(400, 'invalid_request_error', 'Invalid model'),
            ],
        },
    )

    with pytest.raises(LLMConfigurationError, match='Invalid model'):
        asyncio.run(_client().create_batch([REQUEST], ['job1']))
    assert [request.url.path for request in api.requests] == ['/v1/messages', '/v1/messages']


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


def test_get_batch_results_parses_every_result_type_keeping_unsuccessful_responses_usage(
    mock_api: MockAPIInstaller,
) -> None:
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
    assert all(result.response is None for result in results.values())
    assert {job_id: (type(result.error), str(result.error)) for job_id, result in results.items()} == {
        'refused': (LLMResponseError, 'The LLM refused to generate a response'),
        'errored': (LLMTransientError, 'Batch request failed: Invalid schema'),
        'canceled': (LLMTransientError, 'Batch request was canceled before processing'),
        'expired': (LLMTransientError, 'Batch request expired before processing'),
    }
    refusal = results['refused'].error
    assert isinstance(refusal, LLMResponseError)
    assert refusal.metrics is not None


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


def _error(status_code: int, error_type: str, message: str) -> httpx2.Response:
    """Build an Anthropic API error response."""
    return httpx2.Response(status_code, json={'type': 'error', 'error': {'type': error_type, 'message': message}})


def test_generate_resends_a_rejected_schema_as_instructions_and_remembers_it(mock_api: MockAPIInstaller) -> None:
    """Resend a request whose enforced schema the API rejects without enforcing it, and stop enforcing that schema."""
    rejection = _error(400, 'invalid_request_error', 'Schemas contains too many parameters with union types')
    api = mock_api(
        {'/v1/messages': [rejection, httpx2.Response(200, json=_message()), httpx2.Response(200, json=_message())]}
    )
    client = _client()

    asyncio.run(client.generate(REQUEST))
    asyncio.run(client.generate(REQUEST))

    assert 'format' in api.request_body(0)['output_config']
    for index in (1, 2):
        assert 'format' not in api.request_body(index)['output_config']
        assert api.request_body(index)['system'].endswith(json.dumps(SCHEMA))


def test_generate_raises_the_original_error_when_the_request_is_invalid_for_another_reason(
    mock_api: MockAPIInstaller,
) -> None:
    """Raise the original configuration error when the request also fails without enforcing its schema."""
    invalid = _error(400, 'invalid_request_error', 'Invalid model')
    api = mock_api({'/v1/messages': [invalid, _error(400, 'invalid_request_error', 'Invalid model')]})

    with pytest.raises(LLMConfigurationError, match='Invalid model'):
        asyncio.run(_client().generate(REQUEST))
    assert len(api.requests) == 2


def test_generate_writes_the_cache_again_once_the_entry_may_have_expired(
    mock_api: MockAPIInstaller,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hold requests sharing a prefix again behind a new first request once its cache entry may have expired."""
    api = mock_api({'/v1/messages': httpx2.Response(200, json=_message())})
    api.delay = 0.05

    async def run() -> None:
        client = _client()
        await client.generate(REQUEST)
        monkeypatch.setattr(client_module, 'CACHE_ENTRY_LIFETIME', -1)
        await asyncio.gather(client.generate(REQUEST), client.generate(REQUEST))

    asyncio.run(run())

    assert api.max_in_flight == 1


def test_generate_lets_a_held_request_write_the_cache_when_the_first_one_fails(mock_api: MockAPIInstaller) -> None:
    """Let one held request write the cache entry when the first one fails, still holding the others."""
    api = mock_api(
        {
            '/v1/messages': [
                _error(500, 'api_error', 'Internal server error'),
                httpx2.Response(200, json=_message()),
                httpx2.Response(200, json=_message()),
            ],
        },
    )
    api.delay = 0.05

    async def run() -> list[Any]:
        client = _client()
        return await asyncio.gather(*(client.generate(REQUEST) for _ in range(3)), return_exceptions=True)

    results = asyncio.run(run())

    assert [type(result) for result in results].count(LLMTransientError) == 1
    assert len(api.requests) == 3
    assert api.max_in_flight == 1


def test_config_rejects_disabled_thinking_for_models_that_cannot_disable_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject at configuration time a model whose efforts map to disabled thinking when it can't disable it."""
    assert AnthropicConfig(api_key='test-key', model=MODEL).model == MODEL

    monkeypatch.setattr(config_module, 'THINKING_OPTIONAL_MODELS', frozenset())
    with pytest.raises(ValueError, match='cannot disable thinking'):
        AnthropicConfig(api_key='test-key', model=MODEL)
