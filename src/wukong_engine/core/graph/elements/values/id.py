from dataclasses import dataclass
from typing import Self

from wukong_engine.core.graph.model.values import EntityTypeName
from wukong_engine.core.primitives.identity import ContentHash, InstanceId


# TODO: Model normalized primary key as a separate class, with its own validation and normalization logic
# TODO: Store a content ID version string (e.g. "v1") both here and in the final graph
@dataclass(frozen=True)
class EntityId:
    """The unique identifier for entities.

    The identifier consists of two components:
        1. instance: A unique id for the runtime instance, used for relationship references and as the id for the final graph.
        2. content: A content-based id, used for efficient deduplication.
    """

    instance: InstanceId
    content: ContentHash

    def __str__(self) -> str:
        """User-friendly string representation of the entity ID."""
        return f'{self.instance} (Instance), {self.content} (Content)'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the entity ID."""
        return f'EntityID(instance={self.instance}, content={self.content})'

    @classmethod
    def from_identity(cls, entity_type: EntityTypeName, normalized_pk: str) -> Self:
        """Create an EntityId from the entity type and normalized primary key.

        Args:
            entity_type: The type of the entity (e.g. Person, Organization).
            normalized_pk: The normalized primary key value of the entity.

        Returns:
            A valid EntityId that contains instance and content components.
        """
        identity = f'{entity_type}|{normalized_pk}'  # TODO:
        return cls(instance=InstanceId.generate(), content=ContentHash.from_string(identity))

    @classmethod
    def from_components(cls, instance: InstanceId, content: ContentHash) -> Self:
        """Create an EntityId from already existing instance and content components.

        Args:
            instance: The unique id for the runtime instance.
            content: The content-based id for efficient deduplication.

        Returns:
            A valid EntityId that contains instance and content components.
        """
        return cls(instance=instance, content=content)


# TODO: ID
# Follow the same ideas as with entities, adding the endpoints/structural deduplication as well (3 in total: none, structural, structural + exact normalized PK)
# Have 2 IDs:
# Main (<UUIDv7>) -> for final graph ID
# Content ID (sha-256-hash(<RelationshipType>|<SRC ID>|<TGT ID>|<normalized primary key>) [first 128 bits]) -> for fast exact deduplication
# Above, <SRC ID> and <TGT ID> refer to the respective ID for src/tgt, depending on the dedup mode chosen for it (e.g. if src is dedup "PK" then use content ID, else use unique ID)
# Store all IDs in the relationship instance (SQLite) and graph, consider Main as the unique graph ID
# Store a content ID version string (e.g. "v1") both here and in the final graph
@dataclass(frozen=True)
class RelationshipId:
    """The unique identifier for relationships.

    The identifier consists of two components:
        1. instance: A unique id for the runtime instance, used for the final graph.
        2. content: A content-based id, used for efficient deduplication.
    """
