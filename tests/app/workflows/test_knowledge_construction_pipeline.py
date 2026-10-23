"""Tests for the step planning of the knowledge construction pipeline."""

import asyncio
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.config.pipeline import PipelineConfig
from wukong_engine.app.shared.exceptions import PipelineExecutionError
from wukong_engine.app.workflows.knowledge_construction_pipeline import KnowledgeConstructionPipeline
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.pipeline.model.values import PipelineCheckpointStatus, PipelineStep
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem import LocalInputSnapshotStore


class RecordingStep:
    """Pipeline step use case recording its resets and runs, completing its checkpoints when run."""

    def __init__(self, step: PipelineStep, uow: SQLiteUnitOfWork, calls: list[str]) -> None:
        """Initialize the step with the unit of work holding its checkpoints and a shared call log."""
        self.step, self.uow, self.calls = step, uow, calls

    def execute(self, *_: Any) -> None:
        """Record the run and complete the step."""
        self.calls.append(f'run {self.step.value}')
        with self.uow as tx:
            for checkpoint in self.step.checkpoints:
                tx.pipeline.set_checkpoint_status(checkpoint, PipelineCheckpointStatus.COMPLETED)

    def reset(self) -> None:
        """Record the reset."""
        self.calls.append(f'reset {self.step.value}')


class AsyncRecordingStep(RecordingStep):
    """Asynchronous variant of the recording step, as used by the extraction steps."""

    async def execute(self, *args: Any) -> None:
        """Record the run and complete the step."""
        super().execute(*args)

    async def reset(self) -> None:
        """Record the reset."""
        super().reset()


def _snapshot_store(workspace_root: Path) -> LocalInputSnapshotStore:
    """Create the workspace's input files, which the stubbed use cases ignore, and a store for their snapshots."""
    for name in ('knowledge_model.json', 'document_collections.json'):
        (workspace_root / name).write_text('{}')
    return LocalInputSnapshotStore(workspace_root / 'staging' / 'snapshots')


def _run(
    tmp_path: Path,
    pipeline_config: PipelineConfig,
    *,
    should_reset: bool,
    completed: set[PipelineStep],
    calls: list[str],
) -> None:
    """Run the pipeline with steps recording into ``calls``, over a database holding the given completed steps."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    uow = SQLiteUnitOfWork(connection_factory=factory)
    with uow as tx:
        tx.pipeline.initialize_all_steps()
        for step in completed:
            for checkpoint in step.checkpoints:
                tx.pipeline.set_checkpoint_status(checkpoint, PipelineCheckpointStatus.COMPLETED)

    steps = {
        step: (
            AsyncRecordingStep
            if step in {PipelineStep.EXTRACT_ENTITIES, PipelineStep.EXTRACT_RELATIONSHIPS}
            else RecordingStep
        )(step, uow, calls)
        for step in PipelineStep
    }
    registry = SimpleNamespace(validate_collections=lambda _: None)
    pipeline = KnowledgeConstructionPipeline(
        app_config=SimpleNamespace(pipeline=pipeline_config, chunking=ChunkingConfig()),
        uow=uow,
        input_snapshots=_snapshot_store(tmp_path),
        get_document_registry=SimpleNamespace(execute=lambda *_, **__: registry),
        get_knowledge_model=SimpleNamespace(execute=lambda *_: SimpleNamespace(active_entity_types={})),
        ingest_documents=steps[PipelineStep.INGEST_DOCUMENTS],
        extract_entities=steps[PipelineStep.EXTRACT_ENTITIES],
        extract_relationships=steps[PipelineStep.EXTRACT_RELATIONSHIPS],
        export_knowledge=steps[PipelineStep.EXPORT_KNOWLEDGE],
    )
    asyncio.run(pipeline.execute(Workspace(tmp_path), str(tmp_path), should_reset=should_reset))


ALL_STEPS = set(PipelineStep)
INGEST_AND_EXPORT = PipelineConfig(extract_entities=False, extract_relationships=False)


def test_a_reset_that_would_leave_a_later_step_without_its_requirements_runs_and_resets_nothing(
    tmp_path: Path,
) -> None:
    """Refuse a plan whose reset wipes results a later step needs, before any extraction result is lost."""
    calls: list[str] = []
    with pytest.raises(PipelineExecutionError, match=r'EXTRACT_ENTITIES \(reset by an earlier step\)'):
        _run(tmp_path, INGEST_AND_EXPORT, should_reset=True, completed=ALL_STEPS, calls=calls)
    assert calls == []


def test_a_step_whose_requirements_never_completed_runs_and_resets_nothing(tmp_path: Path) -> None:
    """Refuse a plan whose steps need results that were never produced, naming them."""
    calls: list[str] = []
    with pytest.raises(PipelineExecutionError, match=r'EXTRACT_ENTITIES \(not completed\)'):
        _run(tmp_path, INGEST_AND_EXPORT, should_reset=False, completed=set(), calls=calls)
    assert calls == []


def test_a_plan_relying_on_completed_steps_runs(tmp_path: Path) -> None:
    """Run a partial plan when the steps it skips are already completed and nothing resets them."""
    calls: list[str] = []
    _run(
        tmp_path,
        PipelineConfig(ingest_documents=False, extract_relationships=False, export_knowledge=False),
        should_reset=True,
        completed=ALL_STEPS,
        calls=calls,
    )

    assert set(calls[:2]) == {'reset EXTRACT_RELATIONSHIPS', 'reset EXPORT_KNOWLEDGE'}
    assert calls[2:] == ['reset EXTRACT_ENTITIES', 'run EXTRACT_ENTITIES']


def test_only_the_collections_of_enabled_entity_types_must_exist(tmp_path: Path) -> None:
    """Check the collections of enabled entity types only, so a disabled one may point at a removed collection."""
    registry = DocumentRegistry(collections=MappingProxyType({}))
    model = KnowledgeModelMapper().map_knowledge_model(
        KnowledgeModelSchema.model_validate(
            {
                'extraction_config': {'projection': {'enabled_entities': []}},
                'entity_types': {
                    'Mission': {
                        'description': 'A mission.',
                        'primary_key': 'code',
                        'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
                        'document_collections': {'chunk': 'removed'},
                    },
                },
            },
        ),
    )
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    pipeline = KnowledgeConstructionPipeline(
        app_config=SimpleNamespace(
            chunking=ChunkingConfig(),
            pipeline=PipelineConfig(
                ingest_documents=False,
                extract_entities=False,
                extract_relationships=False,
                export_knowledge=False,
            ),
        ),
        uow=SQLiteUnitOfWork(connection_factory=factory),
        input_snapshots=_snapshot_store(tmp_path),
        get_document_registry=SimpleNamespace(execute=lambda *_, **__: registry),
        get_knowledge_model=SimpleNamespace(execute=lambda *_: model),
        ingest_documents=None,
        extract_entities=None,
        extract_relationships=None,
        export_knowledge=None,
    )

    asyncio.run(pipeline.execute(Workspace(tmp_path), str(tmp_path)))
