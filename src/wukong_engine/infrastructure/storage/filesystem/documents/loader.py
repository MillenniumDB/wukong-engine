"""Provides the LocalDocumentLoader class."""

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

from wukong_engine.app.document_ingestion.ports import DocumentLoader
from wukong_engine.core.documents.elements import Document, LoadedDocument
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.chunking.tokenization import HuggingFaceTokenizer

# Logging
logger = logging.getLogger(__name__)


class LocalDocumentLoader(DocumentLoader):
    """Loads the text contents of documents stored on the local filesystem."""

    def __init__(self) -> None:
        """Initialize the document loader."""
        self._tokenizer = HuggingFaceTokenizer()

    def load(self, document: Document, encoding: str = 'utf-8', max_tokens: int | None = None) -> LoadedDocument | None:
        """Load the text contents of a document from the local filesystem."""
        try:
            content = Path(document.source_uri).read_bytes()
            content_hash = ContentHash.from_content_bytes(content)
            if content_hash != document.id.content:
                raise ValueError(f'Content hash mismatch for document: {document}')
            decoded_content = content.decode(encoding=encoding)
            if max_tokens is not None:
                decoded_content = self._tokenizer.truncate(decoded_content, max_tokens)
            return LoadedDocument(metadata=document, content=decoded_content)
        except LookupError, OSError, UnicodeDecodeError:
            logger.error(f'Failed to read content for document {document}')
            return None

    def load_many(
        self,
        documents: Iterable[Document],
        encoding: str = 'utf-8',
        max_tokens: int | None = None,
    ) -> Iterator[LoadedDocument | None]:
        """Load the text contents of multiple documents from the local filesystem."""
        for document in documents:
            yield self.load(document=document, encoding=encoding, max_tokens=max_tokens)
