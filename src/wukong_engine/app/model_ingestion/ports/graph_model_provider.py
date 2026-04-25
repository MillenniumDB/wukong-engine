from typing import Protocol

from wukong_engine.core.graph.model import GraphModel


class GraphModelProvider(Protocol):
    """Provides access to a GraphModel."""

    def get(self, source_uri: str) -> GraphModel:
        """Get a fully validated GraphModel from the given uri.

        Raises:
            GraphModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...
