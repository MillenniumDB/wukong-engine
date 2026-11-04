"""Implements the engine pipeline."""

import logging
import time
from dataclasses import dataclass

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.data_extraction.use_cases import ExtractEntities, ExtractRelationships
from wukong_engine.app.document_ingestion.elements import DocumentAdditions
from wukong_engine.app.document_ingestion.use_cases import CheckDocumentAdditions, IngestDocuments
from wukong_engine.app.knowledge_export.elements import ExportReport
from wukong_engine.app.knowledge_export.use_cases import ExportKnowledge
from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetKnowledgeModel
from wukong_engine.app.shared.exceptions import PipelineExecutionError
from wukong_engine.app.shared.progress import progress
from wukong_engine.app.staging.ports import InputSnapshotStore, UnitOfWork
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.pipeline.model.values import (
    InputSnapshot,
    PipelineCheckpointStatus,
    PipelineStep,
)

from .pipeline_plan import (
    CHUNKING_INPUT_NAME,
    EXTENDABLE_STEPS,
    SNAPSHOT_STEPS,
    InputPlan,
    InputSource,
    PipelinePlan,
    StepAction,
)
from .pipeline_reset import ResetPipeline
from .run_stats import RunStatsService, format_duration

# Logging
logger = logging.getLogger(__name__)

# Documents named in the error refusing an addition that would leave their extracted relationships incomplete
MAX_CONFLICTS_SHOWN = 5


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


@dataclass(frozen=True, slots=True)
class PipelineSteps:
    """Use cases running each pipeline step.

    Attributes:
        ingest_documents: Use case for the document ingestion step.
        extract_entities: Use case for the entity extraction step.
        extract_relationships: Use case for the relationship extraction step.
        export_knowledge: Use case for the knowledge export step.
    """

    ingest_documents: IngestDocuments
    extract_entities: ExtractEntities
    extract_relationships: ExtractRelationships
    export_knowledge: ExportKnowledge


