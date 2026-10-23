"""Use case for loading the knowledge model."""

import logging

from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.app.model_ingestion.ports import KnowledgeModelProvider
from wukong_engine.core.knowledge.model import KnowledgeModel

# Logging
logger = logging.getLogger(__name__)


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
            The validated knowledge model. Enabled types that can never be extracted are reported with a warning.

        Raises:
            ModelIngestionError: If the knowledge model can't be read or is invalid.
        """
        try:
            knowledge_model = self._provider.get(knowledge_model_uri)
        except Exception as exc:
            error = f'Failed to load the knowledge model from "{knowledge_model_uri}": {exc}'
            logger.error(error)
            raise ModelIngestionError(error) from exc

        self._warn_about_unextractable_types(knowledge_model)
        return knowledge_model

    @staticmethod
    def _warn_about_unextractable_types(knowledge_model: KnowledgeModel) -> None:
        """Warn about enabled entity and relationship types that no extraction job can ever be created for.

        Args:
            knowledge_model: Knowledge model whose enabled types are checked.
        """
        for entity_type in knowledge_model.active_entity_types.values():
            if not any(entity_type.document_collections.values()):
                logger.warning(f'Entity type "{entity_type.name}" lists no document collections and is never extracted')

        projection = knowledge_model.extraction_config.relationship_projection
        for relationship_type in knowledge_model.relationship_types.values():
            is_enabled = projection is None or relationship_type.name in projection
            if is_enabled and not knowledge_model.active_endpoints(relationship_type):
                logger.warning(
                    f'Relationship type "{relationship_type.name}" has no endpoint between enabled entity types and '
                    f'is never extracted',
                )
