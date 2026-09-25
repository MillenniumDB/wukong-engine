"""Port for loading knowledge models."""

from typing import Protocol

from wukong_engine.core.knowledge.model import KnowledgeModel


class KnowledgeModelProvider(Protocol):
    """Provides access to a KnowledgeModel."""

    def get(self, source_uri: str) -> KnowledgeModel:
        """Get a fully validated KnowledgeModel from the given uri.

        Args:
            source_uri: Location of the knowledge model definition.

        Returns:
            The validated knowledge model.

        Raises:
            OSError: If the model definition cannot be read.
            ValueError: If the model definition is malformed or the resulting model is invalid.
        """
        ...
