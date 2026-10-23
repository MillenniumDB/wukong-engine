"""Tests for the recursive document chunker."""

import pytest

from wukong_engine.core.documents.elements import Document, LoadedDocument
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.infrastructure.chunking import ChunkingPlan, RecursiveDocumentChunker
from wukong_engine.infrastructure.chunking.tokenization import CharacterTokenizer


def _chunk(content: str, target_size: int, overlap_size: int, max_size: int) -> list[str]:
    """Chunk a text with the character tokenizer and return the content of each chunk."""
    plan = ChunkingPlan(
        target_size=target_size,
        overlap_size=overlap_size,
        max_size=max_size,
        tokenizer=CharacterTokenizer(),
    )
    document = Document(id=DocumentId.from_content(content.encode()), source_uri='document.txt')
    return [chunk.content for chunk in RecursiveDocumentChunker(plan).chunk(LoadedDocument(document, content))]


@pytest.mark.parametrize('overlap_size', [0, 3])
def test_pieces_holding_only_whitespace_do_not_become_chunks(overlap_size: int) -> None:
    """Drop whitespace-only pieces, which would each cost an extraction call on no text."""
    chunks = _chunk('first paragraph\n\n' + ' ' * 20 + '\n\nsecond paragraph', 16, overlap_size, 20)

    assert chunks
    assert all(chunk.strip() for chunk in chunks)
    assert 'first paragraph' in chunks[0]
    assert 'second paragraph' in chunks[-1]
