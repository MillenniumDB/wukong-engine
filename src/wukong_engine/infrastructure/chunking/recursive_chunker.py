"""Provides the RecursiveDocumentChunker class."""

from collections.abc import Iterator

from wukong_engine.app.document_ingestion.ports import DocumentChunker
from wukong_engine.core.documents.elements import Chunk, LoadedDocument
from wukong_engine.core.documents.elements.values import ChunkId

from .config import ChunkingConfig
from .models import Segment


# TODO: Overlap should it appear inside recursive split or only later?
# TODO: List vs Streaming
# TODO: Improve to avoid cutting words in half
# TODO: Other improvements mentioned by GPT
# TODO: Improvements for Merge Small Segments: Novel min size vs min size
# TODO: Tiktoken for tokenizing for GPT, add Tokenizer abstraction
# TODO: Best defaults for Config params
# TODO: Config Params from TOML config?
class RecursiveDocumentChunker(DocumentChunker):
    """Structure-aware recursive document chunker.

    Strategy:
        1. Split using configured separator hierarchy
        2. Pack segments toward target size
        3. Recursively refine oversized segments
        4. Hard split as terminal fallback
        5. Merge pathological small chunks

    Notes:
        - Offset-first architecture
        - Preserves contiguous source coverage
        - Supports arbitrary separator hierarchies
        - Token/character agnostic via token counter abstraction
        - Uses soft target chunk sizing
    """

    def __init__(self, config: ChunkingConfig) -> None:
        """Initialize the chunker with its configuration."""
        self._config = config

    def chunk(self, document: LoadedDocument) -> Iterator[Chunk]:
        """Chunk a document into smaller pieces."""
        text = self._normalize_text(document.content)
        root_segment = Segment(0, len(text))
        candidate_segments = self._split_recursive(text, root_segment, 0)
        final_segments = self._merge_small_segments(text, candidate_segments)
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

    # TODO: Check
    def _split_recursive(self, text: str, segment: Segment, level_index: int) -> list[Segment]:
        """Recursively split a segment using the separator hierarchy."""
        # Base case: segment already fits target size
        if self._measure(text, segment) <= self._config.target_chunk_size:
            return [segment]

        # Terminal fallback
        if level_index >= len(self._config.separators):
            return self._hard_split(text, segment)

        # Recursive case: split by current separator level and recurse on oversized segments
        separator = self._config.separators[level_index]
        atomic_segments = list(separator.split(text, segment.start, segment.end))

        # Ineffective split -> next separator level
        if len(atomic_segments) <= 1:
            return self._split_recursive(text, segment, level_index + 1)

        # Pack segments toward target size with recursive refinement of oversized segments
        output: list[Segment] = []
        current_start: int | None = None
        current_end: int | None = None
        for atomic in atomic_segments:
            atomic_size = self._measure(text, atomic)

            # Oversized atomic segment -> recurse deeper
            if atomic_size > self._config.target_chunk_size:
                if current_start is not None and current_end is not None:
                    output.append(Segment(current_start, current_end))
                    current_start = None
                    current_end = None
                output.extend(self._split_recursive(text, atomic, level_index + 1))
                continue

            # Initialize current packed chunk
            if current_start is None or current_end is None:
                current_start = atomic.start
                current_end = atomic.end
                continue

            # Check if adding the atomic segment would fit within target size
            candidate_segment = Segment(current_start, atomic.end)
            candidate_size = self._measure(text, candidate_segment)

            # Fits target size -> keep packing
            if candidate_size <= self._config.target_chunk_size:
                current_end = atomic.end
                continue

            # Finalize current chunk
            output.append(Segment(current_start, current_end))

            # Start new chunk with overlap
            overlap_start = self._compute_overlap_start(current_start=current_start, current_end=current_end)
            current_start = overlap_start
            current_end = atomic.end

        # Tail
        if current_start is not None and current_end is not None:
            output.append(Segment(current_start, current_end))

        return output

    # TODO: Check
    def _merge_small_segments(self, text: str, segments: list[Segment]) -> list[Segment]:
        """Merge pathological small chunks into neighboring chunks when possible."""
        if not segments:
            return segments

        merged: list[Segment] = [segments[0]]

        for current in segments[1:]:
            current_size = self._measure(text, current)

            # Already large enough
            if current_size >= self._config.min_chunk_size:
                merged.append(current)
                continue

            previous = merged[-1]

            merged_candidate = Segment(previous.start, current.end)
            merged_size = self._measure(text, merged_candidate)

            # Safe soft-overflow merge
            if merged_size <= self._config.max_chunk_size:
                merged[-1] = merged_candidate
                continue

            merged.append(current)

        return merged

    # TODO: Check
    def _hard_split(self, text: str, segment: Segment) -> list[Segment]:
        """Terminal fallback split ignoring structure."""
        output: list[Segment] = []
        start = segment.start
        end = segment.end
        step = self._config.target_chunk_size - self._config.overlap_size

        # Split into fixed-size chunks
        while start < end:
            chunk_end = start

            # Expand until target size reached
            while chunk_end < end:
                candidate_end = chunk_end + 1
                candidate_segment = Segment(start, candidate_end)
                candidate_size = self._measure(text, candidate_segment)
                if candidate_size > self._config.target_chunk_size:
                    break
                chunk_end = candidate_end

            # Ensure forward progress
            if chunk_end <= start:
                chunk_end = min(start + 1, end)

            output.append(Segment(start, chunk_end))
            if chunk_end >= end:
                break

            start += step

        return output

    def _compute_overlap_start(self, current_start: int, current_end: int) -> int:
        """Compute overlap start offset for next chunk."""
        return max(current_end - self._config.overlap_size, current_start)

    def _measure(self, text: str, segment: Segment) -> int:
        """Measure a segment using the token counter."""
        return self._config.token_counter.count(text[segment.start : segment.end])
