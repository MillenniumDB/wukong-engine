"""Tests for keeping the inputs of a workspace fixed between resets through their snapshots."""

import asyncio
import json
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.config.pipeline import PipelineConfig
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import EntityExtractionRepository, RelationshipExtractionRepository
from wukong_engine.app.document_ingestion.use_cases import CheckDocumentAdditions
from wukong_engine.app.llm.model import LLMRegistry
from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetKnowledgeModel
from wukong_engine.app.shared.exceptions import PipelineExecutionError
from wukong_engine.app.workflows import InputSource, PipelineSteps, ResetPipeline, RunStatsService, StepAction
from wukong_engine.app.workflows.knowledge_construction_pipeline import KnowledgeConstructionPipeline
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.pipeline.model.values import InputSnapshot, PipelineCheckpointStatus, PipelineStep
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem import LocalInputSnapshotStore
from wukong_engine.infrastructure.storage.filesystem.documents import (
    LocalDocumentSourceValidator,
    LocalDocumentStreamProvider,
)

REPOSITORY = Path(__file__).parents[3]
DATA_DIR = REPOSITORY / 'data' / 'example'
MISSION = EntityTypeName('Mission')


def _run_stats(uow: SQLiteUnitOfWork) -> RunStatsService:
    """Build the run stats service over the test database, discarding the stats it would save."""
    return RunStatsService(
        uow=uow,
        entity_repository=EntityExtractionRepository(uow=uow),
        relationship_repository=RelationshipExtractionRepository(uow=uow),
        model=LLMRegistry.default_model(),
        execution_mode=ExecutionMode.REALTIME,
        export_format='MillenniumDB',
        writer=SimpleNamespace(write=lambda *_: None),
    )


class RecordingStep:
    """Pipeline step use case recording the inputs it runs with, completing its checkpoints when run."""

    def __init__(self, step: PipelineStep, uow: SQLiteUnitOfWork) -> None:
        """Initialize the step with the unit of work holding its checkpoints."""
        self.step, self.uow = step, uow
        self.runs: list[tuple[Any, ...]] = []

    def execute(self, *args: Any) -> None:
        """Record the inputs and complete the step."""
        self.runs.append(args)
        with self.uow as tx:
            for checkpoint in self.step.checkpoints:
                tx.pipeline.set_checkpoint_status(checkpoint, PipelineCheckpointStatus.COMPLETED)


class AsyncRecordingStep(RecordingStep):
    """Asynchronous variant of the recording step, as used by the extraction steps."""

    async def execute(self, *args: Any) -> None:
        """Record the inputs and complete the step."""
        super().execute(*args)


class NoReset:
    """Reset use case of a step that stores no results, so it has nothing to reset."""

    def execute(self) -> None:
        """Reset nothing."""


class AsyncNoReset:
    """Asynchronous variant of the empty reset, as used by the extraction steps."""

    async def execute(self) -> None:
        """Reset nothing."""


