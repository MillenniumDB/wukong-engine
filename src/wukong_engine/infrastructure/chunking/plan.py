"""Chunking plan configuration for the recursive chunker."""

from dataclasses import dataclass, field

from wukong_engine.app.config.chunking import MAX_ALLOWED_MAX_TOKENS, MAX_ALLOWED_TARGET_TOKENS

from .boundaries import (
    BlingfireSentenceBoundary,
    Boundary,
    LineBoundary,
    MarkdownHeadingBoundary,
    ParagraphBoundary,
    WordBoundary,
)
from .tokenization import HuggingFaceTokenizer, TextTokenizer


@dataclass(frozen=True, slots=True)
class ChunkingPlan:
    """Plan for chunking documents, including parameters, boundary rules and tokenizer.

    Attributes:
        target_size: Desired chunk size in tokens; segments larger than this are split further.
        overlap_size: Number of tokens each chunk overlaps with the previous one.
        max_size: Hard upper bound on chunk size in tokens.
        boundaries: Boundary rules applied from coarsest to finest when splitting oversized segments.
        tokenizer: Tokenizer used to measure segment sizes.
    """

    target_size: int
    overlap_size: int
    max_size: int
    boundaries: tuple[Boundary, ...] = (
        MarkdownHeadingBoundary(),
        ParagraphBoundary(),
        LineBoundary(),
        BlingfireSentenceBoundary(),
        WordBoundary(),
    )
    tokenizer: TextTokenizer = field(default_factory=HuggingFaceTokenizer)

    def __post_init__(self) -> None:
        """Validate the chunking plan invariants.

        Raises:
            ValueError: If any size parameter is out of range.
        """
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate the parameters of the plan.

        Raises:
            ValueError: If ``target_size`` or ``max_size`` is out of range, ``max_size`` is smaller than
                ``target_size``, or ``overlap_size`` is negative or not smaller than ``target_size``.
        """
        if self.target_size <= 0 or self.target_size > MAX_ALLOWED_TARGET_TOKENS:
            raise ValueError(f'target_size must be > 0 and <= {MAX_ALLOWED_TARGET_TOKENS}')
        if self.max_size <= 0 or self.max_size > MAX_ALLOWED_MAX_TOKENS:
            raise ValueError(f'max_size must be > 0 and <= {MAX_ALLOWED_MAX_TOKENS}')
        if self.max_size < self.target_size:
            raise ValueError('max_size must be greater or equal to target_size')
        if self.overlap_size < 0 or self.overlap_size >= self.target_size:
            raise ValueError('overlap_size must be >= 0 and smaller than target_size')
