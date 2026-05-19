import re
from typing import ClassVar

from .text_tokenizer import TextTokenizer
from .tokenized_text import TokenizedText


class WhitespaceTokenizer(TextTokenizer):
    """Tokenizer using contiguous non-whitespace spans as tokens."""

    _TOKEN_PATTERN: ClassVar[re.Pattern] = re.compile(r'\S+')

    def tokenize(self, text: str) -> TokenizedText:
        """Tokenize a given text."""
        starts: list[int] = []
        ends: list[int] = []

        # Find contiguous non-whitespace spans as tokens
        for match in self._TOKEN_PATTERN.finditer(text):
            starts.append(match.start())
            ends.append(match.end())
        return TokenizedText(text=text, token_starts=tuple(starts), token_ends=tuple(ends))
