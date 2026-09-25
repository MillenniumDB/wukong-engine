"""Defines the NormalizedPK value object and its normalization invariants."""

import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class NormalizedPK:
    """A normalized primary key (PK) value for entity and relationship deduplication.

    Current version: v1. Enforced rules:

    1. Non-empty: The normalized PK cannot be an empty string.
    2. Allowed characters: Only lowercase ASCII letters, digits, whitespace, backslashes, and the special
       characters ``/ - + _ # & @ . : ( )`` are allowed.
    3. Normalized whitespace: No leading/trailing whitespace and no consecutive whitespace characters are allowed.
    4. Edge characters: Cannot start or end with whitespace, a backslash, or any of ``/ . : ( )``.

    Attributes:
        value: The normalized primary key string.
    """

    value: str

    # Relevant characters expressed as regex patterns
    ALLOWED_CHARS_PATTERN: ClassVar[str] = r'a-z0-9\s/\\\-+_#&@.:\(\)'
    FORBIDDEN_EDGE_CHARS_PATTERN: ClassVar[str] = r'\s/\\.:\(\)'

    def __post_init__(self) -> None:
        """Validate normalized PK invariants.

        Raises:
            ValueError: If the value breaks any of the enforced normalization rules.
        """
        self._validate_pk()

    def _validate_pk(self) -> None:
        """Validate that the normalized PK value meets expected criteria.

        Raises:
            ValueError: If the value is empty, contains disallowed characters, has non-normalized whitespace, or
                starts or ends with a forbidden edge character.
        """
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
