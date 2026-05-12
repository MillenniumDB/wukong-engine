from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality, ContextLevel
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.graph.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId


class ExtractEntities:
    """Extract entities from documents."""

    def __init__(self, uow: UnitOfWork, llm_client: LLMClient, pk_normalizer: PKNormalizer) -> None:
        """Initialize the use case with necessary dependencies."""
        self._uow = uow
        self._llm_client = llm_client
        self._pk_normalizer = pk_normalizer

    def execute(self, graph_model: GraphModel) -> None:
        """Execute the entity extraction process."""
        # Setup entity types and associated document collections
        with self._uow as tx:
            entity_types = tuple(graph_model.entity_types.values())
            tx.entities.add_types(et.name for et in entity_types)
            for entity_type in entity_types:
                tx.entities.link_collections_to_type(
                    entity_type.document_collections.get(ContextLevel.DOCUMENT, []),
                    entity_type.name,
                    ContextLevel.DOCUMENT,
                )
                tx.entities.link_collections_to_type(
                    entity_type.document_collections.get(ContextLevel.CHUNK, []),
                    entity_type.name,
                    ContextLevel.CHUNK,
                )

        # Materialize pending extractions for all entity types
        with self._uow as tx:
            tx.extraction.entities.materialize_pending_extractions()

        # TODO: Context Level + Tasks
        context_level = ContextLevel.DOCUMENT
        cardinality = Cardinality.SINGLE
        task = EntityExtractionTask(context_level=context_level, cardinality=cardinality)

        # TODO: LLM Concurrency using async instead of threads

        # TODO: Test stores
        normalized_pk_a = self._pk_normalizer.normalize(' .( #123- 1|teA& Søren  Noël  key %válue  .)m')
        normalized_pk_b = self._pk_normalizer.normalize('Test')
        entity_type = graph_model.entity_types[EntityTypeName('LGUC')]
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
