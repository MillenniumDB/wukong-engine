"""Implements the engine pipeline."""

import logging

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.data_extraction.use_cases import ExtractEntities, ExtractRelationships
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments
from wukong_engine.app.knowledge_export.use_cases import ExportKnowledge
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetGraphModel
from wukong_engine.app.shared.exceptions import PipelineExecutionError
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.pipeline.model.values import PipelineStep

# Logging
logger = logging.getLogger(__name__)


class GraphConstructionPipeline:
    """Pipeline to build a knowledge graph from unstructured documents."""

    def __init__(
        self,
        app_config: ApplicationConfig,
        uow: UnitOfWork,
        get_document_registry: GetDocumentRegistry,
        get_graph_model: GetGraphModel,
        ingest_documents: IngestDocuments,
        extract_entities: ExtractEntities,
        extract_relationships: ExtractRelationships,
        export_knowledge: ExportKnowledge,
    ) -> None:
        """Initialize the graph construction workflow with its use cases."""
        self._app_config = app_config
        self._uow = uow
        self._get_document_registry = get_document_registry
        self._get_graph_model = get_graph_model
        self._ingest_documents = ingest_documents
        self._extract_entities = extract_entities
        self._extract_relationships = extract_relationships
        self._export_knowledge = export_knowledge

    def _step_to_use_case(
        self,
        step: PipelineStep,
    ) -> IngestDocuments | ExtractEntities | ExtractRelationships | ExportKnowledge:
        """Map a pipeline step to its corresponding use case."""
        match step:
            case PipelineStep.INGEST_DOCUMENTS:
                return self._ingest_documents
            case PipelineStep.EXTRACT_ENTITIES:
                return self._extract_entities
            case PipelineStep.EXTRACT_RELATIONSHIPS:
                return self._extract_relationships
            case PipelineStep.EXPORT_KNOWLEDGE:
                return self._export_knowledge
            case _:
                error = f'No use case found for pipeline step: {step.value}'
                logger.error(error)
                raise PipelineExecutionError(error)

    async def execute(self, workspace: Workspace, data_uri: str, *, should_reset: bool = True) -> None:
        """Execute the WUKONG engine pipeline.

        Orchestrates the entire pipeline, which includes:

        1. Ingest documents
        2. Extract entities
        3. Extract relationships
        4. Export knowledge

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            data_uri: The base URI pointing to the data to be ingested (e.g. a local directory).
            should_reset: If True, clears existing data on each pipeline step. If False, keeps existing data and appends any new results.
        """
        # Initialize the pipeline checkpoints
        with self._uow as tx:
            tx.pipeline.initialize_all_steps()

        # Get document registry and validate document sources
        document_registry = self._get_document_registry.execute(str(workspace.paths.document_registry), data_uri)
        logger.info(
            f'Document Collections obtained successfully from "{workspace.paths.document_registry}"\n\n{document_registry}',
        )

        # Get graph model and validate selected document collections
        graph_model = self._get_graph_model.execute(str(workspace.paths.graph_model))
        unique_collections = set()
        for entity_type in graph_model.entity_types.values():
            for collections in entity_type.document_collections.values():
                unique_collections.update(collections)
        document_registry.validate_collections(frozenset(unique_collections))
        logger.info(f'Graph Model obtained successfully from "{workspace.paths.graph_model}"\n\n{graph_model}')

        # Run pipeline steps
        for step in self._app_config.pipeline.steps:
            # Map the step to its corresponding use case
            use_case = self._step_to_use_case(step)

            # Stop if dependencies have not been completed
            with self._uow as tx:
                if not tx.pipeline.are_dependencies_completed(step):
                    error = (
                        f'Cannot execute {step.value} step because the previous required steps have not been completed'
                    )
                    logger.error(error)
                    raise PipelineExecutionError(error)

            # Reset all steps downstream if the reset flag is present
            if should_reset:
                for dependent_step in step.is_required_by:
                    dependent_use_case = self._step_to_use_case(dependent_step)
                    dependent_use_case.reset()
                use_case.reset()
                with self._uow as tx:
                    tx.pipeline.reset_dependent_checkpoints(step)

            # Check if step has already been completed
            with self._uow as tx:
                completed = tx.pipeline.is_step_completed(step)

            # If not completed, execute the step
            if not completed:
                logger.info(f'Starting {step.value} step...')
                match step:
                    case PipelineStep.INGEST_DOCUMENTS:
                        self._ingest_documents.execute(document_registry)
                    case PipelineStep.EXTRACT_ENTITIES:
                        await self._extract_entities.execute(graph_model)
                    case PipelineStep.EXTRACT_RELATIONSHIPS:
                        await self._extract_relationships.execute(graph_model)
                    case PipelineStep.EXPORT_KNOWLEDGE:
                        self._export_knowledge.execute(graph_model, str(workspace.paths.exports))

                # Stop the pipeline if the step did not fully complete
                completed = False
                with self._uow as tx:
                    completed = tx.pipeline.is_step_completed(step)
                if not completed:
                    logger.info(f'{step.value} step is not fully completed. Stopping the pipeline...')
                    return
                logger.info(f'{step.value} step completed successfully!')
            else:
                logger.info(f'Skipping {step.value} step because it has already been completed...')

    def reset(self) -> None:
        """Reset the pipeline back to its initial state."""
        for step in PipelineStep:
            use_case = self._step_to_use_case(step)
            use_case.reset()
        with self._uow as tx:
            tx.pipeline.clear()
