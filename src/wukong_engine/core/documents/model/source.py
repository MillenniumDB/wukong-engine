"""Document sources that locate the files to ingest."""

from dataclasses import dataclass

from .values import DocumentSourceMode


@dataclass(frozen=True, slots=True)
class DocumentSource:
    """A document source.

    Attributes:
        root: Path to the file or directory the documents are read from; must not be blank.
        mode: How ``root`` is interpreted (single file, directory, or recursive directory).
    """

    root: str
    mode: DocumentSourceMode

    def __str__(self) -> str:
        """User-friendly string representation of the document source."""
        return f'[{self.mode.value}] {self.root}'

    def __post_init__(self) -> None:
        """Validate document source invariants.

        Raises:
            ValueError: If the root is empty or whitespace-only.
        """
        self._validate_root()

    def _validate_root(self) -> None:
        """Validate that the root is well-formed.

        Raises:
            ValueError: If the root is empty or whitespace-only.
        """
        if not self.root.strip():
            raise ValueError('Root must not be empty.')
