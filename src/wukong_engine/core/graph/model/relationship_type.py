import json
from dataclasses import dataclass
from types import MappingProxyType

from .field import RelationshipField
from .rules.compatibility import ensure_compatible_context_pairings
from .values import ContextLevel, EntityTypeName, FieldName, RelationshipDeduplicationMode


@dataclass(frozen=True)
class RelationshipType:
    """A relationship type from the graph model."""

    description: str
    instructions: str | None
    endpoints: MappingProxyType[tuple[EntityTypeName, EntityTypeName], tuple[tuple[ContextLevel, ContextLevel], ...]]
    primary_key: FieldName | None
    deduplication_mode: RelationshipDeduplicationMode
    fields: MappingProxyType[FieldName, RelationshipField]

    def __str__(self) -> str:
        """User-friendly string representation of the relationship type."""
        lines = []
        lines.append(f'Description: {self.description}')

        # Endpoints
        endpoints_str = []
        for (src, tgt), context_pairs in self.endpoints.items():
            context_info = ', '.join(f'{src_ctx.value} → {tgt_ctx.value}' for src_ctx, tgt_ctx in context_pairs)
            endpoints_str.append(f'\n  {src} → {tgt} [{context_info}]')
        lines.append(f'Endpoints: {"".join(endpoints_str)}')

        if self.primary_key:
            lines.append(f'Primary Key: {self.primary_key}')
        lines.append(f'Deduplication: {self.deduplication_mode.value}')
        lines.append(f'Fields: {len(self.fields)}')
        lines.append(f'  {"\n  ".join(f"{field_name}: {field}" for field_name, field in self.fields.items())}')

        return '\n'.join(lines)

    def __repr__(self) -> str:
        """JSON representation of the relationship type."""
        # Format endpoints
        endpoints = []
        for src, tgt in self.endpoints:
            endpoints.append([str(src), str(tgt)])

        # Format fields
        fields = {}
        for field_name, field in self.fields.items():
            fields[str(field_name)] = json.loads(repr(field))

        rel_info = {
            'description': self.description,
            'endpoints': endpoints,
            'fields': fields,
        }
        if self.primary_key:
            rel_info['primary_key'] = str(self.primary_key)

        return json.dumps(rel_info)

    def __post_init__(self) -> None:
        """Validate relationship type invariants."""
        self._validate_endpoints()
        self._validate_primary_key()

    def _validate_endpoints(self) -> None:
        """Validate that all context level pairings in endpoints are compatible."""
        ensure_compatible_context_pairings(self.endpoints)

    def _validate_primary_key(self) -> None:
        """Validate that the primary key is present when required, and properly defined in the fields."""
        if self.primary_key is not None and self.primary_key not in self.fields:
            raise ValueError(f'Invalid RelationshipType: primary key "{self.primary_key}" not found in fields')

        if self.deduplication_mode.requires_primary_key and self.primary_key is None:
            raise ValueError(
                f'Invalid RelationshipType: deduplication mode "{self.deduplication_mode.value}" '
                f'requires a primary key, but none was provided',
            )
