"""Tests for the SQLite pipeline store: the recorded durations of the runs of each step."""

from pathlib import Path

import pytest

from wukong_engine.core.pipeline.model.values import PipelineStep
from wukong_engine.infrastructure.persistence.sqlite import SQLiteSessionFactory, initialize_sqlite_database
from wukong_engine.infrastructure.persistence.sqlite.stores.pipeline_store import SQLitePipelineStore


def _store(tmp_path: Path) -> SQLitePipelineStore:
    """Create a staging database and a pipeline store over it."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    return SQLitePipelineStore(factory())


def test_the_runs_of_a_step_add_up_until_its_checkpoints_are_reset(tmp_path: Path) -> None:
    """Sum every run of a step, whether it completed or not, and forget only that step's runs when it is reset."""
    store = _store(tmp_path)
    store.record_step_run(PipelineStep.EXTRACT_ENTITIES, 1.5)
    store.record_step_run(PipelineStep.EXTRACT_ENTITIES, 2.25)
    store.record_step_run(PipelineStep.INGEST_DOCUMENTS, 0.5)

    assert store.get_step_durations() == {PipelineStep.EXTRACT_ENTITIES: 3.75, PipelineStep.INGEST_DOCUMENTS: 0.5}

    store.reset_step_checkpoints(PipelineStep.EXTRACT_ENTITIES)
    assert store.get_step_durations() == {PipelineStep.INGEST_DOCUMENTS: 0.5}


@pytest.mark.parametrize('step', list(PipelineStep))
def test_clearing_the_store_forgets_every_run(tmp_path: Path, step: PipelineStep) -> None:
    """Forget the runs of every step when the whole pipeline is reset."""
    store = _store(tmp_path)
    store.record_step_run(step, 1.0)

    store.clear()

    assert store.get_step_durations() == {}
