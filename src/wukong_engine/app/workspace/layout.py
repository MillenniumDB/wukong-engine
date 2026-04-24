from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceLayout:
    """Directory and file layout for a workspace."""

    DOCUMENT_REGISTRY: str = 'document_collections.json'
    GRAPH_MODEL: str = 'graph_model.json'
    STAGING_DB: str = 'staging/extraction.db'
    EXPORTS_DIR: str = 'exports/'
