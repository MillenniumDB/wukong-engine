from dataclasses import dataclass, field

from wukong_engine.app.config.chunking import MAX_ALLOWED_MAX_TOKENS, MAX_ALLOWED_TARGET_TOKENS

from .separators import (
    BlingfireSentenceSeparator,
    LineSeparator,
    MarkdownHeadingSeparator,
    ParagraphSeparator,
    Separator,
    WhitespaceSeparator,
)
from .tokenization import CharacterTokenCounter, TokenCounter


# TODO: Defaults for derived params
@dataclass(frozen=True)
class ChunkingPlan:
    """Plan for chunking documents, including parameters and strategies."""

    target_size: int
    max_size: int
    overlap_size: int
    min_size: int = 50
    boundary_separators: tuple[Separator, ...] = (
        MarkdownHeadingSeparator(),
        ParagraphSeparator(),
        LineSeparator(),
        BlingfireSentenceSeparator(),
        WhitespaceSeparator(),
    )
    token_counter: TokenCounter = field(default_factory=CharacterTokenCounter)

    def __post_init__(self) -> None:
        """Validate the configuration values."""
        # Validate base parameters
        self._validate_base_params()

        # Assign derived parameters
        min_size = self.min_size or max(self.target_size // 3, 1)
        object.__setattr__(self, 'min_size', min_size)

        # Validate derived parameters
        self._validate_derived_params()

    def _validate_base_params(self) -> None:
        """Validate the base parameters of the configuration."""
        if self.target_size <= 0 or self.target_size > MAX_ALLOWED_TARGET_TOKENS:
            raise ValueError(f'target_size must be > 0 and <= {MAX_ALLOWED_TARGET_TOKENS}')
        if self.max_size <= 0 or self.max_size > MAX_ALLOWED_MAX_TOKENS:
            raise ValueError(f'max_size must be > 0 and <= {MAX_ALLOWED_MAX_TOKENS}')
        if self.max_size < self.target_size:
            raise ValueError('max_size must be greater or equal to target_size')
        if self.overlap_size < 0 or self.overlap_size >= self.target_size:
            raise ValueError('overlap_size must be >= 0 and smaller than target_size')

    def _validate_derived_params(self) -> None:
        """Validate the derived parameters of the configuration."""
        if self.min_size <= 0:
            raise ValueError('min_size must be > 0')
        if self.min_size > self.target_size:
            raise ValueError('min_size must be smaller or equal to target_size')
        if self.max_size < self.min_size:
            raise ValueError('max_size must be greater or equal to min_size')
