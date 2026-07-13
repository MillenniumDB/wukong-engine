from typing import Protocol


# TODO: Add reset method to reset the export directory and checkpoint status
class KnowledgeExporter(Protocol):
    """Exports extracted knowledge (entities, relationships) to a specific output format."""

    def export(self, export_uri: str) -> None:
        """Export knowledge to a specified output format."""
        ...
