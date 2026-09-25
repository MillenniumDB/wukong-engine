"""Provides the LocalDocumentSourceValidator class."""

from pathlib import Path

from wukong_engine.app.document_ingestion.ports import DocumentSourceValidator
from wukong_engine.core.documents.model import DocumentSource
from wukong_engine.core.documents.model.values import DocumentSourceMode


class LocalDocumentSourceValidator(DocumentSourceValidator):
    """Validates document sources against the local filesystem."""

    def validate(self, sources: tuple[DocumentSource, ...], data_uri: str) -> None:
        """Validate all given sources.

        Checks for each source that:
        1) The path exists and is contained inside data_uri.
        2) The path type matches the source mode.
        3) The path can be accessed/read.

        Args:
            sources: Document sources to validate.
            data_uri: Data root directory every source must be contained in.

        Raises:
            ValueError: If any source is invalid, listing the errors of every invalid source.
        """
        errors: list[str] = []
        for source in sources:
            root_path = Path(source.root).resolve()
            base_data_path = Path(data_uri).resolve()
            source_label = str(source)

            if root_path != base_data_path and not root_path.is_relative_to(base_data_path):
                errors.append(f'{source_label}: path is outside of the allowed data root "{base_data_path}"')
                continue

            if not root_path.exists():
                errors.append(f'{source_label}: path does not exist')
                continue

            if source.mode is DocumentSourceMode.FILE:
                file_error = self._validate_file_source(root_path, source_label)
                if file_error is not None:
                    errors.append(file_error)
                    continue

            if source.mode in (DocumentSourceMode.DIRECTORY, DocumentSourceMode.RECURSIVE):
                directory_error = self._validate_directory_source(root_path, source_label)
                if directory_error is not None:
                    errors.append(directory_error)

        if errors:
            raise ValueError('Invalid document source(s):\n' + '\n'.join(errors))

    def _validate_file_source(self, path: Path, source_label: str) -> str | None:
        """Validate FILE mode path constraints and return an error message when invalid.

        Args:
            path: Resolved, existing source path.
            source_label: Source description used to prefix the error message.

        Returns:
            An error message if the path is not a readable ".txt" file, None otherwise.
        """
        if not path.is_file():
            return f'{source_label}: expected a file path, but found a non-file path'
        if path.suffix != '.txt':
            return f'{source_label}: expected a ".txt" file'
        if not self._is_readable_file(path):
            return f'{source_label}: file is not readable due to permission/access issues'
        return None

    def _validate_directory_source(self, path: Path, source_label: str) -> str | None:
        """Validate DIRECTORY/RECURSIVE mode path constraints and return an error when invalid.

        Args:
            path: Resolved, existing source path.
            source_label: Source description used to prefix the error message.

        Returns:
            An error message if the path is not an accessible directory, None otherwise.
        """
        if not path.is_dir():
            return f'{source_label}: expected a directory path, but found a non-directory path'
        if not self._is_accessible_directory(path):
            return f'{source_label}: directory is not accessible due to permission/access issues'
        return None

    def _is_readable_file(self, path: Path) -> bool:
        """Return True if the file can be opened for reading.

        Args:
            path: File to check.

        Returns:
            True if the file can be opened for reading, False otherwise.
        """
        try:
            with path.open('rb'):
                pass
        except OSError:
            return False
        return True

    def _is_accessible_directory(self, path: Path) -> bool:
        """Return True if the directory can be traversed/listed.

        Args:
            path: Directory to check.

        Returns:
            True if the directory can be listed, False otherwise.
        """
        try:
            next(path.iterdir(), None)
        except OSError:
            return False
        return True
