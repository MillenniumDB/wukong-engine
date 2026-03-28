from typing import Protocol

from wukong_engine.core.documents.model import DocumentSource


class DocumentSourceValidator(Protocol):
    """Validates a list of document sources."""

    def validate(self, sources: tuple[DocumentSource, ...]) -> None:
        """Validate the given document sources, raising an exception if any are invalid."""
        ...
