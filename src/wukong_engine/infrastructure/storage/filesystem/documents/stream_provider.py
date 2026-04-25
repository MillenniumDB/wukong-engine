"""Provides the LocalDocumentStreamProvider class."""

import logging
from collections.abc import Iterator
from pathlib import Path

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
        """Find and stream documents from the given list of sources.

        Resolves each source to a set of file paths according to its mode, then yields all Documents found.
        """
        for source in sources:
            for path in self._expand_source(source):
                canonical_path = path.resolve()
                document = self._load_document(canonical_path)
                if document is not None:
                    yield document

    def _validate_source(self, source: DocumentSource) -> None:
        """Validate a document source."""
        path = Path(source.root)
        if not path.exists():
            raise FileNotFoundError(f'Root path does not exist: "{path}"')

        match source.mode:
            case DocumentSourceMode.FILE:
                if not path.is_file() or path.suffix != '.txt':
                    raise ValueError(f'Root path is not a valid ".txt" file: "{path}"')
            case DocumentSourceMode.DIRECTORY | DocumentSourceMode.RECURSIVE:
                if not path.is_dir():
                    raise ValueError(f'Root path is not a valid directory: "{path}"')

    def _expand_source(self, source: DocumentSource) -> Iterator[Path]:
        """Expand a source root uri into an iterator of concrete file paths."""
        self._validate_source(source)
        path = Path(source.root)
        match source.mode:
            case DocumentSourceMode.FILE:
                yield path
            case DocumentSourceMode.DIRECTORY:
                yield from path.glob('*.txt')
            case DocumentSourceMode.RECURSIVE:
                yield from path.rglob('*.txt')

    def _load_document(self, path: Path) -> Document | None:
        """Load a Document from a file path."""
        try:
            return Document(
                id=DocumentId.from_content(path.read_bytes()),
                source_uri=str(path),
            )
        except OSError:
            logger.warning(f'Failed to load document from "{path}" (skipped).')
            return None
