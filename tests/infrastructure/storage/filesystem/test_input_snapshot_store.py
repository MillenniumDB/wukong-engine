"""Tests for the snapshots of a workspace's input files."""

from pathlib import Path

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.core.pipeline.model.values import InputSnapshot
from wukong_engine.infrastructure.storage.filesystem import LocalInputSnapshotStore


def test_only_content_changes_count_as_changes(tmp_path: Path) -> None:
    """Treat a reformatted file as unchanged, and a file with different contents (or none) as changed."""
    source = tmp_path / 'knowledge_model.json'
    source.write_text('{"entity_types": {}, "relationship_types": {}}')
    store = LocalInputSnapshotStore(tmp_path / 'snapshots')
    store.save(InputSnapshot.KNOWLEDGE_MODEL, str(source))

    source.write_text('{\n    "relationship_types": {},\n    "entity_types": {}\n}\n')
    reformatted = store.matches(InputSnapshot.KNOWLEDGE_MODEL, str(source))
    source.write_text('{"entity_types": {"Mission": {}}}')
    edited = store.matches(InputSnapshot.KNOWLEDGE_MODEL, str(source))
    source.unlink()
    deleted = store.matches(InputSnapshot.KNOWLEDGE_MODEL, str(source))

    assert (reformatted, edited, deleted) == (True, False, False)


def test_chunking_settings_round_trip_with_their_derived_budgets(tmp_path: Path) -> None:
    """Load back the same chunking settings, including the overlap and maximum derived from the target."""
    store = LocalInputSnapshotStore(tmp_path / 'snapshots')
    settings = ChunkingConfig(target_tokens=400)

    store.save_chunking(settings)

    assert store.load_chunking() == settings


def test_clearing_removes_every_snapshot(tmp_path: Path) -> None:
    """Remove the file snapshots and the chunking settings together."""
    source = tmp_path / 'document_collections.json'
    source.write_text('{}')
    store = LocalInputSnapshotStore(tmp_path / 'snapshots')
    store.save(InputSnapshot.DOCUMENT_REGISTRY, str(source))
    store.save_chunking(ChunkingConfig())

    store.clear()

    assert (store.exists(InputSnapshot.DOCUMENT_REGISTRY), store.load_chunking()) == (False, None)
