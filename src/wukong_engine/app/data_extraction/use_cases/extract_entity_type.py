from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.extraction.elements import EntityExtractionRequest
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality, ContextLevel
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.elements.values import EntityId, RelationshipId
from wukong_engine.core.graph.model import EntityType
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipIdentityPolicy, RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId


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
                'summary': 'Define la ley de la gravitación universal y explica su importancia en la física.',
                'other': 'Other value',
            },
        )
        entity_b = Entity(
            id=EntityId.from_identity(entity_type.name, normalized_pk_b),
            type=entity_type,
            properties={
                'name': 'LGUC_B',
                'summary': 'Define la ley de inercia y explica su importancia en la física.',
            },
        )

        # Setup extraction
        with self._uow as tx:
            tx.entities.add_types([entity_type])
            tx.entities.link_collections_to_type(
                collections=collections,
                entity_type=entity_type,
                context_level=context_level,
            )
            tx.extraction.entities.materialize_pending_extractions()
            for pending in tx.extraction.entities.stream_pending_extractions():
                print(pending)

        # Perform extraction
        test_document = Document(
            id=DocumentId(
                instance=InstanceId.from_hex('019e04730eb67057aaed440ccafbb781'),
                content=ContentHash.from_hex('5ad98f6cf287e51d9d4063fc954672dd'),
            ),
            source_uri='/home/imfd/Desktop/knowledge-graphs/wukong-engine/data/example/docs/LGUC/fake_lguc.txt',
        )
        with self._uow as tx:
            tx.entities.bulk_upsert([entity_a, entity_b])
            tx.extraction.entities.link_extracted_entities_to_document([entity_a, entity_b], test_document)
            tx.extraction.entities.mark_completed_extractions_from_document([entity_type.name], test_document)

        # Verify results
        with self._uow as tx:
            for link in tx.extraction.entities.stream_entity_document_links():
                print(link)
