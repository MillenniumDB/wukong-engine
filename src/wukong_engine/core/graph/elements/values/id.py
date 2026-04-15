from dataclasses import dataclass
from typing import ClassVar, Self

from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipIdentityPolicy, RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId

from .normalized_pk import NormalizedPK


@dataclass(frozen=True)
class EntityId:
    """The unique identifier for entities.

    The identifier consists of two components:
        1. instance: A unique id for the runtime instance, used for relationship references and as the id for the final graph.
        2. content: A content-based id, used for efficient deduplication.

    Current Version: v1
    Instance: UUIDv7
    Content: sha-256 hash of "<Version>|<EntityType>|<Normalized_PK>" (first 128 bits)
    """

    instance: InstanceId
    content: ContentHash

    # Versioning (evolves together with the identity structure)
    _VERSION: ClassVar[str] = 'v1'

    def __str__(self) -> str:
        """User-friendly string representation of the entity ID."""
        return f'Instance → {self.instance}, Content → {self.content}'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the entity ID."""
        return f'EntityID(instance={self.instance}, content={self.content}, version={self._VERSION})'

    @classmethod
    def from_identity(cls, entity_type: EntityTypeName, normalized_pk: NormalizedPK) -> Self:
        """Create an EntityId from the identity-defining components of an entity.

        Args:
            entity_type: The name of the entity type.
            normalized_pk: The normalized primary key value of the entity.

        Returns:
            An EntityId that contains instance and content components.
        """
        identity = f'{cls._VERSION}|{entity_type}|{normalized_pk}'
        return cls(instance=InstanceId.generate(), content=ContentHash.from_string(identity))

    @classmethod
    def from_components(cls, instance: InstanceId, content: ContentHash) -> Self:
        """Create an EntityId from already existing instance and content components.

        Args:
            instance: The unique id for the runtime instance.
            content: The content-based id for efficient deduplication.

        Returns:
            An EntityId that contains instance and content components.
        """
        return cls(instance=instance, content=content)


@dataclass(frozen=True)
class RelationshipId:
    """The unique identifier for relationships.

    The identifier consists of two components:
        1. instance: A unique id for the runtime instance, used for the final graph.
        2. content: A content-based id, used for efficient deduplication.

    Current Version: v1
    Instance: UUIDv7
    Content: sha-256 hash of "<Version>|<RelationshipType>|<IdentityPolicy>|<SRC_ID>|<TGT_ID>|<Normalized_PK>?" (first 128 bits)
    """

    instance: InstanceId
    content: ContentHash

    # Versioning (evolves together with the identity structure)
    _VERSION: ClassVar[str] = 'v1'

    def __str__(self) -> str:
        """User-friendly string representation of the relationship ID."""
        return f'Instance → {self.instance}, Content → {self.content}'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the relationship ID."""
        return f'RelationshipID(instance={self.instance}, content={self.content}, version={self._VERSION})'

    @classmethod
    def from_identity(
        cls,
        relationship_type: RelationshipTypeName,
        identity_policy: RelationshipIdentityPolicy,
        source: EntityId,
        target: EntityId,
        normalized_pk: NormalizedPK | None = None,
    ) -> Self:
        """Create a RelationshipId from relationship identity-defining components.

        Args:
            relationship_type: The name of the relationship type.
            identity_policy: The relationship type identity policy.
            source: The source entity id.
            target: The target entity id.
            normalized_pk: Normalized relationship primary key when required by policy.

        Returns:
            A RelationshipId that contains instance and content components.

        Raises:
            ValueError: If primary-key-based relationship identity is requested but no normalized primary key is provided.
        """
        instance_id = InstanceId.generate()

        # Assign identity based on policy
        if identity_policy == RelationshipIdentityPolicy.PRIMARY_KEY:
            if normalized_pk is None:
                raise ValueError('A Normalized PK is required when relationship identity policy is: "primary_key"')
            identity = f'{cls._VERSION}|{relationship_type}|{identity_policy.value}|{source.content}|{target.content}|{normalized_pk}'
            content_id = ContentHash.from_string(identity)
        elif identity_policy == RelationshipIdentityPolicy.ENDPOINTS:
            identity = f'{cls._VERSION}|{relationship_type}|{identity_policy.value}|{source.content}|{target.content}'
            content_id = ContentHash.from_string(identity)
        else:  # If policy is NONE, we fall back to instance-based identity (no deduplication)
            identity = instance_id.to_bytes()
            content_id = ContentHash(identity)

        return cls(instance=instance_id, content=content_id)

    @classmethod
    def from_components(cls, instance: InstanceId, content: ContentHash) -> Self:
        """Create a RelationshipId from already existing instance and content components.

        Args:
            instance: The unique id for the runtime instance.
            content: The content-based id for efficient deduplication.

        Returns:
            A RelationshipId that contains instance and content components.
        """
        return cls(instance=instance, content=content)
