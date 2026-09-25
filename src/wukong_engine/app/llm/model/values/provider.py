"""Supported LLM providers."""

from enum import Enum


class LLMProvider(Enum):
    """LLM providers supported by the engine.

    Attributes:
        OPENAI: OpenAI's LLM offerings.
    """

    OPENAI = 'OpenAI'