class KnowledgeConstructionPipeline:
    """Pipeline to build a knowledge base from unstructured documents."""

    def __init__(
        self,
        app_config: ApplicationConfig,
        uow: UnitOfWork,
        input_snapshots: InputSnapshotStore,
        get_document_registry: GetDocumentRegistry,
        get_knowledge_model: GetKnowledgeModel,
        check_document_additions: CheckDocumentAdditions,
        steps: PipelineSteps,
        reset_pipeline: ResetPipeline,
        run_stats: RunStatsService,
    ) -> None:
        """Initialize the knowledge construction workflow with its use cases.

        Args:
            app_config: Application configuration; its pipeline settings select which steps run.
            uow: Unit of work used to read and update pipeline checkpoints.
            input_snapshots: Store of the snapshots of the input files and chunking settings the steps use.
            get_document_registry: Use case that loads and validates the document registry.
            get_knowledge_model: Use case that loads the knowledge model.
            check_document_additions: Use case checking what adding the documents of the registry would do, used when
                a run adds documents.
            steps: Use cases running each pipeline step.
            reset_pipeline: Workflow resetting the results of the steps, used when a run resets them.
            run_stats: Service reading the statistics shown after each step and at the end of a run, and recording
                them next to the export.
        """
        self._app_config = app_config
        self._uow = uow
        self._input_snapshots = input_snapshots
        self._get_document_registry = get_document_registry
        self._get_knowledge_model = get_knowledge_model
        self._check_document_additions = check_document_additions
        self._steps = steps
        self._reset_pipeline = reset_pipeline
        self._run_stats = run_stats

    def _validate_plan(self, *, should_reset: bool, reopened: set[PipelineStep]) -> None:
        """Check that every configured step will find its required steps completed when it runs.

        A required step is satisfied if it runs earlier in the plan, or if it is already completed, isn't reopened
        for added documents and no earlier step resets it.

        Args:
            should_reset: Whether each step resets itself and every step that depends on it before running.
            reopened: Steps the run reopens for added documents, which are no longer completed once it starts.

        Raises:
            PipelineExecutionError: If a step's required steps are neither run before it nor left completed.
        """
        with self._uow as tx:
            completed = {step for step in PipelineStep if tx.pipeline.is_step_completed(step)} - reopened

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

    def _step_actions(self, resets: set[PipelineStep], reopened: set[PipelineStep]) -> dict[PipelineStep, StepAction]:
        """Get what this run does with each pipeline step.

        Args:
            resets: Steps this run resets.
            reopened: Steps the run reopens for added documents.

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
                    actions[step] = StepAction.EXTEND if step in reopened else StepAction.SKIP
                else:
                    actions[step] = StepAction.RUN
            elif step in resets:
                actions[step] = StepAction.RESET
            elif step in completed:
                actions[step] = StepAction.KEEP_TO_EXTEND if step in reopened else StepAction.KEEP
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
        *,
        add_documents: bool,
    ) -> tuple[DocumentRegistry, KnowledgeModel, dict[InputSnapshot, InputSource]]:
        """Load the document registry and knowledge model this run uses.

        A run adding documents uses an edited input instead of its snapshot when the edit only adds to it: collections
        or sources to the registry, or collections to the entity types of the model.

        Args:
            workspace: Workspace holding the input files.
            data_uri: Data location the registry's sources are resolved against.
            sources: Where each input file is read from.
            actions: Action taken on each step.
            add_documents: Whether the run adds documents.

        Returns:
            The document registry and the knowledge model, each from its snapshot if one is used, otherwise from the
            workspace, along with where each input file is read from.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, an enabled entity
                type references unknown document collections, or documents are added from a registry that leaves out
                sources of its snapshot.
        """
        sources = dict(sources)
        registry_path = str(workspace.paths.document_registry)
        model_path = str(workspace.paths.knowledge_model)

        def uri(snapshot: InputSnapshot, source_uri: str) -> str:
            return self._input_snapshots.uri(snapshot) if sources[snapshot].uses_snapshot else source_uri

        # Get document registry, validating its sources only if documents are going to be ingested from them
        validate_sources = actions[PipelineStep.INGEST_DOCUMENTS].runs
        registry_uri = uri(InputSnapshot.DOCUMENT_REGISTRY, registry_path)
        document_registry = self._get_document_registry.execute(
            registry_uri,
            data_uri,
            validate_sources=validate_sources,
        )
        if add_documents and sources[InputSnapshot.DOCUMENT_REGISTRY] is InputSource.OUTDATED_SNAPSHOT:
            current_registry = self._get_document_registry.execute(
                registry_path,
                data_uri,
                validate_sources=validate_sources,
            )
            missing = document_registry.sources_missing_from(current_registry)
            if missing:
                details = ', '.join(f'{source} from "{collection}"' for collection, source in missing)
                error = (
                    f'Documents can only be added from a "{registry_path}" that keeps every collection and source it '
                    f'had when documents were ingested, but it leaves out: {details}. Restore them, or reset the '
                    f'{PipelineStep.INGEST_DOCUMENTS.value} step to ingest the documents from scratch.'
                )
                logger.error(error)
                raise ModelIngestionError(error)
            document_registry, registry_uri = current_registry, registry_path
            sources[InputSnapshot.DOCUMENT_REGISTRY] = InputSource.EXTENDED_SNAPSHOT
        logger.info(f'Document Collections obtained successfully from "{registry_uri}"\n\n{document_registry}')

        # Get knowledge model and validate the document collections of the enabled entity types
        model_uri = uri(InputSnapshot.KNOWLEDGE_MODEL, model_path)
        knowledge_model = self._get_knowledge_model.execute(model_uri)
        if add_documents and sources[InputSnapshot.KNOWLEDGE_MODEL] is InputSource.OUTDATED_SNAPSHOT:
            current_model = self._get_knowledge_model.execute(model_path)
            if current_model.only_adds_collections_to(knowledge_model):
                knowledge_model, model_uri = current_model, model_path
                sources[InputSnapshot.KNOWLEDGE_MODEL] = InputSource.EXTENDED_SNAPSHOT
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

        return document_registry, knowledge_model, sources

    def _validate_document_addition(self, *, should_reset: bool) -> None:
        """Check that a run adding documents can do so.

        Args:
            should_reset: Whether each step resets itself and every step that depends on it before running.

        Raises:
            PipelineExecutionError: If the run resets steps, which would discard the results documents are added to,
                or doesn't ingest documents.
        """
        if should_reset:
            error = 'Documents are added to the stored results, so adding them can not be combined with a reset.'
            logger.error(error)
            raise PipelineExecutionError(error)
        if not self._app_config.pipeline.is_active(PipelineStep.INGEST_DOCUMENTS):
            error = (
                f'Adding documents ingests them, but the {PipelineStep.INGEST_DOCUMENTS.value.lower()} step is disabled '
                f'in the [pipeline] section of the configuration.'
            )
            logger.error(error)
            raise PipelineExecutionError(error)

    def _check_additions(
        self,
        document_registry: DocumentRegistry,
        data_uri: str,
        knowledge_model: KnowledgeModel,
    ) -> DocumentAdditions:
        """Find the documents a run adds, refusing an addition that would leave extracted relationships incomplete.

        Args:
            document_registry: Registry the documents are added from.
            data_uri: Data location the registry's sources are resolved against.
            knowledge_model: Knowledge model the documents are extracted with.

        Returns:
            What adding the documents does.

        Raises:
            PipelineExecutionError: If documents that relationships were extracted from would become extractable for
                more entity types.
        """
        additions = self._check_document_additions.execute(document_registry, data_uri, knowledge_model)
        if additions.conflicts:
            shown = ', '.join(f'"{document.source_uri}"' for document in additions.conflicts[:MAX_CONFLICTS_SHOWN])
            more = len(additions.conflicts) - MAX_CONFLICTS_SHOWN
            error = (
                f'{len(additions.conflicts):,} ingested documents would be extracted for more entity types, but '
                f'relationships were already extracted from them, and would miss the new entities: {shown}'
                f'{f" and {more:,} more" if more > 0 else ""}. This happens when a document joins another '
                f'collection, or a collection holding it is added to an entity type. Leave those documents out of '
                f'the change, or reset the {PipelineStep.EXTRACT_RELATIONSHIPS.value} step first, which keeps the '
                f'extracted entities. Nothing was run or reset.'
            )
            logger.error(error)
            raise PipelineExecutionError(error)
        return additions

    def _prepare(
        self,
        workspace: Workspace,
        data_uri: str,
        *,
        should_reset: bool,
        add_documents: bool,
    ) -> _PreparedRun:
        """Check the plan of a run and load the inputs it uses, without writing anything.

        Args:
            workspace: Workspace holding the input files.
            data_uri: Data location the registry's sources are resolved against.
            should_reset: Whether each step resets itself and every step that depends on it before running.
            add_documents: Whether the run adds the documents of the registry to the ingested ones, reopening the
                steps whose results grow with them.

        Returns:
            The plan of the run along with the inputs it uses.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, an enabled entity
                type references unknown document collections, or documents are added from a registry that leaves out
                sources of its snapshot.
            PipelineExecutionError: If a step's required steps are neither run before it nor left completed, or the
                documents can't be added.
        """
        if add_documents:
            self._validate_document_addition(should_reset=should_reset)
        reopened = set(EXTENDABLE_STEPS) if add_documents else set()
        self._validate_plan(should_reset=should_reset, reopened=reopened)
        resets = self._planned_resets(should_reset=should_reset)
        actions = self._step_actions(resets, reopened)

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
        document_registry, knowledge_model, sources = self._load_inputs(
            workspace,
            data_uri,
            sources,
            actions,
            add_documents=add_documents,
        )
        additions = self._check_additions(document_registry, data_uri, knowledge_model) if add_documents else None

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
            additions=additions,
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
        for snapshot, source_uri, additive_change in (
            (InputSnapshot.DOCUMENT_REGISTRY, str(workspace.paths.document_registry), 'collections or sources'),
            (InputSnapshot.KNOWLEDGE_MODEL, str(workspace.paths.knowledge_model), 'collections to entity types'),
        ):
            step = SNAPSHOT_STEPS[snapshot]
            if step in prepared.resets:
                self._input_snapshots.discard(snapshot)
            match prepared.sources[snapshot]:
                case InputSource.NEW_SNAPSHOT | InputSource.EXTENDED_SNAPSHOT:
                    self._input_snapshots.save(snapshot, source_uri)
                case InputSource.OUTDATED_SNAPSHOT:
                    logger.warning(
                        f'"{source_uri}" changed since it was used to {step.value.lower().replace("_", " ")}. This run '
                        f'keeps using the version that step used; reset the {step.value} step to apply the changes, '
                        f'or, if they only add {additive_change}, add documents with --add-documents to apply them.',
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

    def _reopen_for_added_documents(self, workspace: Workspace, prepared: _PreparedRun) -> None:
        """Reopen the steps whose results grow with added documents, then take the snapshots of the extended inputs.

        The steps are reopened first: if the run stops before the snapshots are taken, later runs ingest the
        documents of the previous registry again, which stores nothing new, and keep warning that it changed.
        Snapshots taken first would instead leave the added documents out for good, with nothing left to warn about.

        Args:
            workspace: Workspace holding the input files.
            prepared: Plan of the run, adding documents.
        """
        with self._uow as tx:
            for step in EXTENDABLE_STEPS:
                for checkpoint in step.checkpoints:
                    tx.pipeline.set_checkpoint_status(checkpoint, PipelineCheckpointStatus.PENDING)
        self._update_input_snapshots(workspace, prepared)

    def plan(
        self,
        workspace: Workspace,
        data_uri: str,
        *,
        should_reset: bool = True,
        add_documents: bool = False,
    ) -> PipelinePlan:
        """Work out what executing the pipeline would do, without running, resetting or snapshotting anything.

        The inputs are loaded and validated as the execution would, so a plan that is returned can be executed.

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            data_uri: The base URI pointing to the data to be ingested (e.g. a local directory).
            should_reset: Whether each step would reset itself and every step that depends on it before running.
            add_documents: Whether the run would add the documents of the registry to the ingested ones.

        Returns:
            What the execution would do with each step and where it would read its inputs from.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, an enabled entity
                type references unknown document collections, or documents are added from a registry that leaves out
                sources of its snapshot.
            PipelineExecutionError: If a step's required steps have not been completed, or the documents can't be
                added.
        """
        return self._prepare(workspace, data_uri, should_reset=should_reset, add_documents=add_documents).plan

    def add_documents(self, workspace: Workspace, data_uri: str) -> PipelinePlan:
        """Prepare the workspace to add the documents of the registry, without running any step.

        Reopens the steps whose results grow with the added documents, and takes the snapshots of the inputs the
        addition extends, so that the next runs process the added documents.

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            data_uri: The base URI pointing to the data to be ingested (e.g. a local directory).

        Returns:
            What the addition does with each step and where the next runs read their inputs from.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, an enabled entity
                type references unknown document collections, or the registry leaves out sources of its snapshot.
            PipelineExecutionError: If a step's required steps have not been completed, or the documents can't be
                added.
        """
        with self._uow as tx:
            tx.pipeline.initialize_all_steps()
        prepared = self._prepare(workspace, data_uri, should_reset=False, add_documents=True)
        self._reopen_for_added_documents(workspace, prepared)
        progress.info(str(prepared.plan).rstrip())
        return prepared.plan

    async def execute(
        self,
        workspace: Workspace,
        data_uri: str,
        *,
        should_reset: bool = True,
        add_documents: bool = False,
    ) -> bool:
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
        settings change, until the step that took them is reset. A run adding documents instead reopens the steps
        whose results grow with them, using the registry and model as edited if the edits only add to them.

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            data_uri: The base URI pointing to the data to be ingested (e.g. a local directory).
            should_reset: If True, resets each step and every step that depends on it before running it. If False,
                keeps existing data and appends any new results.
            add_documents: If True, adds the documents of the registry to the ingested ones, keeping every stored
                result. Can't be combined with ``should_reset``.

        Returns:
            True if every configured step is completed, False if the pipeline stopped early at a step left unfinished.

        Raises:
            ModelIngestionError: If the document registry or the knowledge model can't be loaded, an enabled entity
                type references unknown document collections, or documents are added from a registry that leaves out
                sources of its snapshot.
            PipelineExecutionError: If a step's required steps have not been completed, or the documents can't be
                added.
        """
        # Initialize the pipeline checkpoints
        with self._uow as tx:
            tx.pipeline.initialize_all_steps()

        # Check the whole plan and load the inputs before any input snapshot is taken, or any step runs or resets data
        prepared = self._prepare(workspace, data_uri, should_reset=should_reset, add_documents=add_documents)
        if add_documents:
            self._reopen_for_added_documents(workspace, prepared)
        else:
            self._update_input_snapshots(workspace, prepared)
        progress.info(str(prepared.plan).rstrip())

        # Run pipeline steps
        durations: dict[PipelineStep, float] = {}
        export_report: ExportReport | None = None
        for step in self._app_config.pipeline.steps:
            # Reset all steps downstream if the reset flag is present
            if should_reset:
                for dependent_step in step.is_required_by:
                    await self._reset_pipeline.reset_step(dependent_step)
                await self._reset_pipeline.reset_step(step)
                with self._uow as tx:
                    tx.pipeline.reset_dependent_checkpoints(step)

            # Check if step has already been completed
            with self._uow as tx:
                # Knowledge is exported again on every run, so the previous export no longer counts as done
                tx.pipeline.reset_step_checkpoints(PipelineStep.EXPORT_KNOWLEDGE)
                completed = tx.pipeline.is_step_completed(step)

            # If completed, skip the step, as the plan shown at the start of the run says
            if completed:
                logger.info(f'Skipping {step.value} step because it has already been completed...')
                continue

            # Execute the step, recording how long it ran even if it fails
            progress.info(f'\n▶ {step.value}...')
            started = time.monotonic()
            try:
                match step:
                    case PipelineStep.INGEST_DOCUMENTS:
                        self._steps.ingest_documents.execute(prepared.document_registry, data_uri, prepared.chunking)
                    case PipelineStep.EXTRACT_ENTITIES:
                        await self._steps.extract_entities.execute(prepared.knowledge_model)
                    case PipelineStep.EXTRACT_RELATIONSHIPS:
                        await self._steps.extract_relationships.execute(prepared.knowledge_model)
                    case PipelineStep.EXPORT_KNOWLEDGE:
                        export_report = self._steps.export_knowledge.execute(prepared.knowledge_model)
            finally:
                durations[step] = time.monotonic() - started
                with self._uow as tx:
                    tx.pipeline.record_step_run(step, durations[step])

            # Stop the pipeline if the step did not fully complete
            with self._uow as tx:
                completed = tx.pipeline.is_step_completed(step)
            summary = self._run_stats.collect(durations, export_report).step_summary(step)
            if not completed:
                progress.info(f'… {step.value} left unfinished after {format_duration(durations[step])}: {summary}')
                return False
            progress.info(f'✓ {step.value} completed in {format_duration(durations[step])}: {summary}')

        # Show the stats of the finished run, and record them with its export
        stats = self._run_stats.collect(durations, export_report)
        progress.info(f'\n{stats}')
        if export_report is not None:
            self._run_stats.save(stats, export_report.directory)
            progress.info(f'Run stats saved to {export_report.directory}')
        return True
