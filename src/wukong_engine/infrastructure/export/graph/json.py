"""Provides the JSONKnowledgeExporter class."""

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter


# TODO: Implement
class JSONKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to a generic JSON format."""

    def export(self, export_uri: str) -> None:
        """Export knowledge as a graph to a set of JSON files."""
        print(f'Exporting knowledge to JSON files at: {export_uri}')
