from typing import Protocol

from .request import LLMRequest
from .response import LLMResponse


class LLMClient(Protocol):
    """Large Language Model (LLM) client."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request."""
        ...