class Workbench:
    """Example workspace copy whose pipeline runs with recording steps."""

    def __init__(self, tmp_path: Path) -> None:
        """Copy the example workspace definitions and create its staging database."""
        self.root = tmp_path / 'workspace'
        self.root.mkdir()
        for name in ('knowledge_model.json', 'document_collections.json'):
            shutil.copy(REPOSITORY / 'workspaces' / 'example' / name, self.root / name)
        self.workspace = Workspace(self.root)
        factory = SQLiteSessionFactory(db_path=self.workspace.paths.staging_db)
        initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
        self.uow = SQLiteUnitOfWork(connection_factory=factory)
        self.steps = {
            step: (AsyncRecordingStep if step.name.startswith('EXTRACT') else RecordingStep)(step, self.uow)
            for step in PipelineStep
        }

    def edit_registry(self, edit: Callable[[dict[str, Any]], object]) -> None:
        """Apply an edit to the collections of the workspace's document registry."""
        path = self.workspace.paths.document_registry
        registry = json.loads(path.read_text())
        edit(registry['collections'])
        path.write_text(json.dumps(registry))

    def add_model_collection(self, entity_type: str, context_level: str, collection: str) -> None:
        """Add a collection to an entity type of the workspace's knowledge model, at a context level."""
        path = self.workspace.paths.knowledge_model
        model = json.loads(path.read_text())
        collections = model['entity_types'][entity_type]['document_collections']
        current = collections.get(context_level, [])
        collections[context_level] = [*([current] if isinstance(current, str) else current), collection]
        path.write_text(json.dumps(model))

    def completed(self) -> set[PipelineStep]:
        """Get the completed steps."""
        with self.uow as tx:
            return {step for step in PipelineStep if tx.pipeline.is_step_completed(step)}

    def edit_model(self, description: str) -> None:
        """Change the description of the ``Mission`` entity type in the workspace's knowledge model."""
        path = self.workspace.paths.knowledge_model
        model = json.loads(path.read_text())
        model['entity_types']['Mission']['description'] = description
        path.write_text(json.dumps(model))

    def pipeline(self, *steps: PipelineStep, chunking: ChunkingConfig | None = None) -> KnowledgeConstructionPipeline:
        """Build the pipeline with only the given steps enabled."""
        pipeline_config = PipelineConfig(**{step.value.lower(): step in steps for step in PipelineStep})
        return KnowledgeConstructionPipeline(
            app_config=SimpleNamespace(pipeline=pipeline_config, chunking=chunking or ChunkingConfig()),
            uow=self.uow,
            input_snapshots=self.snapshots,
            get_document_registry=GetDocumentRegistry(LocalDocumentRegistryProvider(), LocalDocumentSourceValidator()),
            get_knowledge_model=GetKnowledgeModel(LocalKnowledgeModelProvider()),
            check_document_additions=CheckDocumentAdditions(LocalDocumentStreamProvider(), self.uow),
            steps=PipelineSteps(
                ingest_documents=self.steps[PipelineStep.INGEST_DOCUMENTS],
                extract_entities=self.steps[PipelineStep.EXTRACT_ENTITIES],
                extract_relationships=self.steps[PipelineStep.EXTRACT_RELATIONSHIPS],
                export_knowledge=self.steps[PipelineStep.EXPORT_KNOWLEDGE],
            ),
            reset_pipeline=self.reset_pipeline,
            run_stats=_run_stats(self.uow),
        )

    @property
    def reset_pipeline(self) -> ResetPipeline:
        """Workflow resetting the steps, whose results are only their checkpoints and input snapshots."""
        return ResetPipeline(
            uow=self.uow,
            input_snapshots=self.snapshots,
            reset_document_ingestion=NoReset(),
            reset_entity_extraction=AsyncNoReset(),
            reset_relationship_extraction=AsyncNoReset(),
            reset_knowledge_export=NoReset(),
        )

    @property
    def snapshots(self) -> LocalInputSnapshotStore:
        """Store of the workspace's input snapshots."""
        return LocalInputSnapshotStore(self.workspace.paths.snapshots)

    def run(
        self,
        *steps: PipelineStep,
        reset: bool = False,
        add_documents: bool = False,
        chunking: ChunkingConfig | None = None,
        data_dir: Path = DATA_DIR,
    ) -> None:
        """Run the pipeline with only the given steps enabled."""
        pipeline = self.pipeline(*steps, chunking=chunking)
        asyncio.run(
            pipeline.execute(self.workspace, str(data_dir), should_reset=reset, add_documents=add_documents),
        )

    def last_description(self, step: PipelineStep) -> str:
        """Get the ``Mission`` description of the knowledge model the given step last ran with."""
        model: KnowledgeModel = self.steps[step].runs[-1][0]
        return model.entity_types[MISSION].description


@pytest.fixture
def bench(tmp_path: Path) -> Workbench:
    """Provide a fresh copy of the example workspace."""
    return Workbench(tmp_path)


