"""Port for exporting extracted knowledge to an output format."""

from typing import Protocol

from wukong_engine.app.knowledge_export.elements import ExportReport
from wukong_engine.core.knowledge.model import KnowledgeModel


class KnowledgeExporter(Protocol):
    """Exports extracted knowledge (entities, relationships) to a specific output format."""

    def export(self, model: KnowledgeModel, export_uri: str) -> ExportReport:
        """Export knowledge to a specified output format.

        Args:
            model: Knowledge model whose entity and relationship types define what gets exported.
            export_uri: Base location where the exported output is written.

        Returns:
            What was exported: the objects of each label and type, and the files written.
        """
        ...
