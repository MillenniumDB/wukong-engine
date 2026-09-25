"""Validated name for document collections."""

import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class DocumentCollectionName:
    """Document collection name.

    Attributes:
        value: The name: 1 to 64 characters from letters, digits, ``.``, ``_`` and ``-``, starting with a letter or
            digit.
    """

    value: str

    # Validation parameters
    _PATTERN: ClassVar[str] = r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$'

    def __post_init__(self) -> None:
        """Validate document collection name invariants.

        Raises:
            ValueError: If the value doesn't match the allowed name pattern.
        """
        if not re.match(self._PATTERN, self.value):
            raise ValueError(
                f'Invalid {self.__class__.__name__}: "{self.value}". Must match regex pattern: {self._PATTERN}',
            )

    def __str__(self) -> str:
        """User-friendly representation of the document collection name."""
        return self.value

    def __repr__(self) -> str:
        """Developer-friendly representation of the document collection name."""
        return self.value
