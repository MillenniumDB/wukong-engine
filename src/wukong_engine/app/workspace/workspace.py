"""Workspace rooted at a user directory."""

from pathlib import Path

from .layout import WorkspaceLayout
from .paths import WorkspacePaths


class Workspace:
    """A user-centered workspace for the engine."""

    def __init__(self, root: Path) -> None:
        """Initialize a workspace with the given root directory.

        Args:
            root: Root directory of the workspace; paths are resolved using the default layout.
        """
        self._root = root
        self._layout = WorkspaceLayout()
        self._paths = WorkspacePaths(self._root, self._layout)

    @property
    def paths(self) -> WorkspacePaths:
        """Workspace paths."""
        return self._paths
