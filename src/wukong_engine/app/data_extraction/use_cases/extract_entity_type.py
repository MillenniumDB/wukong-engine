from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.extraction.elements import EntityExtractionRequest
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality, ContextLevel
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.elements.values import EntityId, RelationshipId
from wukong_engine.core.graph.model import EntityType
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipIdentityPolicy, RelationshipTypeName


# TODO: Refactor
class ExtractEntityType:
    """Extract entities of a given type."""

    def __init__(
        self,
        uow: UnitOfWork,
        llm_client: LLMClient,
        pk_normalizer: PKNormalizer,
    ) -> None:
        """Initialize the use case with necessary dependencies."""
        self._uow = uow
        self._llm_client = llm_client
        self._pk_normalizer = pk_normalizer

    def execute(self, entity_type: EntityType, document_registry: DocumentRegistry) -> None:
        """Execute the entity extraction process for the given entity type."""
        # TODO: Params: change later
        context_level = ContextLevel.DOCUMENT
        cardinality = Cardinality.SINGLE
        task = EntityExtractionTask(context_level=context_level, cardinality=cardinality)
        collections = document_registry.collections.values()

        # TODO: Execution - refactor to use collections instead of entity type
        # TODO: LLM Concurrency using async instead of threads

        # TODO: Test runtime entities
        normalized_pk_a = self._pk_normalizer.normalize(' .( #123- 1|teA& Søren  Noël  key %válue  .)m')
        normalized_pk_b = self._pk_normalizer.normalize('Test')
        entity_a = Entity(
            id=EntityId.from_identity(entity_type.name, normalized_pk_a),
            type=entity_type,
            properties={
                'name': 'LGUC_A',
                'Desc': 'Define la ley de la gravitación universal y explica su importancia en la física.',
            },
        )
        entity_b = Entity(
            id=EntityId.from_identity(entity_type.name, normalized_pk_b),
            type=entity_type,
            properties={
                'name': 'LGUC_B',
                'Desc': 'Define la ley de inercia y explica su importancia en la física.',
            },
        )
        with self._uow as tx:
            tx.entities.add_types([entity_type])
            tx.entities.link_collections_to_type(
                collections=collections,
                entity_type=entity_type,
                context_level=context_level,
            )
            tx.entities.bulk_upsert([entity_a, entity_b])
        with self._uow as tx:
            for e in tx.entities.stream_by_type(entity_type):
                print(e.id, e.properties)

        # TODO: Insertion
        # with uow as tx:
        #     entity_ids = tx.entities.bulk_upsert(result.entities)
        #     tx.extractions.link_entities(result.document_id, entity_ids)
        #     tx.extractions.mark_types_extracted(result.document_id, result.entity_types)
