"""Tests for the fallbacks of the OpenAI LLM client for response schemas, run against a mocked OpenAI API."""

import asyncio
import json
from functools import partial
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

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
from wukong_engine.infrastructure.llm.openai import OpenAIClient, OpenAIConfig
from wukong_engine.infrastructure.llm.openai import client as client_module
from wukong_engine.infrastructure.llm.openai.schema import MAX_PROPERTIES

SCHEMA = {
    'type': 'object',
    'properties': {'entities': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['entities'],
    'additionalProperties': False,
}
RESPONSE = {
    'id': 'resp_1',
    'object': 'response',
    'created_at': 0,
    'status': 'completed',
    'model': 'gpt-5.6-luna',
    'output': [
        {
            'type': 'message',
            'id': 'msg_1',
            'status': 'completed',
            'role': 'assistant',
            'content': [{'type': 'output_text', 'text': '{"entities": []}', 'annotations': []}],
        },
    ],
    'parallel_tool_calls': True,
    'tool_choice': 'auto',
    'tools': [],
    'usage': {
        'input_tokens': 10,
        'input_tokens_details': {'cached_tokens': 0},
        'output_tokens': 5,
        'output_tokens_details': {'reasoning_tokens': 0},
        'total_tokens': 15,
    },
}


def _request(schema: dict[str, Any]) -> LLMRequest:
    """Build an extraction request with the given response schema."""
    prompt = LLMPrompt(content='Sentence.', instructions='Extract the entities.', schema=schema)
    return LLMRequest(prompt=prompt, reasoning_effort=ReasoningEffort.LOW)


def _bad_request(code: str, param: str) -> httpx.Response:
    """Build an OpenAI API invalid request error response."""
    error = {'message': 'Invalid request', 'type': 'invalid_request_error', 'param': param, 'code': code}
    return httpx.Response(400, json={'error': error})


class MockOpenAIAPI:
    """Mocked OpenAI API that records the request bodies it receives and serves the given responses in turn."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        """Initialize the mocked API.

        Args:
            responses: Responses served in turn, one per request.
        """
        self.responses = responses
        self.bodies: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Record the request body (empty for requests without one) and serve the next response."""
        self.bodies.append(json.loads(request.content) if request.content else {})
        return self.responses.pop(0)


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a function that routes the clients created afterwards to a mocked API serving the given responses."""

    def install(responses: list[httpx.Response]) -> MockOpenAIAPI:
        api = MockOpenAIAPI(responses)
        http_client = DefaultAsyncHttpxClient(transport=httpx.MockTransport(api.handle))
        monkeypatch.setattr(client_module, 'AsyncOpenAI', partial(AsyncOpenAI, http_client=http_client))
        return api

    return install


def _client() -> OpenAIClient:
    """Build a client for the default model, without SDK retries."""
    return OpenAIClient(OpenAIConfig(api_key='test-key', model=LLM(name='gpt-5.6-luna'), max_retries=0))


def _is_unenforced(body: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Check whether a request body leads its input with the schema as instructions, enforcing only valid JSON."""
    first_block = body['input'][0]['content'][0]['text']
    return body['text'] == {'format': {'type': 'json_object'}} and first_block.endswith(json.dumps(schema))


def test_generate_resends_a_rejected_schema_as_instructions_and_remembers_it(mock_api: Any) -> None:
    """Resend a request whose schema the API rejects as JSON mode with instructions, and stop enforcing it."""
    api = mock_api(
        [
            _bad_request('invalid_json_schema', 'text.format.schema'),
            httpx.Response(200, json=RESPONSE),
            httpx.Response(200, json=RESPONSE),
        ],
    )
    client = _client()

    asyncio.run(client.generate(_request(SCHEMA)))
    response = asyncio.run(client.generate(_request(SCHEMA)))

    assert response.content == '{"entities": []}'
    assert api.bodies[0]['text']['format']['type'] == 'json_schema'
    assert all(_is_unenforced(body, SCHEMA) for body in api.bodies[1:])


def test_generate_raises_other_invalid_requests_without_resending(mock_api: Any) -> None:
    """Raise a configuration error, without resending, when the request is invalid for another reason."""
    api = mock_api([_bad_request('unknown_parameter', 'not_a_real_param')])

    with pytest.raises(LLMConfigurationError):
        asyncio.run(_client().generate(_request(SCHEMA)))
    assert len(api.bodies) == 1


def test_generate_sends_a_schema_over_the_limits_as_instructions(mock_api: Any) -> None:
    """Send a schema over the structured output limits as instructions from the first request."""
    oversized = {
        'type': 'object',
        'properties': {f'p{i}': {'type': 'string'} for i in range(MAX_PROPERTIES + 1)},
        'additionalProperties': False,
    }
    api = mock_api([httpx.Response(200, json=RESPONSE)])

    asyncio.run(_client().generate(_request(oversized)))

    assert _is_unenforced(api.bodies[0], oversized)


@pytest.mark.parametrize(
    ('reason', 'expected_error'),
    [('max_output_tokens', LLMTruncatedResponseError), ('content_filter', LLMResponseError)],
)
def test_generate_rejects_incomplete_responses_with_their_usage(
    mock_api: Any,
    reason: str,
    expected_error: type[LLMResponseError],
) -> None:
    """Raise a response error carrying the usage, telling responses cut off by the output limit apart."""
    incomplete = RESPONSE | {'status': 'incomplete', 'incomplete_details': {'reason': reason}}
    mock_api([httpx.Response(200, json=incomplete)])

    with pytest.raises(LLMResponseError) as exc_info:
        asyncio.run(_client().generate(_request(SCHEMA)))

    assert type(exc_info.value) is expected_error
    assert (exc_info.value.metrics or {}).get('output_tokens') == RESPONSE['usage']['output_tokens']


@pytest.mark.parametrize(
    ('code', 'expected_error'),
    [('insufficient_quota', LLMConfigurationError), ('rate_limit_exceeded', LLMTransientError)],
)
def test_generate_stops_on_an_exhausted_quota_but_not_on_rate_limits(
    mock_api: Any,
    code: str,
    expected_error: type[LLMError],
) -> None:
    """Treat an exhausted quota as a configuration error, unlike a rate limit, though both are reported as 429."""
    error = {'message': 'Too many requests', 'type': 'requests', 'param': None, 'code': code}
    mock_api([httpx.Response(429, json={'error': error})])

    with pytest.raises(expected_error):
        asyncio.run(_client().generate(_request(SCHEMA)))


def test_get_batch_results_reads_the_error_file_when_every_request_failed(mock_api: Any) -> None:
    """Return the error file's results, instead of failing, for a completed batch without an output file."""
    batch = {
        'id': 'batch_1',
        'object': 'batch',
        'endpoint': '/v1/responses',
        'input_file_id': 'file-in',
        'completion_window': '24h',
        'status': 'completed',
        'created_at': 0,
        'output_file_id': None,
        'error_file_id': 'file-err',
    }
    error_line = {
        'id': 'batch_req_1',
        'custom_id': 'job1',
        'response': {'status_code': 400, 'body': {'error': {'message': 'Invalid schema'}}},
        'error': None,
    }
    mock_api([httpx.Response(200, json=batch), httpx.Response(200, text=json.dumps(error_line))])

    results = asyncio.run(_client().get_batch_results('batch_1'))

    [result] = results
    assert (result.job_id, result.response) == ('job1', None)
    assert isinstance(result.error, LLMTransientError)
    assert str(result.error) == 'Batch request failed: Invalid schema'


def test_get_batch_results_keeps_the_finished_requests_of_an_expired_batch(mock_api: Any) -> None:
    """Return the results of the requests an expired batch finished, from its output file."""
    batch = {
        'id': 'batch_1',
        'object': 'batch',
        'endpoint': '/v1/responses',
        'input_file_id': 'file-in',
        'completion_window': '24h',
        'status': 'expired',
        'created_at': 0,
        'output_file_id': 'file-out',
        'error_file_id': None,
    }
    output_line = {'id': 'batch_req_1', 'custom_id': 'job1', 'response': {'status_code': 200, 'body': RESPONSE}}
    mock_api([httpx.Response(200, json=batch), httpx.Response(200, text=json.dumps(output_line))])

    [result] = asyncio.run(_client().get_batch_results('batch_1'))

    assert result.job_id == 'job1'
    assert result.error is None
    assert result.response is not None
    assert result.response.content == '{"entities": []}'
