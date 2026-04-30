"""Provides the LocalDocumentContentProvider class."""

import logging
from pathlib import Path

from wukong_engine.app.document_ingestion.ports import DocumentContentProvider
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.shared.identity import ContentHash

# Logging
logger = logging.getLogger(__name__)


class LocalDocumentContentProvider(DocumentContentProvider):
    """Provides the text content of a specific document stored on the local filesystem."""

    def get_content(self, document: Document, encoding: str = 'utf-8') -> str | None:
        """Retrieve the text content of a document from the local filesystem."""
        try:
            content = Path(document.source_uri).read_bytes()
            content_hash = ContentHash.from_content_bytes(content)
            if content_hash != document.id.content:
                raise ValueError(f'Content hash mismatch for document: {document}')
            return content.decode(encoding=encoding)
        except LookupError, OSError, UnicodeDecodeError:
            logger.error(f'Failed to read content for document: {document} (skipped).')
            return None
