from types import MappingProxyType
from typing import Any

from wukong_engine.app.llm.elements.values import ReasoningEffort

from .llm import LLM
from .values import LLMProvider


class LLMRegistry:
    """Registry of supported LLM providers and their models."""

    _DEFAULT_MODEL: LLM = LLM(provider=LLMProvider.OPENAI, name='gpt-5-mini')
    _SUPPORTED: MappingProxyType[LLMProvider, frozenset[str]] = MappingProxyType(
        {
            LLMProvider.OPENAI: frozenset(
                {
                    'gpt-4.1-mini',
                    'gpt-5-mini',
                    'gpt-5.4-mini',
                },
            ),
        },
    )
    _REASONING: MappingProxyType[LLMProvider, Any] = MappingProxyType(
        {
            LLMProvider.OPENAI: {
                'gpt-5-mini': {'effort': ReasoningEffort.MINIMAL},
                'gpt-5.4-mini': {'effort': ReasoningEffort.NONE},
            },
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
    def get_reasoning_effort(cls, model: LLM) -> ReasoningEffort | None:
        """Default reasoning effort level for the given model, or None if not supported."""
        return cls._REASONING.get(model.provider, {}).get(model.name, {}).get('effort')
