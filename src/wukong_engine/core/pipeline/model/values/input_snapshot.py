"""Input files whose snapshot a workspace keeps fixed between resets."""

from enum import Enum


class InputSnapshot(Enum):
    """Input files snapshotted when the first step consuming them runs.

    Attributes:
        DOCUMENT_REGISTRY: The document collections file, consumed first by document ingestion.
        KNOWLEDGE_MODEL: The knowledge model file, consumed first by entity extraction.
    """

    DOCUMENT_REGISTRY = 'DOCUMENT_REGISTRY'
    KNOWLEDGE_MODEL = 'KNOWLEDGE_MODEL'
