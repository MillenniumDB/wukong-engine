"""Provides the LocalWorkspaceInitializer class."""

import json
import logging
from pathlib import Path
from typing import Any

from wukong_engine.app.workspace import Workspace
from wukong_engine.app.workspace.exceptions import WorkspaceError

# Logging
logger = logging.getLogger(__name__)

# Skeleton of the input files: valid as they are, but every <...> text is a placeholder for the user to replace, and the
# collection's root doesn't exist, so documents can't be ingested until the registry is edited
SKELETON_DOCUMENT_REGISTRY: dict[str, Any] = {
    'collections': {
        'my-documents': {
            'sources': [
                {'root': '<path/to/your/documents, relative to the data directory>', 'mode': 'directory'},
            ],
        },
    },
}
SKELETON_KNOWLEDGE_MODEL: dict[str, Any] = {
    'extraction_config': {
        'llm': {
            'domain': '<What the documents are about, e.g. "Annual reports of mining companies.">',
        },
    },
    'entity_types': {
        'Organization': {
            'description': '<What an entity of this type is, e.g. "A company or public body named in the reports.">',
            'primary_key': 'name',
            'fields': {
                'name': {
                    'data_type': 'string',
                    'description': '<What this field holds, e.g. "The official name of the organization.">',
                    'required': True,
                },
            },
            'document_collections': {'chunk': 'my-documents'},
        },
    },
    'relationship_types': {},
}


class LocalWorkspaceInitializer:
    """Creates a new workspace on the local filesystem, with skeleton input files to edit."""

    def initialize(self, workspace: Workspace) -> tuple[Path, ...]:
        """Create the workspace directory, if needed, and its skeleton input files.

        Args:
            workspace: Workspace to create.

        Returns:
            The paths of the created input files.

        Raises:
            WorkspaceError: If the workspace root is not a directory, or an input file already exists, in which case
                nothing is written.
        """
        paths = workspace.paths
        if paths.root.exists() and not paths.root.is_dir():
            error = f'Cannot create workspace "{paths.root}": it exists and is not a directory'
            logger.error(error)
            raise WorkspaceError(error)
        existing = [path for path in (paths.document_registry, paths.knowledge_model) if path.exists()]
        if existing:
            error = (
                f'Cannot create workspace "{paths.root}": it already has '
                f'{" and ".join(f"{path.name}" for path in existing)}, which would be overwritten'
            )
            logger.error(error)
            raise WorkspaceError(error)

        paths.root.mkdir(parents=True, exist_ok=True)
        for path, content in (
            (paths.document_registry, SKELETON_DOCUMENT_REGISTRY),
            (paths.knowledge_model, SKELETON_KNOWLEDGE_MODEL),
        ):
            path.write_text(json.dumps(content, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')
        return paths.document_registry, paths.knowledge_model
