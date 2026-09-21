from typing import Protocol

from wukong_engine.core.knowledge.model import KnowledgeModel


class KnowledgeModelProvider(Protocol):
    """Provides access to a KnowledgeModel."""

    def get(self, source_uri: str) -> KnowledgeModel:
        """Get a fully validated KnowledgeModel from the given uri.

        Raises:
            KnowledgeModelLoadError (or a domain-level error) if the model
            cannot be obtained or is invalid.
        """
        ...
