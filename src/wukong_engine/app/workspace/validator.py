import logging

from .exceptions import InvalidWorkspaceError
from .workspace import Workspace

# Logging
logger = logging.getLogger(__name__)


class WorkspaceValidator:
    """Validates the structure and contents of a WUKONG workspace directory."""

    def validate(self, workspace: Workspace) -> None:
        """Validate the workspace directory structure and required files.

        Args:
            workspace: The Workspace instance to validate.
        """
        root = workspace.paths.root
        paths = workspace.paths
        if not root.exists():
            error = f'Workspace directory "{root}" does not exist'
            logger.error(error)
            raise InvalidWorkspaceError(error)
        if not root.is_dir():
            error = f'Workspace path "{root}" is not a directory'
            logger.error(error)
            raise InvalidWorkspaceError(error)
        if not paths.document_registry.exists():
            error = f'Missing document collections JSON file at "{paths.document_registry}"'
            logger.error(error)
            raise InvalidWorkspaceError(error)
        if not paths.graph_model.exists():
            error = f'Missing graph model JSON file at "{paths.graph_model}"'
            logger.error(error)
            raise InvalidWorkspaceError(error)
