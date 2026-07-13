"""Provides the MillenniumDBKnowledgeExporter class."""

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter


# TODO: Add suffix for MDB export file dir
# TODO: Implement
class MillenniumDBKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to the MillenniumDB graph database format."""

    def export(self, export_uri: str) -> None:
        """Export knowledge as a graph to a MillenniumDB QM file."""
        print(f'Exporting knowledge to MillenniumDB QM file at: {export_uri}')
