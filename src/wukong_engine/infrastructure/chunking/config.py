from dataclasses import dataclass, field

from .separators import (
    BlingfireSentenceSeparator,
    LineSeparator,
    MarkdownHeadingSeparator,
    ParagraphSeparator,
    Separator,
    WhitespaceSeparator,
)
from .tokenization import CharacterTokenCounter, TokenCounter

# Constants
MAX_ALLOWED_CHUNK_SIZE = 1000000


# TODO: Better defaults
@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """Configuration for document chunking."""

    target_chunk_size: int = 1000  # TODO: Assign better default
    overlap_size: int = 200  # TODO: Assign better default
    min_chunk_size: int = 0
    max_chunk_size: int = 0
    separators: tuple[Separator, ...] = (
        MarkdownHeadingSeparator(),
        ParagraphSeparator(),
        LineSeparator(),
        BlingfireSentenceSeparator(),
        WhitespaceSeparator(),
    )
    token_counter: TokenCounter = field(default_factory=CharacterTokenCounter)

    def __post_init__(self) -> None:
        """Validate the configuration values."""
        # Validate target size and overlap
        if self.target_chunk_size <= 0 or self.target_chunk_size > MAX_ALLOWED_CHUNK_SIZE:
            raise ValueError(f'target_size must be > 0 and <= {MAX_ALLOWED_CHUNK_SIZE}')
        if self.overlap_size < 0 or self.overlap_size >= self.target_chunk_size:
            raise ValueError('overlap must be >= 0 and smaller than target_size')

        # Validate min and max sizes
        min_chunk_size = self.min_chunk_size or max(self.target_chunk_size // 3, 1)
        max_chunk_size = self.max_chunk_size or min(int(self.target_chunk_size * 1.2), MAX_ALLOWED_CHUNK_SIZE)
        if min_chunk_size <= 0 or min_chunk_size > MAX_ALLOWED_CHUNK_SIZE:
            raise ValueError(f'min_chunk_size must be > 0 and <= {MAX_ALLOWED_CHUNK_SIZE}')
        if min_chunk_size > self.target_chunk_size:
            raise ValueError('min_chunk_size must be smaller or equal to target_size')
        if max_chunk_size <= 0 or max_chunk_size > MAX_ALLOWED_CHUNK_SIZE:
            raise ValueError(f'max_chunk_size must be > 0 and <= {MAX_ALLOWED_CHUNK_SIZE}')
        if max_chunk_size < self.target_chunk_size:
            raise ValueError('max_chunk_size must be greater or equal to target_size')
        if max_chunk_size < min_chunk_size:
            raise ValueError('max_chunk_size must be greater or equal to min_chunk_size')

        # Assign validated values
        object.__setattr__(self, 'min_chunk_size', min_chunk_size)
        object.__setattr__(self, 'max_chunk_size', max_chunk_size)
