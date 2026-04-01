import json
from dataclasses import dataclass
from types import MappingProxyType

from wukong_engine.core.extraction.model.rules.compatibility import ensure_compatible_context_pairings
from wukong_engine.core.extraction.model.values import RelationshipDeduplicationMode

from .endpoint import Endpoint
from .field import RelationshipField
from .values import FieldName, RelationshipTypeName


@dataclass(frozen=True)
class RelationshipType:
    """A relationship type from the graph model."""

    name: RelationshipTypeName
    description: str
    instructions: str | None
    endpoints: tuple[Endpoint, ...]
    primary_key: FieldName | None
    deduplication_mode: RelationshipDeduplicationMode
    fields: MappingProxyType[FieldName, RelationshipField]

    def __str__(self) -> str:
        """User-friendly string representation of the relationship type."""
        lines = []
        lines.append(str(self.name))
        lines.append(f'  • Description: {self.description}')
        lines.append(f'  • Primary Key: {self.primary_key}')
        lines.append(f'  • Deduplication: {self.deduplication_mode.value}')
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
        """Validate that the primary key is present when required, and properly defined in the fields."""
        if self.primary_key is not None and self.primary_key not in self.fields:
            raise ValueError(
                f'Invalid RelationshipType "{self.name}": primary key "{self.primary_key}" not found in fields',
            )

        if self.deduplication_mode.requires_primary_key and self.primary_key is None:
            raise ValueError(
                f'Invalid RelationshipType "{self.name}": deduplication mode "{self.deduplication_mode.value}" '
                f'requires a primary key, but none was provided',
            )
