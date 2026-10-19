"""Tests for the LLM settings resolved from the configuration file and the environment."""

from pathlib import Path

import pytest

from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.infrastructure.config.env import load_env_config
from wukong_engine.infrastructure.config.mapper import ApplicationConfigMapper
from wukong_engine.infrastructure.config.schemas import ApplicationConfigSchema, LLMConfigSchema


def _map_model(name: str | None) -> tuple[str, LLMProvider]:
    """Map an ``[llm]`` model name through the configuration mapper and return the resolved name and provider."""
    schema = ApplicationConfigSchema(llm=LLMConfigSchema(model=name))
    model = ApplicationConfigMapper().map_configuration(schema).llm.model
    return model.name, model.provider


@pytest.mark.parametrize(
    ('name', 'expected_model'),
    [
        ('claude-haiku-5-5', ('claude-haiku-5-5', LLMProvider.ANTHROPIC)),
        ('gpt-4.1-mini', ('gpt-4.1-mini', LLMProvider.OPENAI)),
        (None, ('gpt-5.6-luna', LLMProvider.OPENAI)),
    ],
)
def test_model_name_resolves_to_its_provider(name: str | None, expected_model: tuple[str, LLMProvider]) -> None:
    """Resolve each supported model to its provider, and an unset model to the default one."""
    assert _map_model(name) == expected_model


def test_unsupported_model_error_lists_the_models_of_every_provider() -> None:
    """Reject an unsupported model, listing the supported models of every provider."""
    with pytest.raises(ValueError, match=r'gpt-5\.6-luna \(OpenAI\).*claude-haiku-5-5 \(Anthropic\)'):
        _map_model('claude-opus-5-5')


@pytest.mark.parametrize(
    ('provider', 'variable'),
    [(LLMProvider.OPENAI, 'OPENAI_API_KEY'), (LLMProvider.ANTHROPIC, 'ANTHROPIC_API_KEY')],
)
def test_only_the_api_key_of_the_configured_provider_is_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    provider: LLMProvider,
    variable: str,
) -> None:
    """Load the API key of the configured provider, failing only when that provider's key is missing."""
    monkeypatch.chdir(tmp_path)  # Keep the project's .env file out of the test
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    with pytest.raises(RuntimeError, match=variable):
        load_env_config(provider)

    monkeypatch.setenv(variable, 'test-key')
    assert load_env_config(provider).llm_api_key == 'test-key'
