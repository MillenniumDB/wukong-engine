"""Status of the knowledge construction pipeline in a workspace."""

from dataclasses import dataclass
from enum import Enum

from wukong_engine.app.data_extraction.elements.values import BatchStatus, PerformanceMetricsState
from wukong_engine.app.data_extraction.services import ExtractionRepository
from wukong_engine.app.staging.ports import InputSnapshotStore, UnitOfWork
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.pipeline.model.values import InputSnapshot, PipelineStep

from .knowledge_construction_pipeline import CHUNKING_INPUT_NAME, SNAPSHOT_STEPS
from .pipeline_plan import InputPlan, InputSource


class StepState(Enum):
    """Progress of a pipeline step.

    Attributes:
        NOT_STARTED: The step has no results.
        IN_PROGRESS: The step has started, but has not completed yet.
        COMPLETED: The step has completed.
    """

    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'


@dataclass(frozen=True, slots=True)
class ExtractionProgress:
    """Progress of an extraction step at one context level.

    Attributes:
        context_level: Context level the sources belong to.
        completed: Number of sources extracted.
        failed: Number of sources whose extraction failed for good.
        remaining: Number of sources still to extract, including those awaiting a retry.
        pending_batches: Number of batches submitted to the provider and not collected yet.
        objects: Number of unique objects extracted.
    """

    context_level: ContextLevel
    completed: int
    failed: int
    remaining: int
    pending_batches: int
    objects: int

    def __str__(self) -> str:
        """User-friendly string representation of the extraction progress."""
        total = self.completed + self.failed + self.remaining
        progress = f'{self.context_level.value}S: {self.completed}/{total} sources extracted'
        if self.failed:
            progress += f', {self.failed} failed'
        if self.pending_batches:
            progress += f', {self.pending_batches} batches pending at the provider'
        return f'{progress} ({self.objects} objects)'


