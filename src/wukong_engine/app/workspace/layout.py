"""Directory and file layout of a workspace."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    """Directory and file layout for a workspace.

    All paths are relative to the workspace root.

    Attributes:
        DOCUMENT_REGISTRY: Path of the document collections JSON file.
        KNOWLEDGE_MODEL: Path of the knowledge model JSON file.
        STAGING_DB: Path of the SQLite staging database used during extraction.
        EXPORTS: Path of the directory where exports are written.
    """

    DOCUMENT_REGISTRY: str = 'document_collections.json'
    KNOWLEDGE_MODEL: str = 'knowledge_model.json'
    STAGING_DB: str = 'staging/extraction.db'
    EXPORTS: str = 'exports/'
