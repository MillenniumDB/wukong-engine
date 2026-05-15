from .counter import TokenCounter


class CharacterTokenCounter(TokenCounter):
    """Counts tokens considering each character as a token."""

    def count(self, text: str) -> int:
        """Count the number of tokens in a given text."""
        return len(text)
