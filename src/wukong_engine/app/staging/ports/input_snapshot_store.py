"""Port for the snapshots of the inputs a workspace's results are produced from."""

from typing import Protocol

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.core.pipeline.model.values import InputSnapshot


class InputSnapshotStore(Protocol):
    """Store keeping a copy of the input files and the chunking settings used by a workspace's steps."""

    def exists(self, snapshot: InputSnapshot) -> bool:
        """Check whether a snapshot of an input file has been taken.

        Args:
            snapshot: Input file to check.

        Returns:
            True if the snapshot exists, False otherwise.
        """
        ...

    def uri(self, snapshot: InputSnapshot) -> str:
        """Get the location of the snapshot of an input file, readable like the original file.

        Args:
            snapshot: Input file whose snapshot is located.

        Returns:
            The location of the snapshot.
        """
        ...

    def save(self, snapshot: InputSnapshot, source_uri: str) -> None:
        """Take a snapshot of an input file, replacing any previous one.

        Args:
            snapshot: Input file being snapshotted.
            source_uri: Location of the file to copy.
        """
        ...

    def matches(self, snapshot: InputSnapshot, source_uri: str) -> bool:
        """Check whether an input file still holds the same contents as its snapshot.

        Args:
            snapshot: Input file to compare.
            source_uri: Location of the current file.

        Returns:
            True if both hold the same contents, False if they differ or either one can't be read.
        """
        ...

    def discard(self, snapshot: InputSnapshot) -> None:
        """Remove the snapshot of an input file, if any.

        Args:
            snapshot: Input file whose snapshot is removed.
        """
        ...

    def load_chunking(self) -> ChunkingConfig | None:
        """Load the chunking settings documents were ingested with.

        Returns:
            The chunking settings, or None if they haven't been saved.
        """
        ...

    def save_chunking(self, config: ChunkingConfig) -> None:
        """Save the chunking settings documents are ingested with, replacing any previous ones.

        Args:
            config: Chunking settings to save.
        """
        ...

    def discard_chunking(self) -> None:
        """Remove the saved chunking settings, if any."""
        ...

    def clear(self) -> None:
        """Remove every snapshot."""
        ...
