"""Jobs for data extraction."""

from dataclasses import dataclass
from typing import Self

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.extraction.model import EntityExtractionTask, RelationshipExtractionTask
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipTypeName

from .values import ExtractionJobId

# Constants
MAX_FAILED_ATTEMPTS = 3  # Maximum number of failed attempts before marking as failed


@dataclass(frozen=True)
class ExtractionJob:
    """Base job for data extraction from a specific source."""

    id: ExtractionJobId
    source: Document | Chunk
    task: EntityExtractionTask | RelationshipExtractionTask


@dataclass(frozen=True)
class EntityExtractionJob(ExtractionJob):
    """Job to perform entity extraction from a specific source."""

    source: Document | Chunk
    task: EntityExtractionTask
    entity_types: tuple[EntityTypeName, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the extraction job."""
        job = f'Job ID: {self.id}\n'
        job += f'Task: {self.task}\n'
        job += f'Entity Types: {", ".join(et.value for et in self.entity_types)}\n'
        job += f'Source: {self.source}'
        return job

    @classmethod
    def from_context(
        cls,
        source: Document | Chunk,
        task: EntityExtractionTask,
        entity_types: tuple[EntityTypeName, ...],
    ) -> Self:
        """Create a new job from its extraction context components, generating a new ID automatically."""
        return cls(id=ExtractionJobId.generate_new(), source=source, task=task, entity_types=entity_types)


# TODO: Complete
@dataclass(frozen=True)
class RelationshipExtractionJob(ExtractionJob):
    """Job to perform relationship extraction from a specific source."""

    source: Chunk
    task: RelationshipExtractionTask
    relationship_types: tuple[RelationshipTypeName, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the extraction job."""
        job = f'Job ID: {self.id}\n'
        job += f'Task: {self.task}\n'
        job += f'Relationship Types: {", ".join(rt.value for rt in self.relationship_types)}\n'
        job += f'Source: {self.source}'
        return job

    @classmethod
    def from_context(
        cls,
        source: Chunk,
        task: RelationshipExtractionTask,
        relationship_types: tuple[RelationshipTypeName, ...],
    ) -> Self:
        """Create a new job from its extraction context components, generating a new ID automatically."""
        return cls(id=ExtractionJobId.generate_new(), source=source, task=task, relationship_types=relationship_types)
