import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.rules.compatibility import ensure_compatible_context_pairings
from wukong_engine.core.extraction.model.values import RelationshipRetrievalMode

from .endpoint import Endpoint
from .field import RelationshipField
from .values import EntityTypeName, FieldName, MergeStrategy, RelationshipIdentityPolicy, RelationshipTypeName


@dataclass(frozen=True)
class RelationshipType:
    """A relationship type from the graph model."""

    name: RelationshipTypeName
    description: str
    instructions: str | None
    endpoints: tuple[Endpoint, ...]
    primary_key: FieldName | None
    identity_policy: RelationshipIdentityPolicy
    fields: MappingProxyType[FieldName, RelationshipField]
    default_merge_strategy: MergeStrategy

    # Private index for fast retrieval of fields by retrieval mode
    _fields_index: MappingProxyType[RelationshipRetrievalMode, tuple[RelationshipField, ...]] = field(
        init=False,
        repr=False,
    )

    def __str__(self) -> str:
        """User-friendly string representation of the relationship type."""
        lines = []
        lines.append(str(self.name))
        lines.append(f'  • Description: {self.description}')
        lines.append(f'  • Primary Key: {self.primary_key or "NONE"}')
        lines.append(f'  • Identity Policy (Deduplication): {self.identity_policy.value}')
        lines.append(f'  • Fields: {len(self.fields)}')
        lines.append(f'      * {"\n      * ".join(str(field) for field in self.fields.values())}')
        return '\n'.join(lines)

    def __repr__(self) -> str:
        """JSON representation of the relationship type."""
        rel_info = {
            'name': str(self.name),
            'description': self.description,
            'primary_key': str(self.primary_key) if self.primary_key else None,
            'fields': [json.loads(repr(field)) for field in self.fields.values()],
        }
        return json.dumps(rel_info)

    def __post_init__(self) -> None:
        """Validate relationship type invariants."""
        self._validate_endpoints()
        self._validate_primary_key()
        object.__setattr__(self, '_fields_index', self._build_fields_index())

    def _validate_endpoints(self) -> None:
        """Validate that all context level pairings in endpoints are compatible."""
        for endpoint in self.endpoints:
            try:
                ensure_compatible_context_pairings(endpoint.context_pairs)
            except ValueError as error:
                raise ValueError(
                    f'Invalid RelationshipType "{self.name}": endpoint {endpoint} has incompatible context level pairings',
                ) from error

    def _validate_primary_key(self) -> None:
        """Validate primary key invariants."""
        # PK existence when specified
        if self.primary_key is not None and self.primary_key not in self.fields:
            raise ValueError(
                f'Invalid RelationshipType "{self.name}": primary key "{self.primary_key}" not found in fields',
            )

        # PK is required for certain identity policies
        if self.identity_policy.requires_primary_key and self.primary_key is None:
            raise ValueError(
                f'Invalid RelationshipType "{self.name}": identity policy (deduplication mode) "{self.identity_policy.value}" '
                f'requires a primary key, but none was provided. Either define a primary key field or specify a different deduplication mode.',
            )

        # PK retrieval mode must be EXTRACT and the field must be required (if PK is specified)
        if self.primary_key is not None:
            pk_field = self.fields[self.primary_key]
            if pk_field.retrieval_mode != RelationshipRetrievalMode.EXTRACT:
                raise ValueError(
                    f'Invalid RelationshipType "{self.name}": primary key "{self.primary_key}" has retrieval mode '
                    f'"{pk_field.retrieval_mode.value}", expected "extract"',
                )
            if not pk_field.required:
                raise ValueError(
                    f'Invalid RelationshipType "{self.name}": primary key "{self.primary_key}" must be explicitly marked as required (boolean)',
                )

    def _build_fields_index(self) -> MappingProxyType[RelationshipRetrievalMode, tuple[RelationshipField, ...]]:
        """Precompute fields by retrieval mode for fast lookups."""
        index: dict[RelationshipRetrievalMode, list[RelationshipField]] = {
            mode: [] for mode in RelationshipRetrievalMode
        }
        for relationship_field in self.fields.values():
            index[relationship_field.retrieval_mode].append(relationship_field)
        return MappingProxyType(
            {retrieval_mode: tuple(relationship_fields) for retrieval_mode, relationship_fields in index.items()},
        )

    def fields_for(self, retrieval_mode: RelationshipRetrievalMode) -> tuple[RelationshipField, ...]:
        """Get the relevant fields for a specific retrieval mode."""
        return self._fields_index.get(retrieval_mode, ())

    def is_valid_endpoint(
        self,
        source_type: EntityTypeName,
        source_ctx: ContextLevel | Iterable[ContextLevel],
        target_type: EntityTypeName,
        target_ctx: ContextLevel | Iterable[ContextLevel],
    ) -> bool:
        """Whether the given source and target entity types and contexts match a valid endpoint definition for this relationship type."""
        source_ctx_levels = {source_ctx} if isinstance(source_ctx, ContextLevel) else set(source_ctx)
        target_ctx_levels = {target_ctx} if isinstance(target_ctx, ContextLevel) else set(target_ctx)
        for endpoint in self.endpoints:
            if endpoint.source == source_type and endpoint.target == target_type:
                for pair in endpoint.context_pairs:
                    if pair.source_level in source_ctx_levels and pair.target_level in target_ctx_levels:
                        return True
        return False
