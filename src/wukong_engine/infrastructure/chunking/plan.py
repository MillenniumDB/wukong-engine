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


@dataclass(frozen=True)
class ChunkingPlan:
    """Plan for chunking documents, including parameters, boundary rules and tokenizer."""

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
        """Validate the chunking plan invariants."""
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate the parameters of the plan."""
        if self.target_size <= 0 or self.target_size > MAX_ALLOWED_TARGET_TOKENS:
            raise ValueError(f'target_size must be > 0 and <= {MAX_ALLOWED_TARGET_TOKENS}')
        if self.max_size <= 0 or self.max_size > MAX_ALLOWED_MAX_TOKENS:
            raise ValueError(f'max_size must be > 0 and <= {MAX_ALLOWED_MAX_TOKENS}')
        if self.max_size < self.target_size:
            raise ValueError('max_size must be greater or equal to target_size')
        if self.overlap_size < 0 or self.overlap_size >= self.target_size:
            raise ValueError('overlap_size must be >= 0 and smaller than target_size')
