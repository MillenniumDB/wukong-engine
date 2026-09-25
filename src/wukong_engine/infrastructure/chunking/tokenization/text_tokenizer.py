"""Protocol for text tokenizers."""

from typing import Protocol

from .tokenized_text import TokenizedText


class TextTokenizer(Protocol):
    """Tokenizer capable of converting text into a tokenized form for efficient span measurement."""

    def tokenize(self, text: str) -> TokenizedText:
        """Tokenize a given text.

        Args:
            text: Text to tokenize.

        Returns:
            The text along with the character offsets of its tokens.
        """
        ...
