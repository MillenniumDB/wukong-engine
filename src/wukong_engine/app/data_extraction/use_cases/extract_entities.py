import logging

from wukong_engine.app.data_extraction.services import EntityExtractionRequestBuilder, ExtractionExecutor
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.graph.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId

# Logging
logger = logging.getLogger(__name__)


# TODO: Implement
# TODO: Activate and complete Document-level extraction
class ExtractEntities:
    """Extract entities from documents."""

    def __init__(
        self,
        uow: UnitOfWork,
        request_builder: EntityExtractionRequestBuilder,
        executor: ExtractionExecutor,
    ) -> None:
        """Initialize the use case with necessary dependencies."""
        self._uow = uow
        self._request_builder = request_builder
        self._executor = executor

    async def execute(self, graph_model: GraphModel) -> None:
        """Execute the entity extraction process."""
        # Setup entity types and associated document collections
        with self._uow as tx:
            entity_types = tuple(graph_model.active_entity_types.values())
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

        # TODO: Run document-level extractions
        # await self._run_extractions(ContextLevel.DOCUMENT, graph_model)

        # Run chunk-level extractions
        await self._run_extractions(ContextLevel.CHUNK, graph_model)

    async def _run_extractions(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run entity extractions."""
        # Materialize pending extractions for all entity types
        with self._uow as tx:
            tx.extraction.entities.materialize_pending_extractions(context_level)

        # TODO: Preparation of jobs for executor
        pending_extractions = []
        with self._uow as tx:
            if context_level == ContextLevel.DOCUMENT:
                pending_extractions = list(tx.extraction.entities.stream_pending_document_extractions())
            elif context_level == ContextLevel.CHUNK:
                pending_extractions = list(tx.extraction.entities.stream_pending_chunk_extractions())
        jobs = pending_extractions
        job = jobs[3]

        # TODO: Build extraction request for each job
        request = self._request_builder.build(job, graph_model)
        if request is None:
            return

        # TODO: Extraction executor
        result = await self._executor.execute(request)
        # async for result in self._executor.execute_many(jobs):
        #     # if isinstance(result, ExtractionSuccess):
        #     #     ...
        #     # else:
        #     #     ...
        #     pass

        # TODO: Validation of data -> Discard invalid ones, keep the rest
        # TODO: Normalization/Mapping to domain instances, assign defaults, apply graph model parameters

        # TODO: Persist results (use the Test stores commented code below as reference)
        # TODO: Each result should be processed individually and stored in the DB
        # async for result in executor.execute_many(extractions):
        #     entity_repository.save(result.entities)
        #     extraction_repository.mark_completed(...)

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
