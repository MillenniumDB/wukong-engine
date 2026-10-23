"""Tests for the discovery of documents in local filesystem sources."""

from pathlib import Path

import pytest

from wukong_engine.core.documents.model import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode
from wukong_engine.infrastructure.storage.filesystem.documents import LocalDocumentLoader, LocalDocumentStreamProvider


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


def test_files_that_are_not_valid_text_are_skipped_and_a_bom_is_dropped(tmp_path: Path) -> None:
    """Skip a file that isn't valid UTF-8 instead of aborting the ingestion, and load BOM files without the BOM."""
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'latin1.txt').write_bytes('café'.encode('latin-1'))
    (data / 'bom.txt').write_bytes('﻿hello'.encode())
    source = DocumentSource(root=str(data), mode=DocumentSourceMode.DIRECTORY)

    documents = list(LocalDocumentStreamProvider().stream((source,), str(data)))

    assert [Path(doc.source_uri).name for doc in documents] == ['bom.txt']
    assert LocalDocumentLoader().load(documents[0]).content == 'hello'
