"""Use case for loading the knowledge model."""

from wukong_engine.app.model_ingestion.ports import KnowledgeModelProvider
from wukong_engine.core.knowledge.model import KnowledgeModel


class GetKnowledgeModel:
    """Use case for retrieving the knowledge model from a specified URI."""

    def __init__(self, provider: KnowledgeModelProvider) -> None:
        """Initialize the use case with its dependencies.

        Args:
            provider: Provider used to load the knowledge model.
        """
        self._provider = provider

    def execute(self, knowledge_model_uri: str) -> KnowledgeModel:
        """Retrieve the knowledge model from the specified URI.

        Args:
            knowledge_model_uri: Location of the knowledge model definition.

        Returns:
            The validated knowledge model.
        """
        return self._provider.get(knowledge_model_uri)
