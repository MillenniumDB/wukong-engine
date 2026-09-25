"""Port for validating document sources before ingestion."""

from typing import Protocol

from wukong_engine.core.documents.model import DocumentSource


class DocumentSourceValidator(Protocol):
    """Validates a list of document sources."""

    def validate(self, sources: tuple[DocumentSource, ...], data_uri: str) -> None:
        """Validate the given document sources, raising an exception if any are invalid.

        Args:
            sources: Document sources to validate.
            data_uri: Root data location that every source must be contained in.

        Raises:
            ValueError: If any source is invalid (e.g. outside ``data_uri``, missing, of the wrong type, or
                unreadable).
        """
        ...
