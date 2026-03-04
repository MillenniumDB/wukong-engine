from pathlib import Path
from typing import Protocol

from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.graph.model import GraphModel


class GraphModelProvider(Protocol):
    """Provides access to a GraphModel."""

    def get(self, path: Path) -> GraphModel:
        """Get a fully validated GraphModel from the given path.

        Raises:
            GraphModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...


class DocumentRegistryProvider(Protocol):
    """Provides access to a DocumentRegistry."""

    def get(self, path: Path) -> DocumentRegistry:
        """Get a fully validated DocumentRegistry from the given path.

        Raises:
            DocumentRegistryLoadError (or a domain-level error) if the registry
            cannot be obtained or is invalid.
        """
        ...
