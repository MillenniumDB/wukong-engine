"""Provides the LocalInputSnapshotStore class."""

import json
import shutil
from pathlib import Path
from typing import ClassVar

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.staging.ports import InputSnapshotStore
from wukong_engine.core.pipeline.model.values import InputSnapshot

from .operations import load_json_file


class LocalInputSnapshotStore(InputSnapshotStore):
    """Keeps input snapshots as files in a directory of the workspace."""

    _FILE_NAMES: ClassVar[dict[InputSnapshot, str]] = {
        InputSnapshot.DOCUMENT_REGISTRY: 'document_collections.json',
        InputSnapshot.KNOWLEDGE_MODEL: 'knowledge_model.json',
    }
    _CHUNKING_FILE_NAME: ClassVar[str] = 'chunking.json'

    def __init__(self, directory: Path) -> None:
        """Initialize the store.

        Args:
            directory: Directory holding the snapshots; it is created on the first save.
        """
        self._directory = directory

    def _path(self, snapshot: InputSnapshot) -> Path:
        """Get the path of a snapshot file.

        Args:
            snapshot: Input file whose snapshot is located.

        Returns:
            The path of the snapshot file.
        """
        return self._directory / self._FILE_NAMES[snapshot]

    def exists(self, snapshot: InputSnapshot) -> bool:
        """Check whether a snapshot of an input file has been taken.

        Args:
            snapshot: Input file to check.

        Returns:
            True if the snapshot file exists, False otherwise.
        """
        return self._path(snapshot).is_file()

    def uri(self, snapshot: InputSnapshot) -> str:
        """Get the path of the snapshot of an input file.

        Args:
            snapshot: Input file whose snapshot is located.

        Returns:
            The path of the snapshot file.
        """
        return str(self._path(snapshot))

    def save(self, snapshot: InputSnapshot, source_uri: str) -> None:
        """Copy an input file as its snapshot, replacing any previous one.

        Args:
            snapshot: Input file being snapshotted.
            source_uri: Path of the file to copy.
        """
        self._directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_uri, self._path(snapshot))

    def matches(self, snapshot: InputSnapshot, source_uri: str) -> bool:
        """Check whether an input file still holds the same JSON contents as its snapshot.

        Formatting differences, such as whitespace or key order, don't count as changes.

        Args:
            snapshot: Input file to compare.
            source_uri: Path of the current file.

        Returns:
            True if both parse to the same JSON value, False if they differ or either one can't be read or parsed.
        """
        try:
            return load_json_file(self._path(snapshot)) == load_json_file(Path(source_uri))
        except OSError, ValueError:
            return False

    def discard(self, snapshot: InputSnapshot) -> None:
        """Remove the snapshot of an input file, if any.

        Args:
            snapshot: Input file whose snapshot is removed.
        """
        self._path(snapshot).unlink(missing_ok=True)

    def load_chunking(self) -> ChunkingConfig | None:
        """Load the chunking settings documents were ingested with.

        Returns:
            The chunking settings, or None if they haven't been saved.
        """
        path = self._directory / self._CHUNKING_FILE_NAME
        if not path.is_file():
            return None
        return ChunkingConfig(**load_json_file(path))

    def save_chunking(self, config: ChunkingConfig) -> None:
        """Save the resolved chunking settings documents are ingested with, replacing any previous ones.

        Args:
            config: Chunking settings to save.
        """
        self._directory.mkdir(parents=True, exist_ok=True)
        settings = {
            'target_tokens': config.target_tokens,
            'overlap_tokens': config.overlap_tokens,
            'max_tokens': config.max_tokens,
        }
        (self._directory / self._CHUNKING_FILE_NAME).write_text(json.dumps(settings, indent=4), encoding='utf-8')

    def discard_chunking(self) -> None:
        """Remove the saved chunking settings, if any."""
        (self._directory / self._CHUNKING_FILE_NAME).unlink(missing_ok=True)

    def clear(self) -> None:
        """Remove the snapshot directory with every snapshot in it."""
        shutil.rmtree(self._directory, ignore_errors=True)
