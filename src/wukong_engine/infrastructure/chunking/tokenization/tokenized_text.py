"""Tokenized text with character offsets for span measurement."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenizedText:
    """Indexed tokenized representation of a text.

    Invariants, enforced on creation:
        - len(token_starts) == len(token_ends)
        - token_starts is sorted ascending
        - token_ends is sorted ascending
        - token_starts[i] < token_ends[i]

    Attributes:
        text: The original text.
        token_starts: Character offset where each token starts (inclusive).
        token_ends: Character offset where each token ends (exclusive).
    """

    text: str
    token_starts: tuple[int, ...]
    token_ends: tuple[int, ...]

    def __post_init__(self) -> None:
        """Validate the invariants of the tokenized text.

        Raises:
            ValueError: If the token offsets break any of the invariants.
        """
        self._validate_token_offsets()

    def _validate_token_offsets(self) -> None:
        """Validate the token offsets.

        Raises:
            ValueError: If the offset arrays differ in length, aren't sorted, or contain an empty or inverted span.
        """
        if len(self.token_starts) != len(self.token_ends):
            raise ValueError('token offset arrays must have equal length')

        # Validate sortedness and span validity
        previous_start = -1
        previous_end = -1
        for start, end in zip(self.token_starts, self.token_ends, strict=True):
            if start < previous_start:
                raise ValueError('token_starts must be sorted')
            if end < previous_end:
                raise ValueError('token_ends must be sorted')
            if start >= end:
                raise ValueError('invalid token span')
            previous_start = start
            previous_end = end

    @property
    def is_empty(self) -> bool:
        """Whether the text contains no tokens."""
        return not self.token_starts

    @property
    def token_count(self) -> int:
        """Total number of tokens in the text."""
        return len(self.token_starts)

    def count(self, start: int, end: int) -> int:
        """Count tokens overlapping the character span [start, end).

        A token overlaps if: token_end > start AND token_start < end

        Args:
            start: Start character offset (inclusive).
            end: End character offset (exclusive).

        Returns:
            The number of overlapping tokens, 0 for an empty span.

        Raises:
            ValueError: If the span is negative, inverted, or exceeds the text length.
        """
        self._validate_span(start, end)

        # Empty spans have no tokens
        if start == end:
            return 0

        # Binary search
        left = bisect_right(self.token_ends, start)
        right = bisect_left(self.token_starts, end)
        return max(0, right - left)

    def token_span(self, start: int, end: int) -> tuple[int, int]:
        """Get the token span overlapping the character span [start, end).

        Args:
            start: Start character offset (inclusive).
            end: End character offset (exclusive).

        Returns:
            The token indices [token_start_index, token_end_index). An empty character span yields an empty token span
            at the index of the first token starting at or after ``start``.

        Raises:
            ValueError: If the span is negative, inverted, or exceeds the text length.
        """
        self._validate_span(start, end)

        # Empty spans have empty token spans at the insertion point
        if start == end:
            index = bisect_left(self.token_starts, start)
            return (index, index)

        # Binary search
        token_start = bisect_right(self.token_ends, start)
        token_end = bisect_left(self.token_starts, end)
        return token_start, token_end

    def char_span(self, token_start: int, token_end: int) -> tuple[int, int]:
        """Get the character span covered by the token slice [token_start, token_end).

        Args:
            token_start: Index of the first token (inclusive).
            token_end: Index past the last token (exclusive).

        Returns:
            The character offsets [char_start, char_end). An empty token slice yields an empty span at the start of
            token ``token_start``, or at the end of the text if it's past the last token.

        Raises:
            ValueError: If the token slice is negative, inverted, or exceeds the token count.
        """
        self._validate_token_span(token_start, token_end)

        # Empty token spans have empty character spans at the token boundaries
        if token_start == token_end:
            if token_start >= self.token_count:
                return (len(self.text), len(self.text))
            offset = self.token_starts[token_start]
            return (offset, offset)

        # Retrieve character offsets from the token span
        char_start = self.token_starts[token_start]
        char_end = self.token_ends[token_end - 1]
        return char_start, char_end

    def _validate_span(self, start: int, end: int) -> None:
        """Validate character span.

        Args:
            start: Start character offset (inclusive).
            end: End character offset (exclusive).

        Raises:
            ValueError: If ``start`` is negative, ``end`` is before ``start``, or ``end`` exceeds the text length.
        """
        if start < 0:
            raise ValueError('start must be >= 0')
        if end < start:
            raise ValueError('end must be >= start')
        if end > len(self.text):
            raise ValueError('end exceeds text length')

    def _validate_token_span(self, start: int, end: int) -> None:
        """Validate token span.

        Args:
            start: Start token index (inclusive).
            end: End token index (exclusive).

        Raises:
            ValueError: If ``start`` is negative, ``end`` is before ``start``, or ``end`` exceeds the token count.
        """
        if start < 0:
            raise ValueError('token start must be >= 0')
        if end < start:
            raise ValueError('token end must be >= start')
        if end > self.token_count:
            raise ValueError('token end exceeds token count')
