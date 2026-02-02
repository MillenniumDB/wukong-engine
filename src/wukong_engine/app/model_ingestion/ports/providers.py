from pathlib import Path
from typing import Protocol

from wukong_engine.core.graph import GraphModel


class GraphModelProvider(Protocol):
    """Provides access to a GraphModel."""

    def get(self, path: Path) -> GraphModel:
        """Get a fully validated GraphModel from the given path.

        Raises:
            GraphModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...
