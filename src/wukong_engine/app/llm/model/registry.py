"""Registry of supported LLMs and their capabilities."""

from types import MappingProxyType
from typing import Any

from wukong_engine.app.llm.elements.values import ReasoningEffort

from .llm import LLM
from .values import LLMProvider


class LLMRegistry:
    """Registry of supported LLM providers and their models."""

    _DEFAULT_MODEL: LLM = LLM(provider=LLMProvider.OPENAI, name='gpt-6-luna')
    _DEFAULT_PROVIDER_MODELS: MappingProxyType[LLMProvider, LLM] = MappingProxyType(
        {
            LLMProvider.OPENAI: _DEFAULT_MODEL,
            LLMProvider.ANTHROPIC: LLM(provider=LLMProvider.ANTHROPIC, name='claude-haiku-5-5'),
        },
    )
    # Anthropic documents 29 days from the batch creation, while OpenAI's output files are reportedly deleted 30 days
    # after being written (undocumented), so 30 days is used for both, a day late at most for Anthropic
    _BATCH_RESULT_RETENTION_HOURS: MappingProxyType[LLMProvider, int] = MappingProxyType(
        {
            LLMProvider.OPENAI: 30 * 24,
            LLMProvider.ANTHROPIC: 30 * 24,
        },
    )
    _SUPPORTED: MappingProxyType[LLMProvider, frozenset[str]] = MappingProxyType(
        {
            LLMProvider.OPENAI: frozenset(
                {
                    'gpt-6-luna',
                },
            ),
            LLMProvider.ANTHROPIC: frozenset(
                {
                    'claude-haiku-5-5',
                },
            ),
        },
    )
    # Generalized levels mapped to the closest native one; a level without a mapping is sent by its own name
    _REASONING: MappingProxyType[LLMProvider, Any] = MappingProxyType(
        {
            LLMProvider.OPENAI: {
                'gpt-6-luna': {
                    ReasoningEffort.EXTREME: 'xhigh',
                },
            },
            LLMProvider.ANTHROPIC: {
                'claude-haiku-5-5': {
                    ReasoningEffort.EXTREME: 'xhigh',
                },
            },
        },
    )
    # Levels used when a request doesn't ask for one, as extraction requests don't, so these are tuned for it
    _DEFAULT_REASONING: MappingProxyType[LLMProvider, Any] = MappingProxyType(
        {
            LLMProvider.OPENAI: {
                'gpt-6-luna': ReasoningEffort.LOW,
            },
            LLMProvider.ANTHROPIC: {
                'claude-haiku-5-5': ReasoningEffort.LOW,
            },
        },
    )
    _EXPLICIT_CACHING: MappingProxyType[LLMProvider, frozenset[str]] = MappingProxyType(
        {
            LLMProvider.OPENAI: frozenset(
                {
                    'gpt-6-luna',
                },
            ),
            LLMProvider.ANTHROPIC: frozenset(
                {
                    'claude-haiku-5-5',
                },
            ),
        },
    )

    @classmethod
    def resolve_model(cls, name: str) -> LLM:
        """Resolve a model name into an LLM of the provider that supports it.

        Args:
            name: Model name to resolve.

        Returns:
            The model with the provider that supports it, or with the default provider if no provider supports it.
        """
        provider = next((provider for provider, models in cls._SUPPORTED.items() if name in models), None)
        return LLM(name=name, provider=provider) if provider is not None else LLM(name=name)

    @classmethod
    def is_supported_model(cls, model: LLM) -> bool:
        """Check whether the given model is supported.

        Args:
            model: Model to check.

        Returns:
            True if the model is supported by its provider, False otherwise.
        """
        return model.name in cls._SUPPORTED.get(model.provider, frozenset())

    @classmethod
    def supported_models(cls, provider: LLMProvider) -> list[str]:
        """Return the supported models for the given provider.

        Args:
            provider: Provider to list the models of.

        Returns:
            The names of the supported models, sorted alphabetically; empty if the provider has none.
        """
        return sorted(cls._SUPPORTED.get(provider, frozenset()))

    @classmethod
    def default_model(cls, provider: LLMProvider | None = None) -> LLM:
        """Return the default LLM model, overall or of a provider.

        Args:
            provider: Provider whose default model is returned. If None, the overall default model is returned.

        Returns:
            The model used when none is configured, for the given provider if any.
        """
        if provider is None:
            return cls._DEFAULT_MODEL
        return cls._DEFAULT_PROVIDER_MODELS[provider]

    @classmethod
    def batch_result_retention(cls, provider: LLMProvider) -> int:
        """Return how long the provider keeps the results of a batch available.

        Args:
            provider: Provider to get the retention of.

        Returns:
            The time, in hours since the batch creation, after which its results can no longer be retrieved.
        """
        return cls._BATCH_RESULT_RETENTION_HOURS[provider]

    @classmethod
    def is_reasoning_model(cls, model: LLM) -> bool:
        """Check whether the given model supports reasoning.

        Args:
            model: Model to check.

        Returns:
            True if the model supports reasoning, False otherwise.
        """
        return model.name in cls._REASONING.get(model.provider, {})

    @classmethod
    def reasoning_effort(cls, model: LLM, effort_level: ReasoningEffort) -> str | None:
        """Return the native reasoning effort name for the given model and effort level, or None if not supported.

        Args:
            model: Model to get the reasoning effort name for.
            effort_level: Generic reasoning effort level to translate.

        Returns:
            The model's native name for the effort level, which defaults to the level's own value when the model has
            no specific mapping for it, or None if the model doesn't support reasoning.
        """
        effort_levels = cls._REASONING.get(model.provider, {}).get(model.name)
        if effort_levels is None:
            return None
        return effort_levels.get(effort_level, effort_level.value)

    @classmethod
    def supports_explicit_caching(cls, model: LLM) -> bool:
        """Check whether the given model supports explicit prompt caching, with caller-placed cache breakpoints.

        Args:
            model: Model to check.

        Returns:
            True if the model supports explicit prompt caching, False otherwise.
        """
        return model.name in cls._EXPLICIT_CACHING.get(model.provider, frozenset())

    @classmethod
    def default_reasoning_effort(cls, model: LLM) -> ReasoningEffort | None:
        """Return the default reasoning effort level for the given model, or None if not supported.

        Args:
            model: Model to get the default reasoning effort for.

        Returns:
            The generalized level of the model's default reasoning effort (see ``reasoning_effort`` for its native
            name), or None if it has no default.
        """
        return cls._DEFAULT_REASONING.get(model.provider, {}).get(model.name)
