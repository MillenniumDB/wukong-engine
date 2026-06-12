"""Data Transfer Objects for data extraction."""

from dataclasses import dataclass
from typing import Any

from wukong_engine.app.llm.elements.values import ResponseMetrics
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.extraction.elements.values import ExtractionStatus
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.graph.model.values import EntityTypeName


@dataclass(frozen=True)
class EntityExtractionJob:
    """Pending job to extract entities from a specific source."""

    source: Document | Chunk
    task: EntityExtractionTask
    entity_types: tuple[EntityTypeName, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the extraction job."""
        job = f'Task: {self.task}\n'
        job += f'Entity Types: {", ".join(et.value for et in self.entity_types)}\n'
        job += f'Source: {self.source}'
        return job


@dataclass(frozen=True)
class ExtractionContext:
    """Generic structured context for an extraction job."""

    document_context: str
    task: str
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
    """Extraction result containing the original job and the extracted data."""

    job: EntityExtractionJob
    data: dict[str, Any]
    status: ExtractionStatus
    metrics: ResponseMetrics | None = None
    error: str | None = None
