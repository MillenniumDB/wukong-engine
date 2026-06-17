"""Jobs for data extraction."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.graph.model.values import EntityTypeName

from .values import ExtractionJobId

# Constants
MAX_FAILED_ATTEMPTS = 3  # Maximum number of failed attempts before marking as failed


@dataclass(frozen=True)
class EntityExtractionJob:
    """Job to perform entity extraction from a specific source."""

    id: ExtractionJobId
    source: Document | Chunk
    task: EntityExtractionTask
    entity_types: tuple[EntityTypeName, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the extraction job."""
        job = f'ID: {self.id}\n'
        job += f'Task: {self.task}\n'
        job += f'Entity Types: {", ".join(et.value for et in self.entity_types)}\n'
        job += f'Source: {self.source}'
        return job

    @classmethod
    def from_components(
        cls,
        source: Document | Chunk,
        task: EntityExtractionTask,
        entity_types: tuple[EntityTypeName, ...],
    ) -> Self:
        """Create an EntityExtractionJob from its components, generating a new ID automatically."""
        job_id = ExtractionJobId.generate_new()
        return cls(id=job_id, source=source, task=task, entity_types=entity_types)
