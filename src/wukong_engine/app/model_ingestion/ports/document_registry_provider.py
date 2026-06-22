from typing import Protocol

from wukong_engine.core.documents.model import DocumentRegistry


class DocumentRegistryProvider(Protocol):
    """Provides access to a DocumentRegistry."""

    def get(self, source_uri: str, data_uri: str) -> DocumentRegistry:
        """Load a document registry from a local JSON file, considering a base data uri for resolving paths."""
        ...
