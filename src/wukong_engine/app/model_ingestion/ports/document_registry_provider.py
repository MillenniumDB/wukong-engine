"""Port for loading document registries."""

from typing import Protocol

from wukong_engine.core.documents.model import DocumentRegistry


class DocumentRegistryProvider(Protocol):
    """Provides access to a DocumentRegistry."""

    def get(self, source_uri: str, data_uri: str) -> DocumentRegistry:
        """Load a document registry from the given URI, considering a base data URI for resolving paths.

        Args:
            source_uri: Location of the document registry definition.
            data_uri: Base data location that relative source roots are resolved against.

        Returns:
            The document registry with every source root resolved against ``data_uri``.

        Raises:
            OSError: If the registry definition cannot be read.
            ValueError: If the registry definition is malformed or invalid.
        """
        ...
