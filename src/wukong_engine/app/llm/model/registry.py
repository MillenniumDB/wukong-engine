"""Registry of supported LLMs and their capabilities."""

from types import MappingProxyType
from typing import Any

from wukong_engine.app.llm.elements.values import ReasoningEffort

from .llm import LLM
from .values import LLMProvider


class LLMRegistry:
    """Registry of supported LLM providers and their models."""

    _DEFAULT_MODEL: LLM = LLM(provider=LLMProvider.OPENAI, name='gpt-5.6-luna')
    _SUPPORTED: MappingProxyType[LLMProvider, frozenset[str]] = MappingProxyType(
        {
            LLMProvider.OPENAI: frozenset(
                {
                    'gpt-4.1-mini',
                    'gpt-5.6-luna',
                },
            ),
        },
    )
    _REASONING: MappingProxyType[LLMProvider, Any] = MappingProxyType(
        {
            LLMProvider.OPENAI: {
                'gpt-5.6-luna': {
                    ReasoningEffort.EXTREME: 'xhigh',
                },
            },
        },
    )
    _DEFAULT_REASONING: MappingProxyType[LLMProvider, Any] = MappingProxyType(
        {
            LLMProvider.OPENAI: {
                'gpt-5.6-luna': 'low',
            },
        },
    )
    _EXPLICIT_CACHING: MappingProxyType[LLMProvider, frozenset[str]] = MappingProxyType(
        {
            LLMProvider.OPENAI: frozenset(
                {
                    'gpt-5.6-luna',
                },
            ),
        },
    )

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
    def default_model(cls) -> LLM:
        """Return the default LLM model.

        Returns:
            The model used when none is configured.
        """
        return cls._DEFAULT_MODEL

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
    def default_reasoning_effort(cls, model: LLM) -> str | None:
        """Return the default reasoning effort level for the given model, or None if not supported.

        Args:
            model: Model to get the default reasoning effort for.

        Returns:
            The model's native name for its default reasoning effort, or None if it has no default.
        """
        return cls._DEFAULT_REASONING.get(model.provider, {}).get(model.name)
