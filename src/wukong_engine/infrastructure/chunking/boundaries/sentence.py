"""Sentence boundary rules based on regular expressions and Blingfire."""

import re
from collections.abc import Iterator
from typing import ClassVar

from blingfire import text_to_sentences_and_offsets

from wukong_engine.infrastructure.chunking.models import Segment

from .boundary import Boundary


class RegexSentenceBoundary(Boundary):
    """Boundary rule capable of partitioning text into sentences using regular expressions."""

    _PATTERN: ClassVar[re.Pattern] = re.compile(r'(?<=[.!?])(?:["\')\]]+)?\s+')

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments ending after sentence-ending punctuation and whitespace.

        Args:
            text: Full text being chunked; offsets refer to positions in this string.
            start: Offset where the region to split begins (inclusive).
            end: Offset where the region to split ends (exclusive).

        Yields:
            Contiguous, non-overlapping segments that together cover ``text[start:end]``.
        """
        # Sliding window looking for sentence-ending punctuation
        sentence_start = start
        for match in self._PATTERN.finditer(text, start, end):
            sentence_end = match.end()
            yield Segment(sentence_start, sentence_end)
            sentence_start = sentence_end

        # Add final sentence if there's remaining text
        if sentence_start < end:
            yield Segment(sentence_start, end)


class BlingfireSentenceBoundary(Boundary):
    """Boundary rule capable of partitioning text into sentences using the specialized Blingfire library."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into sentence segments using Blingfire sentence offsets.

        Args:
            text: Full text being chunked; offsets refer to positions in this string.
            start: Offset where the region to split begins (inclusive).
            end: Offset where the region to split ends (exclusive).

        Yields:
            Contiguous, non-overlapping segments that together cover ``text[start:end]``.
        """
        # Get normalized sentence offsets from Blingfire
        subtext = text[start:end]
        _, offsets = text_to_sentences_and_offsets(subtext)

        # Convert relative offsets to absolute offsets and yield non-normalized segments
        current_start = start
        for _, relative_end in offsets:
            segment_end = min(start + relative_end, end)

            # Defensive validation
            if segment_end <= current_start:
                continue

            yield Segment(current_start, segment_end)
            current_start = segment_end

        # Add final sentence if there's remaining text
        if current_start < end:
            yield Segment(current_start, end)
