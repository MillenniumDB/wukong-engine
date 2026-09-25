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

# Constants
IGNORE_PREFIXES = ('.', '~', '~$')  # Ignore hidden and temporary files


class LocalDocumentStreamProvider(DocumentStreamProvider):
    """Streams documents from a list of sources stored on the local filesystem."""

    def stream(self, sources: tuple[DocumentSource, ...]) -> Iterator[Document]:
        """Find and stream documents from the given list of sources.

        Resolves each source to a set of file paths according to its mode, then yields all Documents found.

        Args:
            sources: Document sources to expand, in order.

        Yields:
            A document for each file found, identified by its content and located by its resolved path.

        Raises:
            ValueError: If a source root doesn't exist or doesn't match its mode.
        """
        for source in sources:
            for path in self._expand_source(source):
                canonical_path = path.resolve()
                yield self._load_document(canonical_path)

    def _validate_source(self, source: DocumentSource) -> None:
        """Validate a document source.

        Args:
            source: Source whose root must exist and match its mode: a ".txt" file for FILE mode, a directory for
                DIRECTORY and RECURSIVE modes.

        Raises:
            FileNotFoundError: If the root path doesn't exist.
            ValueError: If the root path doesn't match the source mode.
        """
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
        """Expand a source root uri into an iterator of concrete file paths.

        Args:
            source: Source to expand. FILE mode yields the root itself, DIRECTORY mode its direct ".txt" files and
                RECURSIVE mode all nested ".txt" files, skipping hidden and temporary files.

        Yields:
            The file paths of the source, built from its root as given (not resolved).

        Raises:
            ValueError: If the source fails validation.
        """
        try:
            self._validate_source(source)
        except Exception as exc:
            error = f'Invalid document source. {exc}'
            logger.error(error)
            raise ValueError(error) from exc
        path = Path(source.root)
        match source.mode:
            case DocumentSourceMode.FILE:
                yield path
            case DocumentSourceMode.DIRECTORY:
                yield from (p for p in path.glob('*.txt') if self._is_valid_document(p))
            case DocumentSourceMode.RECURSIVE:
                yield from (p for p in path.rglob('*.txt') if self._is_valid_document(p))

    @staticmethod
    def _is_valid_document(path: Path) -> bool:
        """Return whether the given path is a valid text file, excluding common system/hidden files.

        Args:
            path: Candidate ".txt" path.

        Returns:
            True if the path is a file whose name doesn't start with a hidden or temporary prefix, False otherwise.
        """
        return path.is_file() and not path.name.startswith(IGNORE_PREFIXES)

    def _load_document(self, path: Path) -> Document:
        """Load a Document from a file path.

        Args:
            path: Resolved path of the file.

        Returns:
            The document identified by the file's content, with the path as its source URI.
        """
        try:
            return Document(
                id=DocumentId.from_content(path.read_bytes()),
                source_uri=str(path),
            )
        except OSError:
            logger.error(f'Failed to load document from "{path}"')
            raise
