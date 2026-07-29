"""Provides the MillenniumDBKnowledgeExporter class."""

from pathlib import Path

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.infrastructure.storage.filesystem import clear_directory


# TODO: Implement
class MillenniumDBKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to the MillenniumDB graph database format."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        """Initialize the exporter with necessary dependencies."""
        self._repository = repository

    def export(self, model: GraphModel, export_uri: str) -> None:
        """Export knowledge to a specified output format."""
        print(f'Exporting knowledge to MillenniumDB QM file at: {export_uri}')

    def clear(self, export_uri: str) -> None:
        """Clear the exported knowledge state, removing any exported data."""
        clear_directory(Path(export_uri).resolve())
