"""Request model for LLM interactions."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMRequest:
    """Fully rendered request to be executed by an LLM client."""

    user_prompt: str
    system_prompt: str | None
    response_schema: Mapping[str, Any] | None = None
    model: str | None = None
