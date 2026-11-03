"""Provides the ExportTally class."""

from pathlib import Path

from wukong_engine.app.knowledge_export.elements import ExportReport
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.infrastructure.storage.filesystem import file_sizes

# Labels and types of the objects every export holds besides the knowledge model's
SOURCE_NODE_LABELS = ('Document', 'Chunk')
SOURCE_EDGE_TYPES = ('ChunkOf', 'ExtractedFrom')


class ExportTally:
    """Counts the objects an export writes, of every label and type it can write, even those it writes none of."""

    def __init__(self, model: KnowledgeModel) -> None:
        """Initialize the tally with a zero count for every label and type the model's export holds.

        Args:
            model: Knowledge model whose active entity and relationship types are exported.
        """
        self.nodes = dict.fromkeys((*SOURCE_NODE_LABELS, *(name.value for name in model.active_entity_types)), 0)
        self.edges = dict.fromkeys(
            (*SOURCE_EDGE_TYPES, *(name.value for name in model.active_relationship_types)),
            0,
        )
        self.relationship_provenance = 0

    def report(self, directory: Path) -> ExportReport:
        """Report the counted objects along with the files of the finished export.

        Args:
            directory: Directory holding the exported files.

        Returns:
            The report of the export.
        """
        return ExportReport(
            directory=str(directory),
            nodes=dict(self.nodes),
            edges=dict(self.edges),
            relationship_provenance=self.relationship_provenance,
            files=file_sizes(directory),
        )
