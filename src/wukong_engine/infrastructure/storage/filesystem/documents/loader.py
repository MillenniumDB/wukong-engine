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

    def load(self, document: Document, encoding: str = 'utf-8', max_tokens: int | None = None) -> LoadedDocument:
        """Load the text contents of a document from the local filesystem.

        Args:
            document: Document whose file at ``source_uri`` is read.
            encoding: Text encoding used to decode the file.
            max_tokens: Maximum number of tokens to keep, truncating the content beyond it. If None, the content is
                not truncated.

        Returns:
            The document paired with its decoded, possibly truncated content.

        Raises:
            ValueError: If the file content no longer matches the document's content hash.
        """
        try:
            content = Path(document.source_uri).read_bytes()
            content_hash = ContentHash.from_content_bytes(content)
            if content_hash != document.id.content:
                error = f'Content hash mismatch for document {document} (expected: {document.id.content}, got: {content_hash})'
                logger.error(error)
                raise ValueError(error)
            decoded_content = content.decode(encoding=encoding)
            if max_tokens is not None:
                decoded_content = self._tokenizer.truncate(decoded_content, max_tokens)
            return LoadedDocument(metadata=document, content=decoded_content)
        except LookupError, OSError, UnicodeDecodeError:
            logger.error(f'Failed to read content for document {document}')
            raise

    def load_many(
        self,
        documents: Iterable[Document],
        encoding: str = 'utf-8',
        max_tokens: int | None = None,
    ) -> Iterator[LoadedDocument]:
        """Load the text contents of multiple documents from the local filesystem.

        Args:
            documents: Documents to load, consumed lazily.
            encoding: Text encoding used to decode each file.
            max_tokens: Maximum number of tokens to keep per document. If None, contents are not truncated.

        Yields:
            Each loaded document, in input order.

        Raises:
            ValueError: If a file's content no longer matches its document's content hash.
        """
        for document in documents:
            yield self.load(document=document, encoding=encoding, max_tokens=max_tokens)
