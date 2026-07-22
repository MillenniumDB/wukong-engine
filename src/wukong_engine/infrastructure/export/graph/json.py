"""Provides the JSONKnowledgeExporter class."""

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository


# TODO: Implement
class JSONKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to a generic JSON format."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        """Initialize the exporter with necessary dependencies."""
        self._repository = repository

    def export(self, export_uri: str) -> None:
        """Export knowledge as a graph to a set of JSON files."""
        print(f'Exporting knowledge to JSON files at: {export_uri}')
