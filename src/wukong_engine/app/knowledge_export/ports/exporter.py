from typing import Protocol

from wukong_engine.core.graph.model import GraphModel


# TODO: Add reset method to reset the export directory and checkpoint status
class KnowledgeExporter(Protocol):
    """Exports extracted knowledge (entities, relationships) to a specific output format."""

    def export(self, model: GraphModel, export_uri: str) -> None:
        """Export knowledge to a specified output format."""
        ...
