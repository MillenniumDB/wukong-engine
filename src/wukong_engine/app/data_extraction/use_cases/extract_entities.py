from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.app.llm.elements import LLMClient, LLMRequest, LLMResponse
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality
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

    # TODO: Complete
    def execute(self, graph_model: GraphModel) -> None:
        """Execute the entity extraction process."""
        # Setup entity types and associated document collections
        with self._uow as tx:
            entity_types = tuple(graph_model.entity_types.values())
            tx.entities.add_entity_types(et.name for et in entity_types)
            for entity_type in entity_types:
                tx.entities.link_collections_to_entity_type(
                    entity_type.document_collections.get(ContextLevel.DOCUMENT, []),
                    entity_type.name,
                    ContextLevel.DOCUMENT,
                )
                tx.entities.link_collections_to_entity_type(
                    entity_type.document_collections.get(ContextLevel.CHUNK, []),
                    entity_type.name,
                    ContextLevel.CHUNK,
                )

        # Run document-level extractions
        # self._run_document_extractions(graph_model)

        # Run chunk-level extractions
        self._run_chunk_extractions(graph_model)

    # TODO: Implement based on chunk version
    # TODO: Remove Graph Model param after testing
    def _run_document_extractions(self, graph_model: GraphModel) -> None:
        """Run entity extractions."""
        # Materialize pending document extractions for all entity types
        with self._uow as tx:
            tx.extraction.entities.materialize_pending_extractions(ContextLevel.DOCUMENT)

        # TODO: Task
        context_level = ContextLevel.DOCUMENT
        cardinality = Cardinality.SINGLE
        task = EntityExtractionTask(context_level=context_level, cardinality=cardinality)

        # TODO: LLM

        # TODO: LLM concurrency using async instead of threads

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
        with self._uow as tx:
            for extraction in tx.extraction.entities.stream_pending_document_extractions():
                context = extraction.document.context_ref
                tx.entities.bulk_upsert_entities([entity_a, entity_b])
                tx.extraction.entities.link_extracted_entities_to_context([entity_a, entity_b], context)
                tx.extraction.entities.mark_completed_extractions_from_context([entity_type.name], context)

        # Verify results
        with self._uow as tx:
            for link in tx.extraction.entities.stream_entity_document_provenance():
                print(link)

    # TODO: Remove Graph Model param after testing
    # TODO: Implement
    def _run_chunk_extractions(self, graph_model: GraphModel) -> None:
        """Run entity extractions on chunks."""
        # Materialize pending chunk extractions for all entity types
        with self._uow as tx:
            tx.extraction.entities.materialize_pending_extractions(ContextLevel.CHUNK)

        # TODO: Task (do this next)
        context_level = ContextLevel.CHUNK
        cardinality = Cardinality.MULTIPLE
        task = EntityExtractionTask(context_level=context_level, cardinality=cardinality)

        # TODO: Prompt renderer, maybe structured schema here or afterwards

        # TODO: Preparation of requests (later interact with executor)
        pending_extractions = []
        with self._uow as tx:
            pending_extractions = list(tx.extraction.entities.stream_pending_chunk_extractions())

        # TODO: LLM testing
        pending = pending_extractions[0]
        base_prompt = 'Extract stuff from this document... Document:\n\n'
        prompt = base_prompt + pending.chunk.content
        # request = LLMRequest(prompt=prompt)
        # print(request)
        # await self._llm_client.generate(request)

        # TODO: Extraction executor

        # TODO: Test stores (remove later)
        # normalized_pk_a = self._pk_normalizer.normalize(' .( #123- 1|teA& Søren  Noël  key %válue  .)m')
        # normalized_pk_b = self._pk_normalizer.normalize('Test')
        # entity_type = graph_model.entity_types[EntityTypeName('LGUC')]
        # entity_a = Entity(
        #     id=EntityId.from_identity(entity_type.name, normalized_pk_a),
        #     type=entity_type,
        #     properties={
        #         'name': 'LGUC_A',
        #         'summary': 'Define la ley de la gravitación universal y explica su importancia en la física.',
        #         'other': 'Other value',
        #     },
        # )
        # entity_b = Entity(
        #     id=EntityId.from_identity(entity_type.name, normalized_pk_b),
        #     type=entity_type,
        #     properties={
        #         'name': 'LGUC_B',
        #         'summary': 'Define la ley de inercia y explica su importancia en la física.',
        #     },
        # )

        # # Perform extraction
        # with self._uow as tx:
        #     for extraction in tx.extraction.entities.stream_pending_chunk_extractions():
        #         context = extraction.chunk.context_ref
        #         tx.entities.bulk_upsert_entities([entity_a, entity_b])
        #         tx.extraction.entities.link_extracted_entities_to_context([entity_a, entity_b], context)
        #         tx.extraction.entities.mark_completed_extractions_from_context([entity_type.name], context)

        # # Verify results
        # with self._uow as tx:
        #     for link in tx.extraction.entities.stream_entity_chunk_provenance():
        #         print(link)