def test_a_model_edited_after_extraction_is_ignored_with_a_warning(
    bench: Workbench,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep using the model entities were extracted with, warning that the edit needs a reset to apply."""
    bench.run(PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES)
    original = bench.last_description(PipelineStep.EXTRACT_ENTITIES)
    bench.edit_model('An edited description.')

    with caplog.at_level(logging.WARNING):
        bench.run(PipelineStep.EXTRACT_RELATIONSHIPS)

    assert bench.last_description(PipelineStep.EXTRACT_RELATIONSHIPS) == original
    assert 'reset the EXTRACT_ENTITIES step to apply the changes' in caplog.text


def test_resetting_entity_extraction_applies_an_edited_model(bench: Workbench) -> None:
    """Take a new snapshot of the model when the step that first uses it is reset."""
    bench.run(PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES)
    bench.edit_model('An edited description.')

    bench.run(PipelineStep.EXTRACT_ENTITIES, reset=True)
    bench.run(PipelineStep.EXTRACT_RELATIONSHIPS)

    assert bench.last_description(PipelineStep.EXTRACT_ENTITIES) == 'An edited description.'
    assert bench.last_description(PipelineStep.EXTRACT_RELATIONSHIPS) == 'An edited description.'


def test_the_model_is_only_snapshotted_once_entities_are_extracted(bench: Workbench) -> None:
    """Leave the model free to change while only documents have been ingested."""
    bench.run(PipelineStep.INGEST_DOCUMENTS)
    bench.edit_model('An edited description.')

    bench.run(PipelineStep.EXTRACT_ENTITIES)

    assert bench.last_description(PipelineStep.EXTRACT_ENTITIES) == 'An edited description.'


def test_resetting_ingestion_alone_releases_the_model_snapshot(bench: Workbench) -> None:
    """Discard the model snapshot when a reset of ingestion also resets entity extraction, without running it."""
    bench.run(PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES)
    bench.edit_model('An edited description.')

    bench.run(PipelineStep.INGEST_DOCUMENTS, reset=True)
    bench.run(PipelineStep.EXTRACT_ENTITIES)

    assert bench.last_description(PipelineStep.EXTRACT_ENTITIES) == 'An edited description.'


def test_resumed_ingestion_keeps_the_chunking_settings_it_started_with(
    bench: Workbench,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Chunk the rest of an interrupted ingestion with the settings it started with, not newly configured ones."""
    started = ChunkingConfig(target_tokens=800)
    bench.run(PipelineStep.INGEST_DOCUMENTS, chunking=started)
    with bench.uow as tx:
        tx.pipeline.reset_step_checkpoints(PipelineStep.INGEST_DOCUMENTS)  # As if the ingestion was interrupted

    with caplog.at_level(logging.WARNING):
        bench.run(PipelineStep.INGEST_DOCUMENTS, chunking=ChunkingConfig(target_tokens=400))

    assert bench.steps[PipelineStep.INGEST_DOCUMENTS].runs[-1][2] == started
    assert 'The [chunking] settings changed since documents were ingested' in caplog.text


def test_sources_are_not_revalidated_once_documents_are_ingested(bench: Workbench, tmp_path: Path) -> None:
    """Run later steps even if the data directory no longer holds the sources, since ingestion won't read them."""
    bench.run(PipelineStep.INGEST_DOCUMENTS)

    bench.run(PipelineStep.EXTRACT_ENTITIES, data_dir=tmp_path / 'moved')

    assert len(bench.steps[PipelineStep.EXTRACT_ENTITIES].runs) == 1


def test_a_plan_takes_no_snapshot_and_reports_edited_inputs(bench: Workbench) -> None:
    """Tell which inputs a run would snapshot or read from edited snapshots, without snapshotting anything itself."""
    steps = (PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES)
    plan = bench.pipeline(*steps).plan(bench.workspace, str(DATA_DIR), should_reset=False)

    assert {input_plan.source for input_plan in plan.inputs} == {InputSource.NEW_SNAPSHOT}
    assert not bench.workspace.paths.snapshots.exists()

    bench.run(*steps)
    bench.edit_model('An edited description.')
    plan = bench.pipeline(PipelineStep.EXTRACT_RELATIONSHIPS).plan(bench.workspace, str(DATA_DIR), should_reset=False)

    assert [input_plan.source for input_plan in plan.inputs] == [
        InputSource.SNAPSHOT,
        InputSource.OUTDATED_SNAPSHOT,
        InputSource.SNAPSHOT,
    ]


def test_resetting_from_entity_extraction_releases_only_the_model_snapshot(bench: Workbench) -> None:
    """Apply an edited model after a reset from entity extraction, keeping the inputs documents were ingested with."""
    bench.run(PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES)
    bench.edit_model('An edited description.')

    asyncio.run(bench.reset_pipeline.execute(from_step=PipelineStep.EXTRACT_ENTITIES))
    bench.run(PipelineStep.EXTRACT_ENTITIES)

    assert bench.last_description(PipelineStep.EXTRACT_ENTITIES) == 'An edited description.'
    assert bench.snapshots.exists(InputSnapshot.DOCUMENT_REGISTRY)
    assert bench.snapshots.load_chunking() is not None


EXTENDABLE = (PipelineStep.INGEST_DOCUMENTS, PipelineStep.EXTRACT_ENTITIES, PipelineStep.EXTRACT_RELATIONSHIPS)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Provide a copy of the example data directory with an extra directory of logs."""
    data = tmp_path / 'data'
    shutil.copytree(DATA_DIR, data)
    (data / 'logs').mkdir()
    (data / 'logs' / 'log_0001.txt').write_text('Routine log entry.')
    return data


def _add_logs(collections: dict[str, Any]) -> None:
    """Add a collection of the logs directory."""
    collections['logs'] = {'sources': [{'root': 'logs', 'mode': 'directory'}]}


def test_a_plan_adding_documents_extends_the_completed_steps_without_writing(bench: Workbench, data_dir: Path) -> None:
    """Plan to run the completed steps again for the added documents, from a registry that only adds to its snapshot."""
    bench.run(*EXTENDABLE, data_dir=data_dir)
    bench.edit_registry(_add_logs)

    plan = bench.pipeline(*EXTENDABLE).plan(bench.workspace, str(data_dir), should_reset=False, add_documents=True)

    assert [plan.steps[step] for step in EXTENDABLE] == [StepAction.EXTEND] * 3
    assert plan.inputs[0].source is InputSource.EXTENDED_SNAPSHOT
    assert plan.additions is not None
    assert (plan.additions.found_documents, plan.additions.new_documents) == (8, 8)  # The recording steps store none
    assert bench.completed() >= set(EXTENDABLE)
    assert not bench.snapshots.matches(InputSnapshot.DOCUMENT_REGISTRY, str(bench.workspace.paths.document_registry))


def test_adding_documents_runs_the_completed_steps_again_with_the_extended_registry(
    bench: Workbench,
    data_dir: Path,
) -> None:
    """Ingest from the edited registry, snapshot it, and extract again, so later runs keep the added collections."""
    bench.run(*EXTENDABLE, data_dir=data_dir)
    bench.edit_registry(_add_logs)

    bench.run(*EXTENDABLE, add_documents=True, data_dir=data_dir)

    ingested_registry = bench.steps[PipelineStep.INGEST_DOCUMENTS].runs[-1][0]
    assert 'logs' in {str(name) for name in ingested_registry.collections}
    assert all(len(bench.steps[step].runs) == 2 for step in EXTENDABLE)
    assert bench.snapshots.matches(InputSnapshot.DOCUMENT_REGISTRY, str(bench.workspace.paths.document_registry))


def test_steps_disabled_while_adding_documents_are_left_to_run_later(bench: Workbench, data_dir: Path) -> None:
    """Keep the results of disabled steps, but no longer as completed, so a later run processes the added documents."""
    bench.run(*EXTENDABLE, data_dir=data_dir)

    plan = bench.pipeline(PipelineStep.INGEST_DOCUMENTS).plan(
        bench.workspace,
        str(data_dir),
        should_reset=False,
        add_documents=True,
    )
    bench.run(PipelineStep.INGEST_DOCUMENTS, add_documents=True, data_dir=data_dir)

    assert plan.steps[PipelineStep.EXTRACT_ENTITIES] is StepAction.KEEP_TO_EXTEND
    assert bench.completed() == {PipelineStep.INGEST_DOCUMENTS}


def test_adding_documents_from_a_registry_leaving_out_a_source_is_refused(bench: Workbench, data_dir: Path) -> None:
    """Refuse a registry that drops sources of its snapshot, before reopening any step."""
    bench.run(*EXTENDABLE, data_dir=data_dir)
    bench.edit_registry(lambda collections: collections.pop('crew'))

    with pytest.raises(ModelIngestionError, match='leaves out'):
        bench.run(*EXTENDABLE, add_documents=True, data_dir=data_dir)

    assert bench.completed() >= set(EXTENDABLE)


def test_adding_documents_applies_a_model_that_only_adds_collections(bench: Workbench, data_dir: Path) -> None:
    """Extract with an edited model whose only change is a collection added to an entity type, and snapshot it."""
    bench.run(*EXTENDABLE, data_dir=data_dir)
    bench.edit_registry(_add_logs)
    bench.add_model_collection('Incident', 'chunk', 'logs')

    bench.run(*EXTENDABLE, add_documents=True, data_dir=data_dir)

    model: KnowledgeModel = bench.steps[PipelineStep.EXTRACT_ENTITIES].runs[-1][0]
    incident_collections = model.entity_types[EntityTypeName('Incident')].document_collections.values()
    assert 'logs' in {str(name) for collections in incident_collections for name in collections}
    assert bench.snapshots.matches(InputSnapshot.KNOWLEDGE_MODEL, str(bench.workspace.paths.knowledge_model))


def test_adding_documents_keeps_a_model_with_other_changes_with_a_warning(
    bench: Workbench,
    data_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep using the model snapshot when the edited model changes more than its collections."""
    bench.run(*EXTENDABLE, data_dir=data_dir)
    original = bench.last_description(PipelineStep.EXTRACT_ENTITIES)
    bench.edit_model('An edited description.')

    with caplog.at_level(logging.WARNING):
        bench.run(*EXTENDABLE, add_documents=True, data_dir=data_dir)

    assert bench.last_description(PipelineStep.EXTRACT_ENTITIES) == original
    assert 'reset the EXTRACT_ENTITIES step to apply the changes' in caplog.text


@pytest.mark.parametrize(
    ('steps', 'reset'),
    [(EXTENDABLE, True), (EXTENDABLE[1:], False)],
    ids=['with a reset', 'without ingestion'],
)
def test_adding_documents_needs_ingestion_and_no_reset(
    bench: Workbench,
    data_dir: Path,
    steps: tuple[PipelineStep, ...],
    *,
    reset: bool,
) -> None:
    """Refuse to add documents along with a reset, which would discard the results, or without ingesting them."""
    bench.run(*EXTENDABLE, data_dir=data_dir)

    with pytest.raises(PipelineExecutionError):
        bench.run(*steps, reset=reset, add_documents=True, data_dir=data_dir)

    assert bench.completed() >= set(EXTENDABLE)
