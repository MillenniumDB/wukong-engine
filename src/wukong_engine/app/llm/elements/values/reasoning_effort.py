"""Reasoning effort levels for LLM requests."""

from enum import Enum


class ReasoningEffort(Enum):
    """Reasoning effort levels for LLMs. These can be used to indicate the desired level of reasoning complexity.

    Attributes:
        NONE: Suitable for simple tasks (e.g. classification, fast retrieval), may not even apply reasoning.
        LOW: Suitable for moderate tasks (e.g. data analysis, chatbots).
        MEDIUM: Suitable for complex tasks (e.g. agentic coding, research).
        HIGH: Suitable for very complex tasks (e.g. complex agentic coding, complex research).
        EXTREME: Suitable for extremely complex tasks (e.g. deep research, code review).
        MAX: Suitable for the most complex tasks possible (evaluate against EXTREME).
    """

    NONE = 'none'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    EXTREME = 'extreme'
    MAX = 'max'
