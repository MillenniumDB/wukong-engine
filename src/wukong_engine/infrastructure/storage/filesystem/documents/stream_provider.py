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
        deduplicates across sources, then yields a Document for each unique path and ID.
        """
        seen_paths: set[Path] = set()
        seen_content: set[bytes] = set()
        for source in sources:
            for path in self._expand_source(source):
                canonical_path = path.resolve()
                if canonical_path in seen_paths:
                    continue
                seen_paths.add(canonical_path)
                document = self._load_document(canonical_path, seen_content)
                if document is not None:
                    yield document

    def _validate_source(self, source: DocumentSource) -> None:
        """Validate a source to make sure its valid."""
        path = Path(source.source_path)
        if not path.exists():
            raise FileNotFoundError(f'Source path does not exist: "{path}"')

        match source.mode:
            case DocumentSourceMode.FILE:
                if not path.is_file() or path.suffix != '.txt':
                    raise ValueError(f'Source path is not a valid ".txt" file: "{path}"')
            case DocumentSourceMode.DIRECTORY | DocumentSourceMode.RECURSIVE:
                if not path.is_dir():
                    raise ValueError(f'Source path is not a valid directory: "{path}"')

    def _expand_source(self, source: DocumentSource) -> Iterator[Path]:
        """Expand a source path into an iterator of concrete file paths."""
        self._validate_source(source)
        path = Path(source.source_path)
        match source.mode:
            case DocumentSourceMode.FILE:
                yield path
            case DocumentSourceMode.DIRECTORY:
                yield from path.glob('*.txt')
            case DocumentSourceMode.RECURSIVE:
                yield from path.rglob('*.txt')

    def _load_document(self, path: Path, seen_content: set[bytes]) -> Document | None:
        """Load a Document from a file path, returning None on error or if the ID is duplicate.

        First loads the bytes, computes the document ID, checks for duplicates,
        and only creates the Document object if the content is new.
        """
        try:
            raw = path.read_bytes()
            doc_id = DocumentId.from_content(raw)

            if doc_id.hash in seen_content:
                logger.warning(
                    f'Found duplicated document content: "{doc_id}" from "{path}" (skipped).',
                )
                return None

            seen_content.add(doc_id.hash)
            return Document(
                id=doc_id,
                text=raw.decode('utf-8'),
                source_path=PurePath(path),
            )
        except OSError:
            logger.warning(f'Failed to load document from "{path}" (skipped).')
            return None
