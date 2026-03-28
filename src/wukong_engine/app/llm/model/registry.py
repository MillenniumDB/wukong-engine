from types import MappingProxyType

from .llm import LLM
from .provider import LLMProvider


class LLMRegistry:
    """Registry of supported LLM providers and their models."""

    _SUPPORTED: MappingProxyType[LLMProvider, frozenset[str]] = MappingProxyType(
        {
            LLMProvider.OPENAI: frozenset(
                {
                    'gpt-4.1-mini',
                    'gpt-4.1-nano',
                    'gpt-5-mini',
                    'gpt-5-nano',
                    'gpt-5.4-mini',
                    'gpt-5.4-nano',
                },
            ),
        },
    )

    @classmethod
    def is_supported_model(cls, model: LLM) -> bool:
        """Check if the given provider and model are supported."""
        return model.name in cls._SUPPORTED.get(model.provider, frozenset())

    @classmethod
    def get_supported_models(cls, provider: LLMProvider) -> list[str]:
        """Get the set of supported models for the given provider."""
        return sorted(cls._SUPPORTED.get(provider, frozenset()))
