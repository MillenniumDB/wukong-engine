"""Implements the engine pipeline."""

import logging
from dataclasses import dataclass

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

from .pipeline_plan import InputPlan, InputSource, PipelinePlan, StepAction

# Logging
logger = logging.getLogger(__name__)

# First step consuming each input snapshot: it is taken when that step runs, and kept until that step is reset
SNAPSHOT_STEPS: dict[InputSnapshot, PipelineStep] = {
    InputSnapshot.DOCUMENT_REGISTRY: PipelineStep.INGEST_DOCUMENTS,
    InputSnapshot.KNOWLEDGE_MODEL: PipelineStep.EXTRACT_ENTITIES,
}

# Name of the chunking settings in plans and warnings, which are snapshotted along with the document registry
CHUNKING_INPUT_NAME = '[chunking] settings'


@dataclass(frozen=True, slots=True)
class _PreparedRun:
    """Plan of a run along with the inputs it was checked against.

    Attributes:
        plan: What the run does with each step and where it reads its inputs from.
        resets: Steps the run resets.
        sources: Where each snapshotted input file is read from.
        chunking_source: Where the chunking settings are read from.
        document_registry: Document registry the run uses.
        knowledge_model: Knowledge model the run uses.
        chunking: Chunking settings documents are ingested with.
    """

    plan: PipelinePlan
    resets: set[PipelineStep]
    sources: dict[InputSnapshot, InputSource]
    chunking_source: InputSource
    document_registry: DocumentRegistry
    knowledge_model: KnowledgeModel
    chunking: ChunkingConfig


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

    def _step_actions(self, resets: set[PipelineStep]) -> dict[PipelineStep, StepAction]:
        """Get what this run does with each pipeline step.

        Args:
            resets: Steps this run resets.

        Returns:
            The action taken on each step, in pipeline order.
        """
        with self._uow as tx:
            completed = {step for step in PipelineStep if tx.pipeline.is_step_completed(step)}

        actions: dict[PipelineStep, StepAction] = {}
        for step in PipelineStep:
            if self._app_config.pipeline.is_active(step):
                if step in resets:
                    actions[step] = StepAction.RESET_AND_RUN
                # Knowledge is exported on every run, as its checkpoint is set back to pending before running steps
                elif step in completed and step is not PipelineStep.EXPORT_KNOWLEDGE:
                    actions[step] = StepAction.SKIP
                else:
                    actions[step] = StepAction.RUN
            elif step in resets:
                actions[step] = StepAction.RESET
            elif step in completed:
                actions[step] = StepAction.KEEP
            else:
                actions[step] = StepAction.NOT_RUN
        return actions

    def _input_source(
        self,
        snapshot: InputSnapshot,
        source_uri: str,
        actions: dict[PipelineStep, StepAction],
        resets: set[PipelineStep],
    ) -> InputSource:
        """Get where this run reads an input file from.

        A snapshot is used unless the reset of its step makes it stale. Without one, the file itself is read, and
        snapshotted if its step runs now.

        Args:
            snapshot: Input file to resolve.
            source_uri: Location of the input file in the workspace.
            actions: Action taken on each step.
            resets: Steps this run resets.

        Returns:
            Where the input file is read from.
        """
        step = SNAPSHOT_STEPS[snapshot]
        if step not in resets and self._input_snapshots.exists(snapshot):
            if self._input_snapshots.matches(snapshot, source_uri):
                return InputSource.SNAPSHOT
            return InputSource.OUTDATED_SNAPSHOT
        return InputSource.NEW_SNAPSHOT if actions[step].runs else InputSource.CURRENT

    def _resolve_chunking(
        self,
        actions: dict[PipelineStep, StepAction],
        resets: set[PipelineStep],
    ) -> tuple[ChunkingConfig, InputSource]:
        """Resolve the chunking settings to ingest documents with.

        Args:
            actions: Action taken on each step.
            resets: Steps this run resets.

        Returns:
            The settings documents were ingested with, or the configured ones if there are none yet or ingestion is
            reset, and where they are read from.
        """
        configured = self._app_config.chunking
        ingested = None if PipelineStep.INGEST_DOCUMENTS in resets else self._input_snapshots.load_chunking()
        if ingested is None:
            runs = actions[PipelineStep.INGEST_DOCUMENTS].runs
            return configured, InputSource.NEW_SNAPSHOT if runs else InputSource.CURRENT
        return ingested, InputSource.SNAPSHOT if ingested == configured else InputSource.OUTDATED_SNAPSHOT

    def _load_inputs(
        self,
        workspace: Workspace,
        data_uri: str,
        sources: dict[InputSnapshot, InputSource],
        actions: dict[PipelineStep, StepAction],
    ) -> tuple[DocumentRegistry, KnowledgeModel]:
        """Load the document registry and knowledge model this run uses.

        Args:
            workspace: Workspace holding the input files.
            data_uri: Data location the registry's sources are resolved against.
            sources: Where each input file is read from.
            actions: Action taken on each step.

        Returns:
            The document registry and the knowledge model, each from its snapshot if one is used, otherwise from the
            workspace.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, or an enabled entity
                type references unknown document collections.
        """

        def uri(snapshot: InputSnapshot, source_uri: str) -> str:
            return self._input_snapshots.uri(snapshot) if sources[snapshot].uses_snapshot else source_uri

        # Get document registry, validating its sources only if documents are going to be ingested from them
        registry_uri = uri(InputSnapshot.DOCUMENT_REGISTRY, str(workspace.paths.document_registry))
        document_registry = self._get_document_registry.execute(
            registry_uri,
            data_uri,
            validate_sources=actions[PipelineStep.INGEST_DOCUMENTS].runs,
        )
        logger.info(f'Document Collections obtained successfully from "{registry_uri}"\n\n{document_registry}')

        # Get knowledge model and validate the document collections of the enabled entity types
        model_uri = uri(InputSnapshot.KNOWLEDGE_MODEL, str(workspace.paths.knowledge_model))
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

        return document_registry, knowledge_model

    def _prepare(self, workspace: Workspace, data_uri: str, *, should_reset: bool) -> _PreparedRun:
        """Check the plan of a run and load the inputs it uses, without writing anything.

        Args:
            workspace: Workspace holding the input files.
            data_uri: Data location the registry's sources are resolved against.
            should_reset: Whether each step resets itself and every step that depends on it before running.

        Returns:
            The plan of the run along with the inputs it uses.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, or an enabled entity
                type references unknown document collections.
            PipelineExecutionError: If a step's required steps are neither run before it nor left completed.
        """
        self._validate_plan(should_reset=should_reset)
        resets = self._planned_resets(should_reset=should_reset)
        actions = self._step_actions(resets)

        paths = workspace.paths
        sources = {
            InputSnapshot.DOCUMENT_REGISTRY: self._input_source(
                InputSnapshot.DOCUMENT_REGISTRY,
                str(paths.document_registry),
                actions,
                resets,
            ),
            InputSnapshot.KNOWLEDGE_MODEL: self._input_source(
                InputSnapshot.KNOWLEDGE_MODEL,
                str(paths.knowledge_model),
                actions,
                resets,
            ),
        }
        chunking, chunking_source = self._resolve_chunking(actions, resets)
        document_registry, knowledge_model = self._load_inputs(workspace, data_uri, sources, actions)

        plan = PipelinePlan(
            steps=actions,
            inputs=(
                InputPlan(
                    paths.document_registry.name,
                    SNAPSHOT_STEPS[InputSnapshot.DOCUMENT_REGISTRY],
                    sources[InputSnapshot.DOCUMENT_REGISTRY],
                ),
                InputPlan(
                    paths.knowledge_model.name,
                    SNAPSHOT_STEPS[InputSnapshot.KNOWLEDGE_MODEL],
                    sources[InputSnapshot.KNOWLEDGE_MODEL],
                ),
                InputPlan(CHUNKING_INPUT_NAME, PipelineStep.INGEST_DOCUMENTS, chunking_source),
            ),
        )
        return _PreparedRun(
            plan=plan,
            resets=resets,
            sources=sources,
            chunking_source=chunking_source,
            document_registry=document_registry,
            knowledge_model=knowledge_model,
            chunking=chunking,
        )

    def _update_input_snapshots(self, workspace: Workspace, prepared: _PreparedRun) -> None:
        """Take or discard the input snapshots as planned, warning about inputs whose changes are ignored.

        Args:
            workspace: Workspace holding the input files.
            prepared: Plan of the run.
        """
        for snapshot, source_uri in (
            (InputSnapshot.DOCUMENT_REGISTRY, str(workspace.paths.document_registry)),
            (InputSnapshot.KNOWLEDGE_MODEL, str(workspace.paths.knowledge_model)),
        ):
            step = SNAPSHOT_STEPS[snapshot]
            if step in prepared.resets:
                self._input_snapshots.discard(snapshot)
            match prepared.sources[snapshot]:
                case InputSource.NEW_SNAPSHOT:
                    self._input_snapshots.save(snapshot, source_uri)
                case InputSource.OUTDATED_SNAPSHOT:
                    logger.warning(
                        f'"{source_uri}" changed since it was used to {step.value.lower().replace("_", " ")}. This run '
                        f'keeps using the version that step used; reset the {step.value} step to apply the changes.',
                    )

        if PipelineStep.INGEST_DOCUMENTS in prepared.resets:
            self._input_snapshots.discard_chunking()
        match prepared.chunking_source:
            case InputSource.NEW_SNAPSHOT:
                self._input_snapshots.save_chunking(prepared.chunking)
            case InputSource.OUTDATED_SNAPSHOT:
                logger.warning(
                    f'The {CHUNKING_INPUT_NAME} changed since documents were ingested. This run keeps using the '
                    f'ingested ones; reset the {PipelineStep.INGEST_DOCUMENTS.value} step to apply the changes.',
                )

    def plan(self, workspace: Workspace, data_uri: str, *, should_reset: bool = True) -> PipelinePlan:
        """Work out what executing the pipeline would do, without running, resetting or snapshotting anything.

        The inputs are loaded and validated as the execution would, so a plan that is returned can be executed.

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            data_uri: The base URI pointing to the data to be ingested (e.g. a local directory).
            should_reset: Whether each step would reset itself and every step that depends on it before running.

        Returns:
            What the execution would do with each step and where it would read its inputs from.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, or an enabled entity
                type references unknown document collections.
            PipelineExecutionError: If a step's required steps have not been completed.
        """
        return self._prepare(workspace, data_uri, should_reset=should_reset).plan

    async def execute(self, workspace: Workspace, data_uri: str, *, should_reset: bool = True) -> bool:
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

        Returns:
            True if every configured step is completed, False if the pipeline stopped early at a step left unfinished.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, or an enabled entity
                type references unknown document collections.
            PipelineExecutionError: If a step has no use case or its required steps have not been completed.
        """
        # Initialize the pipeline checkpoints
        with self._uow as tx:
            tx.pipeline.initialize_all_steps()

        # Check the whole plan and load the inputs before any input snapshot is taken, or any step runs or resets data
        prepared = self._prepare(workspace, data_uri, should_reset=should_reset)
        self._update_input_snapshots(workspace, prepared)

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
                        self._ingest_documents.execute(prepared.document_registry, data_uri, prepared.chunking)
                    case PipelineStep.EXTRACT_ENTITIES:
                        await self._extract_entities.execute(prepared.knowledge_model)
                    case PipelineStep.EXTRACT_RELATIONSHIPS:
                        await self._extract_relationships.execute(prepared.knowledge_model)
                    case PipelineStep.EXPORT_KNOWLEDGE:
                        self._export_knowledge.execute(prepared.knowledge_model)

                # Stop the pipeline if the step did not fully complete
                completed = False
                with self._uow as tx:
                    completed = tx.pipeline.is_step_completed(step)
                if not completed:
                    logger.info(f'{step.value} step is not fully completed. Stopping the pipeline...')
                    return False
                logger.info(f'{step.value} step completed successfully!')
            else:
                logger.info(f'Skipping {step.value} step because it has already been completed...')
        return True

    async def reset(self, from_step: PipelineStep = PipelineStep.INGEST_DOCUMENTS) -> None:
        """Reset a step and every step that depends on it, without running any of them.

        Their results and checkpoints are cleared, and the input snapshots they took are released, so that the next run
        uses the current inputs. Resetting from the first step resets the whole pipeline.

        Args:
            from_step: First step to reset.
        """
        steps = {from_step, *from_step.is_required_by}

        # Downstream steps are reset first, as when a run resets a step
        for step in reversed(PipelineStep):
            if step in steps:
                await self._reset_step(step)
        with self._uow as tx:
            for step in steps:
                tx.pipeline.reset_step_checkpoints(step)

        for snapshot, step in SNAPSHOT_STEPS.items():
            if step in steps:
                self._input_snapshots.discard(snapshot)
        if PipelineStep.INGEST_DOCUMENTS in steps:
            self._input_snapshots.discard_chunking()
