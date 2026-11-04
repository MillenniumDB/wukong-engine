"""Report of what an export wrote."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExportReport:
    """What an export wrote, counted as it was written.

    Attributes:
        directory: Directory holding the exported files.
        nodes: Number of exported nodes of each label, ``Document`` and ``Chunk`` included.
        edges: Number of exported edges of each type, ``ChunkOf`` and ``ExtractedFrom`` included.
        relationship_provenance: Number of chunk references in the provenance of the exported relationships, summed
            over every relationship.
        files: Size of each exported file in bytes, keyed by its path relative to ``directory``.
    """

    directory: str
    nodes: dict[str, int]
    edges: dict[str, int]
    relationship_provenance: int
    files: dict[str, int]

    @property
    def total_bytes(self) -> int:
        """Total size of the exported files, in bytes."""
        return sum(self.files.values())
