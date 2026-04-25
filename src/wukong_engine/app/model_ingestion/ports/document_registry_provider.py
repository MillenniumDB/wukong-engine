from typing import Protocol

from wukong_engine.core.documents.model import DocumentRegistry


class DocumentRegistryProvider(Protocol):
    """Provides access to a DocumentRegistry."""

    def get(self, source_uri: str) -> DocumentRegistry:
        """Get a fully validated DocumentRegistry from the given uri.

        Raises:
            DocumentRegistryLoadError (or a domain-level error) if the registry
            cannot be obtained or is invalid.
        """
        ...
