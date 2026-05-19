"""Provides the RecursiveDocumentChunker class."""

import itertools
from collections.abc import Iterator

from wukong_engine.app.document_ingestion.ports import DocumentChunker
from wukong_engine.core.documents.elements import Chunk, LoadedDocument
from wukong_engine.core.documents.elements.values import ChunkId

from .models import Segment
from .plan import ChunkingPlan
from .tokenization import TokenizedText


class RecursiveDocumentChunker(DocumentChunker):
    """Structure-aware recursive document chunker.

    Strategy:
        1. Split using configured boundary hierarchy
        2. Pack segments toward target size
        3. Recursively refine oversized segments
        4. Hard split as terminal fallback
        5. Apply overlap in post-processing

    Notes:
        - Offset-first architecture
        - Preserves contiguous source coverage
        - Supports arbitrary boundary hierarchies
        - Token agnostic via tokenized text abstraction
        - Uses soft target chunk sizing
    """

    def __init__(self, plan: ChunkingPlan) -> None:
        """Initialize the chunker with its configuration."""
        self._plan = plan

    def chunk(self, document: LoadedDocument) -> Iterator[Chunk]:
        """Chunk a document into smaller pieces."""
        text = self._normalize_text(document.content)
        root_segment = Segment(0, len(text))
        tokenized_text = self._plan.tokenizer.tokenize(text)
        segments = self._split_recursive(tokenized_text, root_segment, 0)
        final_segments = self._apply_overlap(tokenized_text, segments)
        for chunk_index, segment in enumerate(final_segments):
            yield Chunk(
                id=ChunkId.from_identity(document.metadata.id, chunk_index),
                document_id=document.metadata.id,
                chunk_index=chunk_index,
                start_offset=segment.start,
                end_offset=segment.end,
                content=text[segment.start : segment.end],
            )

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize document text for more consistent chunking.

        Current Strategy (conservative for preservation):
            - Normalize newlines to unix standard
            - Remove null bytes
        """
        return (
            text.replace('\r\n', '\n')
            .replace('\r', '\n')
            .replace('\u2028', '\n')
            .replace('\u2029', '\n')
            .replace('\x00', '')
        )

    def _split_recursive(self, tokenized_text: TokenizedText, segment: Segment, level_index: int) -> list[Segment]:
        """Recursively split a segment using the boundary hierarchy."""
        # Base case: segment is acceptable, no further splitting needed
        if self._measure(tokenized_text, segment) <= self._plan.max_size:
            return [segment]

        # Terminal fallback to hard split when boundaries are exhausted
        if level_index >= len(self._plan.boundaries):
            return self._hard_split(tokenized_text, segment)

        # Recursive case: split by current boundary level
        boundary = self._plan.boundaries[level_index]
        atomic_segments = list(boundary.split(tokenized_text.text, segment.start, segment.end))

        # Ineffective split -> next boundary level
        if len(atomic_segments) <= 1:
            return self._split_recursive(tokenized_text, segment, level_index + 1)

        # Pack segments toward target size with recursive refinement of oversized segments
        output: list[Segment] = []
        current_start: int | None = None
        current_end: int | None = None
        for atomic in atomic_segments:
            atomic_size = self._measure(tokenized_text, atomic)

            # Recursively refine segments that exceed max size
            if atomic_size > self._plan.max_size:
                refined_segments = self._split_recursive(tokenized_text, atomic, level_index + 1)
            else:
                refined_segments = [atomic]

            # Feed refined segments into the local packer
            for refined in refined_segments:
                # Initialize current packed chunk
                if current_start is None or current_end is None:
                    current_start = refined.start
                    current_end = refined.end
                    continue

                # Check the candidate chunk if we add the refined segment
                current = Segment(current_start, current_end)
                candidate = Segment(current_start, refined.end)
                current_size = self._measure(tokenized_text, current)
                candidate_size = self._measure(tokenized_text, candidate)

                # Fits target size -> keep packing
                if candidate_size <= self._plan.target_size:
                    current_end = refined.end
                    continue

                # Exceeds max size -> finalize current chunk and start next one
                if candidate_size > self._plan.max_size:
                    output.append(current)
                    current_start = refined.start
                    current_end = refined.end
                    continue

                # Soft size breach -> decide based on proximity to target size
                current_distance = abs(self._plan.target_size - current_size)
                candidate_distance = abs(self._plan.target_size - candidate_size)
                if candidate_distance <= current_distance:
                    current_end = refined.end
                else:
                    output.append(current)
                    current_start = refined.start
                    current_end = refined.end

        # Tail
        if current_start is not None and current_end is not None:
            output.append(Segment(current_start, current_end))

        return output

    def _apply_overlap(self, tokenized_text: TokenizedText, segments: list[Segment]) -> list[Segment]:
        """Apply token-based overlap between adjacent chunks."""
        if self._plan.overlap_size <= 0 or len(segments) <= 1:
            return segments

        # Compute overlap start for each segment except the first one
        output: list[Segment] = [segments[0]]
        for previous, current in itertools.pairwise(segments):
            overlap_start = self._compute_overlap_start(tokenized_text, previous)
            output.append(Segment(overlap_start, current.end))

        return output

    def _measure(self, tokenized_text: TokenizedText, segment: Segment) -> int:
        """Measure a segment in tokens."""
        return tokenized_text.count(segment.start, segment.end)

    def _hard_split(self, tokenized_text: TokenizedText, segment: Segment) -> list[Segment]:
        """Terminal fallback split using token boundaries."""
        segment_token_start, segment_token_end = tokenized_text.token_span(segment.start, segment.end)
        output: list[Segment] = []
        start_token = segment_token_start

        # Iterate through token spans of target size
        while start_token < segment_token_end:
            end_token = min(start_token + self._plan.max_size, segment_token_end)
            char_start, char_end = tokenized_text.char_span(start_token, end_token)
            char_start = max(char_start, segment.start)
            char_end = min(char_end, segment.end)

            # Snap artificial split boundaries
            if end_token < segment_token_end:
                snapped_end = self._snap_backward_to_whitespace(tokenized_text.text, char_end, min_offset=char_start)

                # Avoid creating an empty chunk
                if snapped_end > char_start:
                    char_end = snapped_end
                    _, end_token = tokenized_text.token_span(char_start, char_end)

            # Finalize current chunk and start the next one
            output.append(Segment(char_start, char_end))
            start_token = end_token

        return output

    def _compute_overlap_start(self, tokenized_text: TokenizedText, segment: Segment) -> int:
        """Compute chunk overlap start using token counts."""
        token_start, token_end = tokenized_text.token_span(segment.start, segment.end)
        overlap_token_start = max(token_end - self._plan.overlap_size, token_start)
        overlap_start, _ = tokenized_text.char_span(overlap_token_start, overlap_token_start)
        return self._snap_forward_to_whitespace(tokenized_text.text, overlap_start, max_offset=segment.end)

    @staticmethod
    def _is_inside_word(text: str, offset: int) -> bool:
        """Check if the offset is in the middle of a word."""
        if offset <= 0 or offset >= len(text):
            return False
        return not text[offset - 1].isspace() and not text[offset].isspace()

    def _snap_forward_to_whitespace(self, text: str, offset: int, *, max_offset: int, max_adjustment: int = 30) -> int:
        """Move forward until reaching whitespace."""
        # Avoid snapping if not inside a word
        if not self._is_inside_word(text, offset):
            return offset

        limit = min(offset + max_adjustment, max_offset + 1, len(text))
        for i in range(offset, limit):
            if text[i].isspace():
                return i
        if limit == len(text):
            return len(text)

        return offset

    def _snap_backward_to_whitespace(self, text: str, offset: int, *, min_offset: int, max_adjustment: int = 30) -> int:
        """Move backward until reaching whitespace."""
        # Avoid snapping if not inside a word
        if not self._is_inside_word(text, offset):
            return offset

        limit = max(offset - max_adjustment, min_offset, 0)
        for i in range(offset, limit, -1):
            if text[i - 1].isspace():
                return i
        return offset
