from pathlib import Path

from .layout import WorkspaceLayout


class WorkspacePaths:
    """Group of paths to key files and directories in a workspace."""

    def __init__(self, root: Path, layout: WorkspaceLayout) -> None:
        """Initialize with the root directory and layout."""
        self._root = root
        self._layout = layout

    @property
    def root(self) -> Path:
        """Path to the root directory of the workspace."""
        return self._root

    @property
    def document_registry(self) -> Path:
        """Path to the document registry file."""
        return self._root / self._layout.DOCUMENT_REGISTRY

    @property
    def knowledge_model(self) -> Path:
        """Path to the knowledge model file."""
        return self._root / self._layout.KNOWLEDGE_MODEL

    @property
    def staging_db(self) -> Path:
        """Path to the staging database file."""
        return self._root / self._layout.STAGING_DB

    @property
    def exports(self) -> Path:
        """Path to the exports directory."""
        return self._root / self._layout.EXPORTS
