from dataclasses import dataclass
from typing import Any

from wukong_engine.core.graph.elements.values import NormalizedPK
from wukong_engine.core.graph.model import EntityField, EntityType

from .values import EntityId


# TODO: Consider version when exporting
@dataclass(frozen=True)
class Entity:
    """Entity instance in the graph."""

    id: EntityId
    type: EntityType
    properties: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        self._validate_property_fields()
        self._validate_property_values()

    def _validate_property_fields(self) -> None:
        """Validate property field invariants."""
        # All property keys must be valid field names for the entity type
        valid_field_names = {field.name.value for field in self.type.fields.values()}
        for p_name in self.properties:
            if p_name not in valid_field_names:
                raise ValueError(
                    f'Invalid Entity: property field "{p_name}" does not exist in EntityType "{self.type.name}"\n<Invalid Entity>\n{self}',
                )

        # Required fields must all be present in properties with a non-null value
        for field in self.type.fields.values():
            if field.required and self.properties.get(field.name.value) is None:
                raise ValueError(
                    f'Invalid Entity: required field "{field.name.value}" is missing '
                    f'from properties for EntityType "{self.type.name}"\n<Invalid Entity>\n{self}',
                )

    def _validate_property_values(self) -> None:
        """Validate property value invariants."""
        fields_by_name = {f_name.value: field for f_name, field in self.type.fields.items()}
        for property_name, value in self.properties.items():
            field = fields_by_name[property_name]

            # Stored values in properties must not be null
            if value is None:
                raise ValueError(
                    f'Invalid Entity: property "{property_name}" has a null value stored (should be omitted instead)\n<Invalid Entity>\n{self}',
                )

            # Property values must be strings (currently)
            if not isinstance(value, str):
                raise TypeError(
                    f'Invalid Entity: property "{property_name}" must be of type string, '
                    f'got {type(value).__name__} instead\n<Invalid Entity>\n{self}',
                )

            # Value must be contained in allowed values (options) if defined for the field
            if field.options and value not in field.options:
                raise ValueError(
                    f'Invalid Entity: property "{property_name}" value "{value}" '
                    f"is not present in the field's defined options for allowed values: {field.options}\n<Invalid Entity>\n{self}",
                )

    def __str__(self) -> str:
        """User-friendly string representation of the entity."""
        lines = []
        lines.append(f'Entity ID: {self.id}')
        lines.append(f'Type: {self.type.name}')
        lines.append('Properties:')
        for field, value in self.full_properties.items():
            lines.append(f'  * {field.name}: {value}')
        return '\n'.join(lines)

    @classmethod
    def from_extraction(
        cls,
        entity_type: EntityType,
        properties: dict[str, Any],
        normalized_pk: NormalizedPK,
    ) -> Entity:
        """Create an entity instance from extraction results."""
        entity_id = EntityId.from_identity(entity_type=entity_type.name, normalized_pk=normalized_pk)
        valid_properties = {}
        for field in entity_type.fields.values():
            value = properties.get(field.name.value)
            if value is not None:
                valid_properties[field.name.value] = value
        return cls(id=entity_id, type=entity_type, properties=valid_properties)

    @property
    def full_properties(self) -> dict[EntityField, Any]:
        """Get the full set of properties for the entity, as entity fields and their values."""
        full_props: dict[EntityField, Any] = {}
        for field in self.type.fields.values():
            full_props[field] = self.properties.get(field.name.value)
        return dict(sorted(full_props.items(), key=lambda item: item[0].name.value))
