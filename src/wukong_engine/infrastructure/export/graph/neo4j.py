"""Provides the Neo4jKnowledgeExporter class."""

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter


# TODO: Implement
class Neo4jKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to the Neo4j graph database format."""

    def export(self, export_uri: str) -> None:
        """Export knowledge as a graph to a set of Neo4j CSV files."""
        print(f'Exporting knowledge to Neo4j CSV files at: {export_uri}')
