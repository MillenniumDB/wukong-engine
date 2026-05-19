import logging
from dataclasses import dataclass

# Logging
logger = logging.getLogger(__name__)

# Constants
MIN_RECOMMENDED_TARGET_TOKENS = 100
MAX_RECOMMENDED_TARGET_TOKENS = 2000
MAX_ALLOWED_TARGET_TOKENS = 4096
MAX_ALLOWED_MAX_TOKENS = 8192


@dataclass(frozen=True)
class ChunkingConfig:
    """Chunking configuration."""

    target_tokens: int = 800
    max_tokens: int | None = None
    overlap_tokens: int | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the chunking configuration."""
        return (
            f'Target Tokens: {self.target_tokens}\nMax Tokens: {self.max_tokens}\nOverlap Tokens: {self.overlap_tokens}'
        )

    def __post_init__(self) -> None:
        """Validate chunking configuration invariants."""
        # Validate base parameters
        self._validate_base_params()

        # Assign derived parameters
        derived_max = min(int(self.target_tokens * 1.5), MAX_ALLOWED_MAX_TOKENS)
        derived_overlap = min(
            max(20, int(self.target_tokens * 0.15)),
            self.target_tokens // 3,
            200,
            MAX_ALLOWED_TARGET_TOKENS // 3,
        )
        max_tokens = self.max_tokens if self.max_tokens is not None else derived_max
        overlap_tokens = self.overlap_tokens if self.overlap_tokens is not None else derived_overlap
        object.__setattr__(self, 'max_tokens', max_tokens)
        object.__setattr__(self, 'overlap_tokens', overlap_tokens)

        # Validate derived parameters
        self._validate_derived_params()

    def _validate_base_params(self) -> None:
        """Validate the base parameters of the configuration."""
        if self.target_tokens <= 0 or self.target_tokens > MAX_ALLOWED_TARGET_TOKENS:
            raise ValueError(f'target_tokens must be > 0 and <= {MAX_ALLOWED_TARGET_TOKENS}')
        if self.target_tokens < MIN_RECOMMENDED_TARGET_TOKENS or self.target_tokens > MAX_RECOMMENDED_TARGET_TOKENS:
            logger.warning(
                f'{self.target_tokens} target tokens is outside the recommended range of '
                f'[{MIN_RECOMMENDED_TARGET_TOKENS}, {MAX_RECOMMENDED_TARGET_TOKENS}] tokens. Consider adjusting for better performance.',
            )

    def _validate_derived_params(self) -> None:
        """Validate the derived parameters of the configuration."""
        if self.max_tokens is None or self.overlap_tokens is None:
            raise ValueError('max_tokens and overlap_tokens must be set after initialization')
        if self.max_tokens <= 0 or self.max_tokens > MAX_ALLOWED_MAX_TOKENS:
            raise ValueError(f'max_tokens must be > 0 and <= {MAX_ALLOWED_MAX_TOKENS}')
        if self.max_tokens < self.target_tokens:
            raise ValueError('max_tokens must be greater or equal to target_tokens')
        if self.overlap_tokens < 0 or self.overlap_tokens >= self.target_tokens:
            raise ValueError('overlap_tokens must be >= 0 and smaller than target_tokens')
