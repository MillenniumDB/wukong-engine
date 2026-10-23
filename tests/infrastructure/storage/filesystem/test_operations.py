"""Tests for the local filesystem operations."""

from pathlib import Path

import pytest

from wukong_engine.infrastructure.storage.filesystem import load_json_file, replacing_directory


def _previous_export(tmp_path: Path) -> Path:
    """Create an export directory holding the files of a previous run."""
    target = tmp_path / 'neo4j'
    (target / 'entities').mkdir(parents=True)
    (target / 'entities' / 'Spacecraft.csv').write_text('previous')
    return target


def test_replacing_a_directory_leaves_none_of_its_previous_files(tmp_path: Path) -> None:
    """Replace the whole directory, so files the new contents no longer include don't linger."""
    target = _previous_export(tmp_path)

    with replacing_directory(target) as staging:
        (staging / 'Astronaut.csv').write_text('new')

    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob('*')) == [
        'neo4j',
        'neo4j/Astronaut.csv',
    ]


def test_a_failed_replacement_keeps_the_previous_directory(tmp_path: Path) -> None:
    """Keep the previous contents intact when building the new ones fails, discarding the partial build."""
    target = _previous_export(tmp_path)

    def fail_midway() -> None:
        with replacing_directory(target) as staging:
            (staging / 'Astronaut.csv').write_text('partial')
            raise RuntimeError

    with pytest.raises(RuntimeError):
        fail_midway()

    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob('*')) == [
        'neo4j',
        'neo4j/entities',
        'neo4j/entities/Spacecraft.csv',
    ]


def test_replacing_a_missing_directory_creates_it(tmp_path: Path) -> None:
    """Create the directory, and its parents, when there are no previous contents."""
    target = tmp_path / 'exports' / 'mdb'

    with replacing_directory(target) as staging:
        (staging / 'knowledge_graph.qm').write_text('new')

    assert (target / 'knowledge_graph.qm').read_text() == 'new'


@pytest.mark.parametrize(
    'content',
    [
        '{"entity_types": {"Mission": {}, "Mission": {}}}',
        '{"collections": {"c": {"sources": [{"root": "a", "root": "b"}]}}}',
    ],
)
def test_json_objects_repeating_a_key_are_rejected(tmp_path: Path, content: str) -> None:
    """Reject a repeated key at any depth, instead of silently keeping its last definition."""
    path = tmp_path / 'definition.json'
    path.write_text(content)

    with pytest.raises(ValueError, match='Duplicate keys in a JSON object'):
        load_json_file(path)


def test_json_files_with_a_byte_order_mark_are_loaded(tmp_path: Path) -> None:
    """Load a JSON file saved with a byte order mark, as some editors do."""
    path = tmp_path / 'definition.json'
    path.write_bytes(b'\xef\xbb\xbf{"collections": {}}')

    assert load_json_file(path) == {'collections': {}}
