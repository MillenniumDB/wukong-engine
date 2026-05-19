from .counter import TokenCounter


class CharacterTokenCounter(TokenCounter):
    """Counts tokens approximating each token as a fixed amount of characters."""

    def count(self, text: str) -> int:
        """Count the number of tokens in a given text."""
        return len(text) // 4
