"""Tests for the step planning of the knowledge construction pipeline."""

import asyncio
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.config.pipeline import PipelineConfig
from wukong_engine.app.shared.exceptions import PipelineExecutionError
from wukong_engine.app.workflows import StepAction
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
    """Pipeline step use case recording its resets and runs, completing its checkpoints when run unless unfinished."""

    def __init__(self, step: PipelineStep, uow: SQLiteUnitOfWork, calls: list[str], *, unfinished: bool) -> None:
        """Initialize the step with the unit of work holding its checkpoints and a shared call log."""
        self.step, self.uow, self.calls, self.unfinished = step, uow, calls, unfinished

    def execute(self, *_: Any) -> None:
        """Record the run and complete the step, unless it is left unfinished."""
        self.calls.append(f'run {self.step.value}')
        if self.unfinished:
            return
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


def _pipeline(
    tmp_path: Path,
    pipeline_config: PipelineConfig,
    *,
    completed: set[PipelineStep],
    calls: list[str],
    unfinished: PipelineStep | None = None,
) -> tuple[KnowledgeConstructionPipeline, SQLiteUnitOfWork]:
    """Build a pipeline with steps recording into ``calls``, over a database holding the given completed steps."""
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
        )(step, uow, calls, unfinished=step is unfinished)
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
    return pipeline, uow


def _run(
    tmp_path: Path,
    pipeline_config: PipelineConfig,
    *,
    should_reset: bool,
    completed: set[PipelineStep],
    calls: list[str],
    unfinished: PipelineStep | None = None,
) -> bool:
    """Run the pipeline with steps recording into ``calls``, over a database holding the given completed steps."""
    pipeline, _ = _pipeline(tmp_path, pipeline_config, completed=completed, calls=calls, unfinished=unfinished)
    return asyncio.run(pipeline.execute(Workspace(tmp_path), str(tmp_path), should_reset=should_reset))


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
    done = _run(
        tmp_path,
        PipelineConfig(ingest_documents=False, extract_relationships=False, export_knowledge=False),
        should_reset=True,
        completed=ALL_STEPS,
        calls=calls,
    )

    assert done
    assert set(calls[:2]) == {'reset EXTRACT_RELATIONSHIPS', 'reset EXPORT_KNOWLEDGE'}
    assert calls[2:] == ['reset EXTRACT_ENTITIES', 'run EXTRACT_ENTITIES']


def test_a_run_stops_at_an_unfinished_step_and_reports_it(tmp_path: Path) -> None:
    """Leave the steps after an unfinished one for later runs, telling the caller the pipeline isn't done."""
    calls: list[str] = []
    done = _run(
        tmp_path,
        PipelineConfig(),
        should_reset=False,
        completed=set(),
        calls=calls,
        unfinished=PipelineStep.EXTRACT_ENTITIES,
    )

    assert not done
    assert calls == ['run INGEST_DOCUMENTS', 'run EXTRACT_ENTITIES']


def test_a_plan_runs_resets_and_snapshots_nothing(tmp_path: Path) -> None:
    """Report what a run would do with each step without touching the workspace."""
    calls: list[str] = []
    pipeline, _ = _pipeline(
        tmp_path,
        PipelineConfig(ingest_documents=False, extract_relationships=False, export_knowledge=False),
        completed=ALL_STEPS,
        calls=calls,
    )

    plan = pipeline.plan(Workspace(tmp_path), str(tmp_path), should_reset=True)

    assert plan.steps == {
        PipelineStep.INGEST_DOCUMENTS: StepAction.KEEP,
        PipelineStep.EXTRACT_ENTITIES: StepAction.RESET_AND_RUN,
        PipelineStep.EXTRACT_RELATIONSHIPS: StepAction.RESET,
        PipelineStep.EXPORT_KNOWLEDGE: StepAction.RESET,
    }
    assert calls == []
    assert not (tmp_path / 'staging' / 'snapshots').exists()


def test_a_plan_without_reset_skips_completed_steps_but_always_exports(tmp_path: Path) -> None:
    """Plan an export on every run, as the run does, while skipping the other completed steps."""
    pipeline, _ = _pipeline(tmp_path, PipelineConfig(), completed=ALL_STEPS, calls=[])

    plan = pipeline.plan(Workspace(tmp_path), str(tmp_path), should_reset=False)

    assert plan.steps == {
        PipelineStep.INGEST_DOCUMENTS: StepAction.SKIP,
        PipelineStep.EXTRACT_ENTITIES: StepAction.SKIP,
        PipelineStep.EXTRACT_RELATIONSHIPS: StepAction.SKIP,
        PipelineStep.EXPORT_KNOWLEDGE: StepAction.RUN,
    }


def test_resetting_from_a_step_resets_it_and_every_later_step_only(tmp_path: Path) -> None:
    """Reset the later steps first, as a run does, and leave the earlier steps completed."""
    calls: list[str] = []
    pipeline, uow = _pipeline(tmp_path, PipelineConfig(), completed=ALL_STEPS, calls=calls)

    asyncio.run(pipeline.reset(from_step=PipelineStep.EXTRACT_ENTITIES))

    assert calls == ['reset EXPORT_KNOWLEDGE', 'reset EXTRACT_RELATIONSHIPS', 'reset EXTRACT_ENTITIES']
    with uow as tx:
        assert {step for step in PipelineStep if tx.pipeline.is_step_completed(step)} == {
            PipelineStep.INGEST_DOCUMENTS,
        }


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
