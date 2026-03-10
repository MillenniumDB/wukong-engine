from pathlib import Path
from typing import Protocol

from wukong_engine.core.documents.model import DocumentRegistry


class DocumentRegistryProvider(Protocol):
    """Provides access to a DocumentRegistry."""

    def get(self, path: Path) -> DocumentRegistry:
        """Get a fully validated DocumentRegistry from the given path.

        Raises:
            DocumentRegistryLoadError (or a domain-level error) if the registry
            cannot be obtained or is invalid.
        """
        ...
