"""LLM RetryPolicy."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RetryPolicy:
    """Controls retry behavior at the transport level for LLM calls."""

    max_attempts: int = 10
    initial_delay: float = 1.0  # Seconds
    delay_multiplier: float = 2.0  # Seconds
    max_delay: float = 120.0  # Seconds

    def __post_init__(self) -> None:
        """Validate retry policy values at construction time."""
        if self.max_attempts <= 0:
            raise ValueError('max_attempts must be greater than 0')
        if self.initial_delay <= 0:
            raise ValueError('initial_delay must be greater than 0')
        if self.delay_multiplier < 1:
            raise ValueError('delay_multiplier must be greater than or equal to 1')
        if self.max_delay < self.initial_delay:
            raise ValueError('max_delay must be greater than or equal to initial_delay')

        for field_name, value in (
            ('initial_delay', self.initial_delay),
            ('delay_multiplier', self.delay_multiplier),
            ('max_delay', self.max_delay),
        ):
            if not isfinite(value):
                raise ValueError(f'{field_name} must be a finite number')