@dataclass(frozen=True, slots=True)
class PipelineStatus:
    """Status of the pipeline in a workspace.

    Attributes:
        steps: Progress of each step, in pipeline order.
        documents: Number of ingested documents.
        chunks: Number of ingested chunks.
        extractions: Progress of each extraction step, per context level with sources to extract.
        inputs: Where the next run reads each input from, as far as known without a configuration.
    """

    steps: dict[PipelineStep, StepState]
    documents: int
    chunks: int
    extractions: dict[PipelineStep, tuple[ExtractionProgress, ...]]
    inputs: tuple[InputPlan, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the pipeline status."""
        width = max(len(step.value) for step in self.steps)
        lines = []
        lines.append('=' * 80)
        lines.append(' STATUS')
        lines.append('=' * 80)

        lines.append('\n[STEPS]\n')
        for step, state in self.steps.items():
            lines.append(f'  {step.value:<{width}}  {state.value.replace("_", " ").capitalize()}')
            if step is PipelineStep.INGEST_DOCUMENTS and state is not StepState.NOT_STARTED:
                lines.append(f'    {self.documents} documents, {self.chunks} chunks')
            lines.extend(f'    {progress}' for progress in self.extractions.get(step, ()))

        lines.append('\n[INPUTS]\n')
        lines.extend(f'  {input_plan}' for input_plan in self.inputs)

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)


class GetPipelineStatus:
    """Read the status of the pipeline in a workspace, without needing a configuration or changing anything."""

    def __init__(
        self,
        uow: UnitOfWork,
        input_snapshots: InputSnapshotStore,
        entity_repository: ExtractionRepository,
        relationship_repository: ExtractionRepository,
    ) -> None:
        """Initialize the use case with the stores of the workspace.

        Args:
            uow: Unit of work used to read pipeline checkpoints and ingestion counts.
            input_snapshots: Store of the snapshots of the input files and chunking settings.
            entity_repository: Repository of entity extractions.
            relationship_repository: Repository of relationship extractions.
        """
        self._uow = uow
        self._input_snapshots = input_snapshots
        self._repositories = {
            PipelineStep.EXTRACT_ENTITIES: entity_repository,
            PipelineStep.EXTRACT_RELATIONSHIPS: relationship_repository,
        }

    def _extraction_progress(self, repository: ExtractionRepository) -> tuple[ExtractionProgress, ...]:
        """Get the progress of an extraction step at each context level with sources to extract.

        Args:
            repository: Repository of the step's extractions.

        Returns:
            The progress at each context level that has sources, in extraction order.
        """
        progress = []
        for context_level in (ContextLevel.DOCUMENT, ContextLevel.CHUNK):
            metrics = repository.get_extraction_metrics(context_level, PerformanceMetricsState())
            if metrics.total_sources == 0:
                continue
            progress.append(
                ExtractionProgress(
                    context_level=context_level,
                    completed=metrics.source_counts['completed'],
                    failed=metrics.source_counts['failed'],
                    remaining=metrics.remaining_sources,
                    pending_batches=(
                        metrics.batch_status_counts.get(BatchStatus.SUBMITTED, 0)
                        + metrics.batch_status_counts.get(BatchStatus.IN_PROGRESS, 0)
                    ),
                    objects=metrics.object_count,
                ),
            )
        return tuple(progress)

    def _input_status(self, snapshot: InputSnapshot, source_uri: str) -> InputSource:
        """Get whether an input file has a snapshot, and whether the file changed since it was taken.

        Args:
            snapshot: Input file to check.
            source_uri: Location of the input file in the workspace.

        Returns:
            Where the next run reads the input file from, unless that run resets the step that took its snapshot.
        """
        if not self._input_snapshots.exists(snapshot):
            return InputSource.CURRENT
        if self._input_snapshots.matches(snapshot, source_uri):
            return InputSource.SNAPSHOT
        return InputSource.OUTDATED_SNAPSHOT

    def execute(self, workspace: Workspace) -> PipelineStatus:
        """Read the status of the pipeline.

        Args:
            workspace: Workspace whose input files are compared with their snapshots.

        Returns:
            The progress of each step and where the next run reads each input from.
        """
        with self._uow as tx:
            completed = {step for step in PipelineStep if tx.pipeline.is_step_completed(step)}
            started = {
                step
                for step in PipelineStep
                if any(tx.pipeline.is_checkpoint_completed(checkpoint) for checkpoint in step.checkpoints)
            }
            documents = tx.documents.count_documents()
            chunks = tx.documents.count_chunks()
        extractions = {step: self._extraction_progress(repository) for step, repository in self._repositories.items()}
        if documents > 0:
            started.add(PipelineStep.INGEST_DOCUMENTS)
        started.update(step for step, progress in extractions.items() if progress)

        steps = {
            step: (
                StepState.COMPLETED
                if step in completed
                else StepState.IN_PROGRESS
                if step in started
                else StepState.NOT_STARTED
            )
            for step in PipelineStep
        }
        paths = workspace.paths
        chunking_source = InputSource.CURRENT if self._input_snapshots.load_chunking() is None else InputSource.SNAPSHOT
        inputs = (
            InputPlan(
                paths.document_registry.name,
                SNAPSHOT_STEPS[InputSnapshot.DOCUMENT_REGISTRY],
                self._input_status(InputSnapshot.DOCUMENT_REGISTRY, str(paths.document_registry)),
            ),
            InputPlan(
                paths.knowledge_model.name,
                SNAPSHOT_STEPS[InputSnapshot.KNOWLEDGE_MODEL],
                self._input_status(InputSnapshot.KNOWLEDGE_MODEL, str(paths.knowledge_model)),
            ),
            InputPlan(CHUNKING_INPUT_NAME, PipelineStep.INGEST_DOCUMENTS, chunking_source),
        )
        return PipelineStatus(
            steps=steps,
            documents=documents,
            chunks=chunks,
            extractions=extractions,
            inputs=inputs,
        )
