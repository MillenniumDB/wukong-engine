"""Tests for the LLM client factory, which requires only the API key of the configured model's provider."""

from pathlib import Path

import pytest

from wukong_engine.app.llm.exceptions import LLMConfigurationError
from wukong_engine.app.llm.model import LLM, LLMRegistry
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.infrastructure.llm.anthropic import AnthropicClient
from wukong_engine.infrastructure.llm.factory import EnvLLMClientFactory
from wukong_engine.infrastructure.llm.openai import OpenAIClient

MODEL = LLM(name='gpt-6-luna', provider=LLMProvider.OPENAI)


@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Start every test without API keys."""
    monkeypatch.chdir(tmp_path)  # Keep the project's .env file out of the test
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)


def test_the_configured_model_requires_the_api_key_of_its_provider() -> None:
    """Fail on initialization when the API key of the configured model's provider is missing."""
    with pytest.raises(RuntimeError, match='OPENAI_API_KEY'):
        EnvLLMClientFactory(model=MODEL)


def test_the_client_of_the_configured_model_uses_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up the client of the configured model's provider with that model."""
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    client = EnvLLMClientFactory(model=MODEL).get_client(LLMProvider.OPENAI)

    assert isinstance(client, OpenAIClient)
    assert client._config.model == MODEL


def test_other_providers_fail_only_when_their_client_is_requested_without_its_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create the client of another provider once its API key is available, with that provider's default model."""
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    factory = EnvLLMClientFactory(model=MODEL)

    with pytest.raises(LLMConfigurationError, match='ANTHROPIC_API_KEY'):
        factory.get_client(LLMProvider.ANTHROPIC)

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    client = factory.get_client(LLMProvider.ANTHROPIC)

    assert isinstance(client, AnthropicClient)
    assert client._config.model == LLMRegistry.default_model(LLMProvider.ANTHROPIC)
    assert factory.get_client(LLMProvider.ANTHROPIC) is client


def test_without_a_configured_model_no_api_key_is_needed_until_a_client_is_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start without any API key, as a reset does, failing only for the providers whose client is requested."""
    factory = EnvLLMClientFactory()

    with pytest.raises(LLMConfigurationError, match='OPENAI_API_KEY'):
        factory.get_client(LLMProvider.OPENAI)

    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    client = factory.get_client(LLMProvider.OPENAI)

    assert isinstance(client, OpenAIClient)
    assert client._config.model == LLMRegistry.default_model(LLMProvider.OPENAI)
