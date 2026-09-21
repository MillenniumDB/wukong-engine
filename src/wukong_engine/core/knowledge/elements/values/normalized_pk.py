"""Defines the NormalizedPK value object and its normalization invariants."""

import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class NormalizedPK:
    """A normalized primary key (PK) value for entity and relationship deduplication.

    Current Version: v1
    Enforced Rules:
        1. Non-empty: The normalized PK cannot be an empty string.
        2. Allowed Characters: Only lowercase letters, numbers, spaces, and specific special characters are allowed.
        3. Normalized Whitespace: No leading/trailing whitespace and no consecutive spaces are allowed.
        4. Edge Characters: Cannot start or end with certain special characters.
    """

    value: str

    # Relevant characters expressed as regex patterns
    ALLOWED_CHARS_PATTERN: ClassVar[str] = r'a-z0-9\s/\\\-+_#&@.:\(\)'
    FORBIDDEN_EDGE_CHARS_PATTERN: ClassVar[str] = r'\s/\\.:\(\)'

    def __post_init__(self) -> None:
        """Validate normalized PK invariants."""
        self._validate_pk()

    def _validate_pk(self) -> None:
        """Validate that the normalized PK value meets expected criteria."""
        # Non-empty
        if not self.value:
            raise ValueError('NormalizedPK cannot be empty')

        # Allowed characters
        allowed_pattern = rf'^[{self.ALLOWED_CHARS_PATTERN}]+$'
        if re.fullmatch(allowed_pattern, self.value) is None:
            raise ValueError('NormalizedPK contains disallowed characters')

        # Normalized whitespace
        if re.search(r'^\s|\s$|\s{2,}', self.value):
            raise ValueError('NormalizedPK has non-normalized whitespace')

        # Edge characters
        edge_pattern = rf'^[{self.FORBIDDEN_EDGE_CHARS_PATTERN}]|[{self.FORBIDDEN_EDGE_CHARS_PATTERN}]$'
        if re.search(edge_pattern, self.value):
            raise ValueError('NormalizedPK has forbidden edge characters')

    def __str__(self) -> str:
        """User-friendly string representation of the NormalizedPK."""
        return self.value
