"""Tests for reading the status of the pipeline in a workspace."""

from pathlib import Path

from wukong_engine.app.data_extraction.services import EntityExtractionRepository, RelationshipExtractionRepository
from wukong_engine.app.workflows import GetPipelineStatus, StepState
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus, PipelineStep
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem import LocalInputSnapshotStore


def test_a_step_is_in_progress_once_any_of_its_checkpoints_is_completed(tmp_path: Path) -> None:
    """Tell apart completed steps, steps left halfway by an earlier run and steps never started."""
    workspace = Workspace(tmp_path)
    factory = SQLiteSessionFactory(db_path=workspace.paths.staging_db)
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    uow = SQLiteUnitOfWork(connection_factory=factory)
    with uow as tx:
        tx.pipeline.initialize_all_steps()
        tx.pipeline.set_checkpoint_status(PipelineCheckpoint.DOCUMENTS_INGESTED, PipelineCheckpointStatus.COMPLETED)
        tx.pipeline.set_checkpoint_status(
            PipelineCheckpoint.PENDING_ENTITY_EXTRACTIONS_MATERIALIZED,
            PipelineCheckpointStatus.COMPLETED,
        )

    status = GetPipelineStatus(
        uow=uow,
        input_snapshots=LocalInputSnapshotStore(workspace.paths.snapshots),
        entity_repository=EntityExtractionRepository(uow=uow),
        relationship_repository=RelationshipExtractionRepository(uow=uow),
    ).execute(workspace)

    assert status.steps == {
        PipelineStep.INGEST_DOCUMENTS: StepState.COMPLETED,
        PipelineStep.EXTRACT_ENTITIES: StepState.IN_PROGRESS,
        PipelineStep.EXTRACT_RELATIONSHIPS: StepState.NOT_STARTED,
        PipelineStep.EXPORT_KNOWLEDGE: StepState.NOT_STARTED,
    }
