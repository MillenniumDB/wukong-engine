"""Tests for the discovery of documents in local filesystem sources."""

from pathlib import Path

import pytest

from wukong_engine.core.documents.model import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode
from wukong_engine.infrastructure.storage.filesystem.documents import LocalDocumentStreamProvider


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a data directory with documents, hidden and temporary entries, and symlinks in and out of it."""
    data = tmp_path / 'data'
    outside = tmp_path / 'outside.txt'
    outside.write_text('secret')
    files = ['docs/b.txt', 'docs/a.txt', 'docs/notes.md', 'docs/~draft.txt', 'docs/sub/c.txt']
    files += ['docs/.git/x.txt', 'docs/.ipynb_checkpoints/a-checkpoint.txt', 'other/d.txt']
    for name in files:
        (data / name).parent.mkdir(parents=True, exist_ok=True)
        (data / name).write_text(name)
    (data / 'docs' / 'link_out.txt').symlink_to(outside)
    (data / 'docs' / 'link_in.txt').symlink_to(data / 'other' / 'd.txt')
    return data


def _stream(data: Path, mode: DocumentSourceMode) -> list[str]:
    """Stream the ``docs`` source of the data directory and return each document's path relative to it."""
    source = DocumentSource(root=str(data / 'docs'), mode=mode)
    return [
        Path(doc.source_uri).relative_to(data).as_posix()
        for doc in LocalDocumentStreamProvider().stream((source,), str(data))
    ]


@pytest.mark.parametrize(
    ('mode', 'expected'),
    [
        (DocumentSourceMode.DIRECTORY, ['docs/a.txt', 'docs/b.txt', 'other/d.txt']),
        (DocumentSourceMode.RECURSIVE, ['docs/a.txt', 'docs/b.txt', 'other/d.txt', 'docs/sub/c.txt']),
    ],
)
def test_sources_yield_only_visible_text_files_inside_the_data_root_in_name_order(
    data_dir: Path,
    mode: DocumentSourceMode,
    expected: list[str],
) -> None:
    """Skip hidden and temporary entries and symlinks leaving the data root, and keep a stable order."""
    assert _stream(data_dir, mode) == expected
