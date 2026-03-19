from dataclasses import dataclass

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.extraction.model import EntityExtractionTask


@dataclass(frozen=True)
class EntityExtractionRequest:
    """Runtime request for extracting entities from a document."""

    task: EntityExtractionTask
    document: Document
