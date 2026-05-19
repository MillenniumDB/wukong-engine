from .counter import TokenCounter


# TODO: Implement
class TiktokenTokenCounter(TokenCounter):
    """Counts tokens considering each character as a token."""

    def count(self, text: str) -> int:
        """Count the number of tokens in a given text."""
        return 0
