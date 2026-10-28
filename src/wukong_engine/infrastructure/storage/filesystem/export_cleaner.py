"""Clearing of the exports kept in a local directory."""

from pathlib import Path

from wukong_engine.app.knowledge_export.ports import ExportCleaner

from .operations import clear_directory


class LocalExportCleaner(ExportCleaner):
    """Cleaner of the exports written to a local directory, in any format."""

    def clear(self, export_uri: str) -> None:
        """Remove every previously exported output.

        Args:
            export_uri: Base export directory; its whole contents are removed if it exists.
        """
        export_path = Path(export_uri).resolve()
        if export_path.is_dir():
            clear_directory(export_path)
