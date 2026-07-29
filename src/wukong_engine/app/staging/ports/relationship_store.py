from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.graph.elements import ChunkRelationshipProvenance, Relationship, RelationshipChunkProvenance
from wukong_engine.core.graph.model import RelationshipType


class RelationshipStore(Protocol):
    """Store for managing relationships and relationship types."""

    def add_relationship_types(self, relationship_types: Iterable[RelationshipType]) -> None:
        """Add relationship types."""
        ...

    def bulk_upsert_relationships(self, relationships: Iterable[Relationship]) -> None:
        """Insert or update a batch of relationships, ensuring deduplication."""
        ...

    def link_relationships_to_source_context(self, relationships: Iterable[Relationship], context: ContextRef) -> None:
        """Link a batch of relationships to their source context."""
        ...

    def stream_by_relationship_type(self, relationship_type: RelationshipType) -> Iterator[Relationship]:
        """Stream all relationships of a given type."""
        ...

    def stream_provenance_by_chunk(self) -> Iterator[ChunkRelationshipProvenance]:
        """Stream all links of extracted relationships and their source chunks, grouped by chunk."""
        ...

    def stream_provenance_by_relationship_type(
        self,
        relationship_type: RelationshipType,
    ) -> Iterator[RelationshipChunkProvenance]:
        """Stream all links of extracted relationships of a given type and their source chunks, grouped by relationship."""
        ...

    def count_relationships(self) -> int:
        """Count the number of unique relationships."""
        ...

    def count_relationship_mentions(self) -> int:
        """Count the number of relationship mentions."""
        ...

    def clear(self) -> None:
        """Reset the relationship store."""
        ...
