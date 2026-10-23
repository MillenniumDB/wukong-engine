"""Implements the engine pipeline."""

import logging

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.data_extraction.use_cases import ExtractEntities, ExtractRelationships
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments
from wukong_engine.app.knowledge_export.use_cases import ExportKnowledge
from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetKnowledgeModel
from wukong_engine.app.shared.exceptions import PipelineExecutionError
from wukong_engine.app.staging.ports import InputSnapshotStore, UnitOfWork
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.pipeline.model.values import (
    InputSnapshot,
    PipelineCheckpoint,
    PipelineCheckpointStatus,
    PipelineStep,
)

# Logging
logger = logging.getLogger(__name__)

# First step consuming each input snapshot: it is taken when that step runs, and kept until that step is reset
SNAPSHOT_STEPS: dict[InputSnapshot, PipelineStep] = {
    InputSnapshot.DOCUMENT_REGISTRY: PipelineStep.INGEST_DOCUMENTS,
    InputSnapshot.KNOWLEDGE_MODEL: PipelineStep.EXTRACT_ENTITIES,
}


class KnowledgeConstructionPipeline:
    """Pipeline to build a knowledge base from unstructured documents."""

    def __init__(
        self,
        app_config: ApplicationConfig,
        uow: UnitOfWork,
        input_snapshots: InputSnapshotStore,
        get_document_registry: GetDocumentRegistry,
        get_knowledge_model: GetKnowledgeModel,
        ingest_documents: IngestDocuments,
        extract_entities: ExtractEntities,
        extract_relationships: ExtractRelationships,
        export_knowledge: ExportKnowledge,
    ) -> None:
        """Initialize the knowledge construction workflow with its use cases.

        Args:
            app_config: Application configuration; its pipeline settings select which steps run.
            uow: Unit of work used to read and update pipeline checkpoints.
            input_snapshots: Store of the snapshots of the input files and chunking settings the steps use.
            get_document_registry: Use case that loads and validates the document registry.
            get_knowledge_model: Use case that loads the knowledge model.
            ingest_documents: Use case for the document ingestion step.
            extract_entities: Use case for the entity extraction step.
            extract_relationships: Use case for the relationship extraction step.
            export_knowledge: Use case for the knowledge export step.
        """
        self._app_config = app_config
        self._uow = uow
        self._input_snapshots = input_snapshots
        self._get_document_registry = get_document_registry
        self._get_knowledge_model = get_knowledge_model
        self._ingest_documents = ingest_documents
        self._extract_entities = extract_entities
        self._extract_relationships = extract_relationships
        self._export_knowledge = export_knowledge

    async def _reset_step(self, step: PipelineStep) -> None:
        """Reset the state of a pipeline step through its use case.

        Args:
            step: Pipeline step to reset.

        Raises:
            PipelineExecutionError: If no use case is registered for the step.
        """
        match step:
            case PipelineStep.INGEST_DOCUMENTS:
                self._ingest_documents.reset()
            case PipelineStep.EXTRACT_ENTITIES:
                await self._extract_entities.reset()
            case PipelineStep.EXTRACT_RELATIONSHIPS:
                await self._extract_relationships.reset()
            case PipelineStep.EXPORT_KNOWLEDGE:
                self._export_knowledge.reset()
            case _:
                error = f'No use case found for pipeline step: {step.value}'
                logger.error(error)
                raise PipelineExecutionError(error)

    def _validate_plan(self, *, should_reset: bool) -> None:
        """Check that every configured step will find its required steps completed when it runs.

        A required step is satisfied if it runs earlier in the plan, or if it is already completed and no earlier
        step resets it.

        Args:
            should_reset: Whether each step resets itself and every step that depends on it before running.

        Raises:
            PipelineExecutionError: If a step's required steps are neither run before it nor left completed.
        """
        with self._uow as tx:
            completed = {step for step in PipelineStep if tx.pipeline.is_step_completed(step)}

        planned: set[PipelineStep] = set()
        reset: set[PipelineStep] = set()
        for step in self._app_config.pipeline.steps:
            missing = sorted(
                (required for required in step.depends_on if required not in planned and required not in completed),
                key=lambda required: required.value,
            )
            if missing:
                reasons = [
                    f'{required.value} ({"reset by an earlier step" if required in reset else "not completed"})'
                    for required in missing
                ]
                error = (
                    f'Cannot execute {step.value} step because required steps that are not part of this run would be '
                    f'missing: {", ".join(reasons)}. Nothing was run or reset.'
                )
                logger.error(error)
                raise PipelineExecutionError(error)

            planned.add(step)
            if should_reset:
                reset |= {step, *step.is_required_by} & completed
                completed -= {step, *step.is_required_by}

    def _planned_resets(self, *, should_reset: bool) -> set[PipelineStep]:
        """Get the steps this run resets, which are the configured steps and every step depending on them.

        Args:
            should_reset: Whether each step resets itself and every step that depends on it before running.

        Returns:
            The steps that will be reset, empty if nothing is reset.
        """
        if not should_reset:
            return set()
        return {reset for step in self._app_config.pipeline.steps for reset in (step, *step.is_required_by)}

    def _will_run(self, step: PipelineStep, resets: set[PipelineStep]) -> bool:
        """Check whether a step runs in this execution, which it does if enabled and reset or not yet completed.

        Args:
            step: Step to check.
            resets: Steps this run resets.

        Returns:
            True if the step will run, False otherwise.
        """
        if step not in self._app_config.pipeline.steps:
            return False
        with self._uow as tx:
            return step in resets or not tx.pipeline.is_step_completed(step)

    def _resolve_input(self, snapshot: InputSnapshot, source_uri: str, resets: set[PipelineStep]) -> str:
        """Resolve where to read an input file from, taking or discarding its snapshot as needed.

        A snapshot that the reset of its step makes stale is discarded. Without a snapshot, the file itself is read,
        and snapshotted if its step runs now. With one, the snapshot is read instead, and a warning is logged if the
        file changed since it was taken.

        Args:
            snapshot: Input file to resolve.
            source_uri: Location of the input file in the workspace.
            resets: Steps this run resets.

        Returns:
            The location to read the input from.
        """
        step = SNAPSHOT_STEPS[snapshot]
        if step in resets:
            self._input_snapshots.discard(snapshot)

        if not self._input_snapshots.exists(snapshot):
            if self._will_run(step, resets):
                self._input_snapshots.save(snapshot, source_uri)
            return source_uri

        if not self._input_snapshots.matches(snapshot, source_uri):
            logger.warning(
                f'"{source_uri}" changed since it was used to {step.value.lower().replace("_", " ")}. This run keeps '
                f'using the version that step used; reset the {step.value} step to apply the changes.',
            )
        return self._input_snapshots.uri(snapshot)

    def _resolve_chunking(self, resets: set[PipelineStep]) -> ChunkingConfig:
        """Resolve the chunking settings to ingest documents with, taking or discarding their snapshot as needed.

        Args:
            resets: Steps this run resets.

        Returns:
            The settings documents were ingested with, or the configured ones if there are none yet.
        """
        if PipelineStep.INGEST_DOCUMENTS in resets:
            self._input_snapshots.discard_chunking()

        configured = self._app_config.chunking
        ingested = self._input_snapshots.load_chunking()
        if ingested is None:
            if self._will_run(PipelineStep.INGEST_DOCUMENTS, resets):
                self._input_snapshots.save_chunking(configured)
            return configured

        if ingested != configured:
            logger.warning(
                'The [chunking] settings changed since documents were ingested. This run keeps using the ingested '
                f'ones; reset the {PipelineStep.INGEST_DOCUMENTS.value} step to apply the changes.',
            )
        return ingested

    def _load_inputs(
        self,
        workspace: Workspace,
        data_uri: str,
        resets: set[PipelineStep],
    ) -> tuple[DocumentRegistry, KnowledgeModel, ChunkingConfig]:
        """Load the document registry, knowledge model and chunking settings this run uses.

        Args:
            workspace: Workspace holding the input files.
            data_uri: Data location the registry's sources are resolved against.
            resets: Steps this run resets.

        Returns:
            The document registry, the knowledge model and the chunking settings, each from its snapshot if one is
            kept, otherwise from the workspace or configuration.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, or an enabled entity
                type references unknown document collections.
        """
        # Get document registry, validating its sources only if documents are going to be ingested from them
        registry_uri = self._resolve_input(
            InputSnapshot.DOCUMENT_REGISTRY,
            str(workspace.paths.document_registry),
            resets,
        )
        document_registry = self._get_document_registry.execute(
            registry_uri,
            data_uri,
            validate_sources=self._will_run(PipelineStep.INGEST_DOCUMENTS, resets),
        )
        logger.info(f'Document Collections obtained successfully from "{registry_uri}"\n\n{document_registry}')

        # Get knowledge model and validate the document collections of the enabled entity types
        model_uri = self._resolve_input(InputSnapshot.KNOWLEDGE_MODEL, str(workspace.paths.knowledge_model), resets)
        knowledge_model = self._get_knowledge_model.execute(model_uri)
        unique_collections = set()
        for entity_type in knowledge_model.active_entity_types.values():
            for collections in entity_type.document_collections.values():
                unique_collections.update(collections)
        try:
            document_registry.validate_collections(frozenset(unique_collections))
        except ValueError as exc:
            error = f'Invalid knowledge model "{model_uri}": {exc}'
            logger.error(error)
            raise ModelIngestionError(error) from exc
        logger.info(f'Knowledge Model obtained successfully from "{model_uri}"\n\n{knowledge_model}')

        return document_registry, knowledge_model, self._resolve_chunking(resets)

    async def execute(self, workspace: Workspace, data_uri: str, *, should_reset: bool = True) -> None:
        """Execute the WUKONG engine pipeline.

        Loads the document registry and knowledge model, then runs the steps configured in
        ``app_config.pipeline.steps``, which may include:

        1. Ingest documents
        2. Extract entities
        3. Extract relationships
        4. Export knowledge

        Steps whose checkpoint is already completed are skipped. The pipeline stops early (without raising) if a step
        finishes without being fully completed.

        The document registry and chunking settings are snapshotted when documents are first ingested, and the
        knowledge model when entities are first extracted. Later runs keep using the snapshots, even if the files or
        settings change, until the step that took them is reset.

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            data_uri: The base URI pointing to the data to be ingested (e.g. a local directory).
            should_reset: If True, resets each step and every step that depends on it before running it. If False,
                keeps existing data and appends any new results.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, or an enabled entity
                type references unknown document collections.
            PipelineExecutionError: If a step has no use case or its required steps have not been completed.
        """
        # Initialize the pipeline checkpoints
        with self._uow as tx:
            tx.pipeline.initialize_all_steps()

        # Check the whole plan before any input snapshot is taken, or any step runs or resets data
        self._validate_plan(should_reset=should_reset)

        # Load the inputs from their snapshots, or from the workspace and configuration
        document_registry, knowledge_model, chunking = self._load_inputs(
            workspace,
            data_uri,
            self._planned_resets(should_reset=should_reset),
        )

        # Run pipeline steps
        for step in self._app_config.pipeline.steps:
            # Reset all steps downstream if the reset flag is present
            if should_reset:
                for dependent_step in step.is_required_by:
                    await self._reset_step(dependent_step)
                await self._reset_step(step)
                with self._uow as tx:
                    tx.pipeline.reset_dependent_checkpoints(step)

            # Check if step has already been completed
            with self._uow as tx:
                tx.pipeline.set_checkpoint_status(
                    PipelineCheckpoint.KNOWLEDGE_EXPORTED,
                    PipelineCheckpointStatus.PENDING,
                )  # Reset the knowledge export checkpoint to be able to export every run
                completed = tx.pipeline.is_step_completed(step)

            # If not completed, execute the step
            if not completed:
                logger.info(f'Starting {step.value} step...')
                match step:
                    case PipelineStep.INGEST_DOCUMENTS:
                        self._ingest_documents.execute(document_registry, data_uri, chunking)
                    case PipelineStep.EXTRACT_ENTITIES:
                        await self._extract_entities.execute(knowledge_model)
                    case PipelineStep.EXTRACT_RELATIONSHIPS:
                        await self._extract_relationships.execute(knowledge_model)
                    case PipelineStep.EXPORT_KNOWLEDGE:
                        self._export_knowledge.execute(knowledge_model)

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

    async def reset(self) -> None:
        """Reset the pipeline back to its initial state."""
        for step in PipelineStep:
            await self._reset_step(step)
        with self._uow as tx:
            tx.pipeline.clear()
        self._input_snapshots.clear()
