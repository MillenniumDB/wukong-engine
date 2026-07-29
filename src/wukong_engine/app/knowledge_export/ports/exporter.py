from typing import Protocol

from wukong_engine.core.graph.model import GraphModel


class KnowledgeExporter(Protocol):
    """Exports extracted knowledge (entities, relationships) to a specific output format."""

    def export(self, model: GraphModel, export_uri: str) -> None:
        """Export knowledge to a specified output format."""
        ...

    def clear(self, export_uri: str) -> None:
        """Clear the exported knowledge state, removing any exported data."""
        ...
