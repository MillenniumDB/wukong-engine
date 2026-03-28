"""LLM response format."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ResponseFormatType(Enum):
    """Response format types for LLM outputs.

    Attributes:
        JSON: Structured output.
        TEXT: Free-form text.
    """

    JSON = 'json'
    TEXT = 'text'


@dataclass(frozen=True)
class ResponseFormat:
    """Defines the expected format of the LLM response."""

    type: ResponseFormatType = ResponseFormatType.TEXT
    schema: dict[str, Any] | None = None
