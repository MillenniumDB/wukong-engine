import hashlib
import uuid
from dataclasses import dataclass
from typing import ClassVar, Self

from wukong_engine.core.graph.model.values import EntityTypeName


# TODO: ID
# TODO: Model content hash and unique ID as separate classes?
# TODO: Store a content ID version string (e.g. "v1") both here and in the final graph
# TODO: Update python to use UUIDv7 natively
# TODO: From components?
# TODO: Model normalized primary key as a separate class, with its own validation and normalization logic
# Store both IDs in the entity instance (SQLite) and graph, consider Main as the unique graph ID
@dataclass(frozen=True)
class EntityId:
    """The unique identifier for entities.

    The identifier consists of two components:
        1. instance: A unique id for the runtime instance, used for relationship references and as the id for the final graph.
        2. content: A content-based id, used for efficient deduplication.
    """

    instance: bytes  # Unique instance identifier (UUIDv7)
    content: bytes  # Content identifier (truncated SHA-256 hash of normalized primary key)

    # Parameters for hashing
    _HASH_SIZE: ClassVar[int] = 16  # 16 bytes → 128 bits → 32 hex chars

    def __post_init__(self) -> None:
        """Validate entity id invariants."""
        self._validate_hash()

    def __str__(self) -> str:
        """User-friendly string representation of the entity ID."""
        return f'{self.instance.hex()} (Instance), {self.content.hex()} (Content)'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the entity ID."""
        return f'EntityID(instance={self.instance.hex()}, content={self.content.hex()})'

    def _validate_hash(self) -> None:
        """Validate that the hash has the correct length."""
        for hash_value in (self.instance, self.content):
            if len(hash_value) != self._HASH_SIZE:
                raise ValueError(
                    f'Invalid hash length: expected {self._HASH_SIZE} bytes, got {len(hash_value)}',
                )

    @classmethod
    def from_identity(cls, entity_type: EntityTypeName, normalized_primary_key: str) -> Self:
        """Create an EntityId from the entity type and normalized primary key.

        Args:
            entity_type: The type of the entity (e.g. Person, Organization).
            normalized_primary_key: The normalized primary key value of the entity.

        Returns:
            A valid EntityId that contains instance and content components.
        """
        instance_id = uuid.uuid4().bytes[: cls._HASH_SIZE]
        content_id = hashlib.sha256(f'{entity_type.value}|{normalized_primary_key}'.encode()).digest()[: cls._HASH_SIZE]
        return cls(instance=instance_id, content=content_id)

    # @classmethod
    # def from_components(cls, instance: InstanceId, content: ContentHash) -> Self: ...


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
