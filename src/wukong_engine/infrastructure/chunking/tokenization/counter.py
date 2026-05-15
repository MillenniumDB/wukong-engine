from typing import Protocol


class TokenCounter(Protocol):
    """Counts tokens inside text."""

    def count(self, text: str) -> int:
        """Count the number of tokens in a given text."""
        ...
