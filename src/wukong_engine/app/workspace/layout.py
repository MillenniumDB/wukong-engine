from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceLayout:
    """Directory and file layout for a workspace."""

    DOCUMENT_REGISTRY: str = 'document_collections.json'
    KNOWLEDGE_MODEL: str = 'knowledge_model.json'
    STAGING_DB: str = 'staging/extraction.db'
    EXPORTS: str = 'exports/'
