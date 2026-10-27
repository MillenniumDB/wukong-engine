"""Reset of the stored results of the knowledge construction pipeline."""

from wukong_engine.app.data_extraction.use_cases import ResetExtraction
from wukong_engine.app.document_ingestion.use_cases import ResetDocumentIngestion
from wukong_engine.app.knowledge_export.use_cases import ResetKnowledgeExport
from wukong_engine.app.staging.ports import InputSnapshotStore, UnitOfWork
from wukong_engine.core.pipeline.model.values import PipelineStep

from .pipeline_plan import SNAPSHOT_STEPS


class ResetPipeline:
    """Reset the results of pipeline steps, which needs neither a configuration nor the steps able to run."""

    def __init__(
        self,
        uow: UnitOfWork,
        input_snapshots: InputSnapshotStore,
        reset_document_ingestion: ResetDocumentIngestion,
        reset_entity_extraction: ResetExtraction,
        reset_relationship_extraction: ResetExtraction,
        reset_knowledge_export: ResetKnowledgeExport,
    ) -> None:
        """Initialize the workflow with the reset use case of each step.

        Args:
            uow: Unit of work used to reset pipeline checkpoints.
            input_snapshots: Store of the snapshots of the input files and chunking settings the steps use.
            reset_document_ingestion: Use case resetting the document ingestion step.
            reset_entity_extraction: Use case resetting the entity extraction step.
            reset_relationship_extraction: Use case resetting the relationship extraction step.
            reset_knowledge_export: Use case resetting the knowledge export step.
        """
        self._uow = uow
        self._input_snapshots = input_snapshots
        self._reset_document_ingestion = reset_document_ingestion
        self._reset_entity_extraction = reset_entity_extraction
        self._reset_relationship_extraction = reset_relationship_extraction
        self._reset_knowledge_export = reset_knowledge_export

    async def reset_step(self, step: PipelineStep) -> None:
        """Clear the results of a single step, leaving its checkpoints and input snapshots as they are.

        Args:
            step: Pipeline step to reset.
        """
        match step:
            case PipelineStep.INGEST_DOCUMENTS:
                self._reset_document_ingestion.execute()
            case PipelineStep.EXTRACT_ENTITIES:
                await self._reset_entity_extraction.execute()
            case PipelineStep.EXTRACT_RELATIONSHIPS:
                await self._reset_relationship_extraction.execute()
            case PipelineStep.EXPORT_KNOWLEDGE:
                self._reset_knowledge_export.execute()

    async def execute(self, from_step: PipelineStep = PipelineStep.INGEST_DOCUMENTS) -> None:
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
                await self.reset_step(step)
        with self._uow as tx:
            for step in steps:
                tx.pipeline.reset_step_checkpoints(step)

        for snapshot, step in SNAPSHOT_STEPS.items():
            if step in steps:
                self._input_snapshots.discard(snapshot)
        if PipelineStep.INGEST_DOCUMENTS in steps:
            self._input_snapshots.discard_chunking()
