from .workspace import Workspace


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
            raise FileNotFoundError(f'Workspace directory does not exist: {root}')
        if not root.is_dir():
            raise ValueError(f'Workspace path is not a directory: {root}')
        if not paths.document_registry.exists():
            raise FileNotFoundError(f'Missing document collections JSON file: {paths.document_registry}')
        if not paths.graph_model.exists():
            raise FileNotFoundError(f'Missing graph model JSON file: {paths.graph_model}')
