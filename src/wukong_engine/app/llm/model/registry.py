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
        """Whether the given model is supported."""
        return model.name in cls._SUPPORTED.get(model.provider, frozenset())

    @classmethod
    def supported_models(cls, provider: LLMProvider) -> list[str]:
        """Set of supported models for the given provider."""
        return sorted(cls._SUPPORTED.get(provider, frozenset()))

    @classmethod
    def default_model(cls) -> LLM:
        """Default LLM model."""
        return cls._DEFAULT_MODEL

    @classmethod
    def is_reasoning_model(cls, model: LLM) -> bool:
        """Whether the given model supports reasoning."""
        return model.name in cls._REASONING.get(model.provider, {})

    @classmethod
    def reasoning_effort(cls, model: LLM, effort_level: ReasoningEffort) -> str | None:
        """Native reasoning effort name for the given model and effort level, or None if not supported."""
        effort_levels = cls._REASONING.get(model.provider, {}).get(model.name)
        if effort_levels is None:
            return None
        return effort_levels.get(effort_level, effort_level.value)

    @classmethod
    def supports_explicit_caching(cls, model: LLM) -> bool:
        """Whether the given model supports explicit prompt caching, with caller-placed cache breakpoints."""
        return model.name in cls._EXPLICIT_CACHING.get(model.provider, frozenset())

    @classmethod
    def default_reasoning_effort(cls, model: LLM) -> str | None:
        """Default reasoning effort level for the given model, or None if not supported."""
        return cls._DEFAULT_REASONING.get(model.provider, {}).get(model.name)
