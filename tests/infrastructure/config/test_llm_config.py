"""Tests for the LLM settings resolved from the configuration file and the environment."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from wukong_engine.app.llm.elements.values import ReasoningEffort
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
        ('gpt-6-luna', ('gpt-6-luna', LLMProvider.OPENAI)),
        (None, ('gpt-6-luna', LLMProvider.OPENAI)),
    ],
)
def test_model_name_resolves_to_its_provider(name: str | None, expected_model: tuple[str, LLMProvider]) -> None:
    """Resolve each supported model to its provider, and an unset model to the default one."""
    assert _map_model(name) == expected_model


@pytest.mark.parametrize(
    ('value', 'expected'),
    [(None, None), ('none', ReasoningEffort.NONE), ('extreme', ReasoningEffort.EXTREME)],
)
def test_reasoning_effort_maps_to_its_level_or_to_none_when_unset(
    value: str | None,
    expected: ReasoningEffort | None,
) -> None:
    """Map a configured reasoning effort to its generalized level, leaving it unset when it isn't configured."""
    schema = ApplicationConfigSchema(llm=LLMConfigSchema.model_validate({'reasoning_effort': value}))
    assert ApplicationConfigMapper().map_configuration(schema).llm.reasoning_effort == expected


def test_unknown_reasoning_effort_is_rejected() -> None:
    """Reject a reasoning effort that isn't a generalized level, such as a provider's native name."""
    with pytest.raises(ValidationError):
        LLMConfigSchema.model_validate({'reasoning_effort': 'xhigh'})


def test_unsupported_model_error_lists_the_models_of_every_provider() -> None:
    """Reject an unsupported model, listing the supported models of every provider."""
    with pytest.raises(ValueError, match=r'gpt-6-luna \(OpenAI\).*claude-haiku-5-5 \(Anthropic\)'):
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


@pytest.mark.parametrize(('value', 'expected'), [(None, 'LOW'), ('medium', 'MEDIUM')])
def test_configuration_shows_the_reasoning_effort_that_runs(value: str | None, expected: str) -> None:
    """Show the configured reasoning effort, or the model's default level when it isn't configured."""
    schema = ApplicationConfigSchema(llm=LLMConfigSchema.model_validate({'reasoning_effort': value}))
    assert f'Reasoning Effort: {expected}' in str(ApplicationConfigMapper().map_configuration(schema).llm)


@pytest.mark.parametrize('name', ['', '   '])
def test_empty_model_name_is_rejected_instead_of_running_the_default_model(name: str) -> None:
    """Reject an empty model name, which would otherwise silently fall back to the default model."""
    with pytest.raises(ValidationError, match='must not be empty'):
        LLMConfigSchema.model_validate({'model': name})


def test_model_and_reasoning_effort_are_trimmed_and_case_insensitive() -> None:
    """Accept model names and reasoning efforts regardless of case and surrounding spaces, like the other keys."""
    schema = ApplicationConfigSchema(
        llm=LLMConfigSchema.model_validate({'model': ' Claude-Haiku-5-5 ', 'reasoning_effort': ' LOW '}),
    )
    llm = ApplicationConfigMapper().map_configuration(schema).llm

    assert (llm.model.name, llm.reasoning_effort) == ('claude-haiku-5-5', ReasoningEffort.LOW)


@pytest.mark.parametrize('value', [True, '8', 8.0])
def test_max_concurrency_must_be_an_integer(value: object) -> None:
    """Reject booleans, strings and floats for the concurrency, as the chunking sizes do."""
    with pytest.raises(ValidationError):
        LLMConfigSchema.model_validate({'max_concurrency': value})
