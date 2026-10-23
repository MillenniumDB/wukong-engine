"""Provides the LocalDocumentStreamProvider class."""

import logging
from collections.abc import Iterator
from pathlib import Path

from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.documents.model import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode

from .loader import DOCUMENT_ENCODING

# Logging
logger = logging.getLogger(__name__)

# Constants
IGNORE_PREFIXES = ('.', '~', '~$')  # Ignore hidden and temporary files


class LocalDocumentStreamProvider(DocumentStreamProvider):
    """Streams documents from a list of sources stored on the local filesystem."""

    def stream(self, sources: tuple[DocumentSource, ...], data_uri: str) -> Iterator[Document]:
        """Find and stream documents from the given list of sources.

        Resolves each source to a set of file paths according to its mode, then yields all Documents found. Files
        that resolve outside the data root through a symlink, can't be read or decoded, or hold no text are skipped
        with a warning, and the number of skipped files is reported after each source.

        Args:
            sources: Document sources to expand, in order.
            data_uri: Data root directory every document must resolve inside of; ``~`` is expanded.

        Yields:
            A document for each file found, identified by its content and located by its resolved path, in source
            order and then in path order.

        Raises:
            ValueError: If a source root doesn't exist or doesn't match its mode.
        """
        data_root = Path(data_uri).expanduser().resolve()
        for source in sources:
            skipped = 0
            for path in self._expand_source(source):
                canonical_path = path.resolve()
                if not canonical_path.is_relative_to(data_root):
                    logger.warning(f'Skipping "{path}": it resolves to "{canonical_path}", outside the data root')
                    skipped += 1
                    continue
                document = self._load_document(canonical_path)
                if document is None:
                    skipped += 1
                    continue
                yield document
            if skipped:
                logger.warning(f'Skipped {skipped} file(s) of source {source}')

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
                RECURSIVE mode all nested ".txt" files, skipping hidden and temporary files and directories.

        Yields:
            The file paths of the source, built from its root as given (not resolved), sorted by name within each
            directory.

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
                yield from (p for p in sorted(path.iterdir()) if self._is_valid_document(p))
            case DocumentSourceMode.RECURSIVE:
                for directory, dir_names, file_names in path.walk():
                    # Pruning in place keeps the walk out of hidden directories, and sorting makes its order stable
                    dir_names[:] = sorted(name for name in dir_names if not name.startswith(IGNORE_PREFIXES))
                    yield from (p for p in map(directory.joinpath, sorted(file_names)) if self._is_valid_document(p))

    @staticmethod
    def _is_valid_document(path: Path) -> bool:
        """Return whether the given path is a valid text file, excluding common system/hidden files.

        Args:
            path: Candidate path.

        Returns:
            True if the path is a ".txt" file whose name doesn't start with a hidden or temporary prefix, False
            otherwise.
        """
        return path.suffix == '.txt' and path.is_file() and not path.name.startswith(IGNORE_PREFIXES)

    @staticmethod
    def _load_document(path: Path) -> Document | None:
        """Load a Document from a file path.

        Args:
            path: Resolved path of the file.

        Returns:
            The document identified by the file's content, with the path as its source URI, or None (logging a
            warning) if the file can't be read, isn't valid text in the documents' encoding, or holds no text.
        """
        try:
            content = path.read_bytes()
            text = content.decode(DOCUMENT_ENCODING)
        except OSError as exc:
            logger.warning(f'Skipping "{path}": it could not be read ({exc})')
            return None
        except UnicodeDecodeError as exc:
            logger.warning(f'Skipping "{path}": it is not valid {DOCUMENT_ENCODING} text ({exc})')
            return None
        if not text.strip():
            logger.warning(f'Skipping "{path}": it holds no text')
            return None
        return Document(id=DocumentId.from_content(content), source_uri=str(path))
