"""Data Transfer Objects for data extraction."""

from dataclasses import dataclass
from typing import Any

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.graph.model.values import EntityTypeName


# TODO: Complete all DTOs
@dataclass(frozen=True)
class EntityExtractionJob:
    """Pending job to extract entities from a specific source."""

    source: Document | Chunk
    task: EntityExtractionTask
    entity_types: tuple[EntityTypeName, ...]


@dataclass(frozen=True)
class ExtractionContext:
    """Generic structured context for an extraction job."""

    task: str
    document_context: str
    definitions: str
    source_text: str
    response_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExtractionRequest:
    """Extraction request containing an extraction job and its derived context."""

    job: EntityExtractionJob
    context: ExtractionContext


@dataclass(frozen=True)
class ExtractionResult:
    """Extraction result containing the original job and the extracted payload."""

    job: EntityExtractionJob
    payload: dict[str, Any]
