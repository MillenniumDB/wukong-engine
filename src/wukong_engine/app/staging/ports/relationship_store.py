"""Port for the relationship store."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.knowledge.elements import ChunkRelationshipProvenance, Relationship, RelationshipChunkProvenance
from wukong_engine.core.knowledge.model import RelationshipType


class RelationshipStore(Protocol):
    """Store for managing relationships and relationship types."""

    def add_relationship_types(self, relationship_types: Iterable[RelationshipType]) -> None:
        """Add relationship types.

        Args:
            relationship_types: Relationship types to register. Already registered types are ignored.
        """
        ...

    def bulk_upsert_relationships(self, relationships: Iterable[Relationship]) -> None:
        """Insert or update a batch of relationships, ensuring deduplication.

        Relationships sharing the same content ID are merged, both within the batch and with the stored ones.

        Args:
            relationships: Relationships to insert or merge into the stored ones.
        """
        ...

    def link_relationships_to_source_context(self, relationships: Iterable[Relationship], context: ContextRef) -> None:
        """Link a batch of relationships to their source context.

        Args:
            relationships: Relationships extracted from the context. Existing links are ignored.
            context: Source context the relationships were extracted from.
        """
        ...

    def stream_by_relationship_type(self, relationship_type: RelationshipType) -> Iterator[Relationship]:
        """Stream all relationships of a given type.

        Args:
            relationship_type: Relationship type whose relationships are streamed.

        Yields:
            The stored relationships of the given type.
        """
        ...

    def stream_provenance_by_chunk(self) -> Iterator[ChunkRelationshipProvenance]:
        """Stream all links of extracted relationships and their source chunks, grouped by chunk.

        Yields:
            One provenance object per chunk, holding the IDs and types of the relationships extracted from it.
        """
        ...

    def stream_provenance_by_relationship_type(
        self,
        relationship_type: RelationshipType,
    ) -> Iterator[RelationshipChunkProvenance]:
        """Stream all links of extracted relationships of a given type and their source chunks, grouped by relationship.

        Args:
            relationship_type: Relationship type whose provenance is streamed.

        Yields:
            One provenance object per relationship of the given type, holding the IDs of the chunks it was extracted
            from.
        """
        ...

    def count_relationships(self) -> int:
        """Count the number of unique relationships.

        Returns:
            The number of stored (deduplicated) relationships.
        """
        ...

    def count_relationship_mentions(self) -> int:
        """Count the number of relationship mentions.

        Returns:
            The number of links between relationships and the chunks they were extracted from.
        """
        ...

    def clear(self) -> None:
        """Reset the relationship store."""
        ...
