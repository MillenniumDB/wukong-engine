"""Provides the LocalDocumentStreamProvider class."""

import logging
from collections.abc import Iterator
from pathlib import Path, PurePath

from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.documents.model import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode

# Logging
logger = logging.getLogger(__name__)


class LocalDocumentStreamProvider(DocumentStreamProvider):
    """Streams documents from a list of sources stored on the local filesystem."""

    def stream(self, sources: tuple[DocumentSource, ...]) -> Iterator[Document]:
        """Find, deduplicate and stream documents from the given list of sources.

        Resolves each source to a set of file paths according to its mode,
        deduplicates across sources, then yields a Document for each unique path.
        """
        seen: set[Path] = set()
        for source in sources:
            for path in self._expand_source(Path(source.source_path), source.mode):
                canonical_path = path.resolve()
                if canonical_path in seen:
                    continue
                seen.add(canonical_path)
                document = self._load_document(canonical_path)
                if document is not None:
                    yield document

    # TODO: Optimize
    def _expand_source(self, path: Path, mode: DocumentSourceMode) -> Iterator[Path]:
        """Expand a source path into an iterator of concrete file paths."""
        match mode:
            case DocumentSourceMode.FILE:
                yield path
            case DocumentSourceMode.DIRECTORY:
                yield from path.glob('*.txt')
            case DocumentSourceMode.RECURSIVE:
                yield from path.rglob('*.txt')

    def _load_document(self, path: Path) -> Document | None:
        """Load a Document from a file path, returning None on error."""
        try:
            raw = path.read_bytes()
            return Document(
                id=DocumentId.from_bytes(raw),
                text=raw.decode('utf-8'),
                source_path=PurePath(path),
            )
        except Exception:
            logger.exception(f'Failed to load document from "{path}".')
            return None
