from enum import Enum


class ReasoningEffort(Enum):
    """Reasoning effort levels for LLMs. These can be used to indicate the desired level of reasoning complexity.

    Attributes:
        MINIMAL: Minimal reasoning effort, suitable for simple tasks (older models)
        NONE: Minimal reasoning effort, suitable for simple tasks
        LOW: Low reasoning effort, suitable for moderately complex tasks
        MEDIUM: Medium reasoning effort, suitable for complex tasks
        HIGH: High reasoning effort, suitable for very complex tasks
        XHIGH: Extra high reasoning effort, suitable for extremely complex tasks
    """

    MINIMAL = 'minimal'  # Minimal reasoning effort, suitable for simple tasks (older models)
    NONE = 'none'  # Minimal reasoning effort, suitable for simple tasks
    LOW = 'low'  # Low reasoning effort, suitable for moderately complex tasks
    MEDIUM = 'medium'  # Medium reasoning effort, suitable for complex tasks
    HIGH = 'high'  # High reasoning effort, suitable for very complex tasks
    XHIGH = 'xhigh'  # Extra high reasoning effort, suitable for extremely complex tasks
