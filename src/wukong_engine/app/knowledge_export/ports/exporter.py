"""Port for exporting extracted knowledge to an output format."""

from typing import Protocol

from wukong_engine.core.knowledge.model import KnowledgeModel


class KnowledgeExporter(Protocol):
    """Exports extracted knowledge (entities, relationships) to a specific output format."""

    def export(self, model: KnowledgeModel, export_uri: str) -> None:
        """Export knowledge to a specified output format.

        Args:
            model: Knowledge model whose entity and relationship types define what gets exported.
            export_uri: Base location where the exported output is written.
        """
        ...

    def clear(self, export_uri: str) -> None:
        """Clear the exported knowledge state, removing any exported data.

        Args:
            export_uri: Base location whose previously exported output is removed.
        """
        ...
