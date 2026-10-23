"""Tests for the recursive document chunker."""

import re

import pytest

from wukong_engine.core.documents.elements import Document, LoadedDocument
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.infrastructure.chunking import ChunkingPlan, RecursiveDocumentChunker
from wukong_engine.infrastructure.chunking.tokenization import CharacterTokenizer, TextTokenizer, TokenizedText


class LeadingSpaceTokenizer(CharacterTokenizer):
    """Character tokenizer that attaches a preceding space to the next character, as BPE tokenizers do."""

    def tokenize(self, text: str) -> TokenizedText:
        """Tokenize each character together with the whitespace character before it, if any."""
        spans = [match.span() for match in re.finditer(r'\s?\S|\s', text)]
        return TokenizedText(text, tuple(start for start, _ in spans), tuple(end for _, end in spans))


def _chunk(
    content: str,
    target_size: int,
    overlap_size: int,
    max_size: int,
    tokenizer: TextTokenizer | None = None,
    *,
    hard_split_only: bool = False,
) -> list[str]:
    """Chunk a text (with the character tokenizer by default) and return the content of each chunk."""
    plan = ChunkingPlan(
        target_size=target_size,
        overlap_size=overlap_size,
        max_size=max_size,
        tokenizer=tokenizer or CharacterTokenizer(),
        **({'boundaries': ()} if hard_split_only else {}),
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


def test_a_hard_split_through_a_token_keeps_the_rest_of_the_token() -> None:
    """Resume the next window at the token the split cut through, so its remaining characters aren't dropped."""
    assert _chunk('a aa', 2, 0, 2, LeadingSpaceTokenizer(), hard_split_only=True) == ['a ', 'aa']


def test_the_overlap_never_starts_past_the_previous_chunk() -> None:
    """Keep the last characters in a chunk when snapping the overlap start forward finds no whitespace."""
    assert _chunk('aaa', 2, 1, 2) == ['aa', 'aa']
