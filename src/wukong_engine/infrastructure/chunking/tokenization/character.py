"""Character-level text tokenizer."""

from .text_tokenizer import TextTokenizer
from .tokenized_text import TokenizedText


class CharacterTokenizer(TextTokenizer):
    """Tokenizer treating each character as a token."""

    def tokenize(self, text: str) -> TokenizedText:
        """Tokenize a given text.

        Args:
            text: Text to tokenize.

        Returns:
            The text with one token per character.
        """
        length = len(text)
        return TokenizedText(text=text, token_starts=tuple(range(length)), token_ends=tuple(range(1, length + 1)))
