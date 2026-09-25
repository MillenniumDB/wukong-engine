"""Relationship instances between extracted entities."""

from dataclasses import dataclass
from typing import Any

from wukong_engine.core.knowledge.model import RelationshipField, RelationshipType

from .values import EntityId, NormalizedPK, RelationshipId


@dataclass(frozen=True, slots=True)
class Relationship:
    """Relationship instance in the extracted knowledge.

    Attributes:
        id: Unique identifier of the relationship.
        type: Relationship type the instance conforms to.
        source: Identifier of the source entity.
        target: Identifier of the target entity.
        properties: Mapping from field name to string value. Null values are omitted rather than stored.
    """

    id: RelationshipId
    type: RelationshipType
    source: EntityId
    target: EntityId
    properties: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate relationship invariants.

        Raises:
            ValueError: If a property is not a field of the relationship type, a required field is missing, a stored
                value is null, or a value is not among the field's options.
            TypeError: If a property value is not a string.
        """
        self._validate_property_fields()
        self._validate_property_values()

    def _validate_property_fields(self) -> None:
        """Validate property field invariants.

        Raises:
            ValueError: If a property is not a field of the relationship type, or a required field is missing or
                null.
        """
        # All property keys must be valid field names for the relationship type
        valid_field_names = {field.name.value for field in self.type.fields.values()}
        for p_name in self.properties:
            if p_name not in valid_field_names:
                raise ValueError(
                    f'Invalid Relationship: property field "{p_name}" does not exist in RelationshipType "{self.type.name}"\n<Invalid Relationship>\n{self}',
                )

        # Required fields must all be present in properties with a non-null value
        for field in self.type.fields.values():
            if field.required and self.properties.get(field.name.value) is None:
                raise ValueError(
                    f'Invalid Relationship: required field "{field.name.value}" is missing '
                    f'from properties for RelationshipType "{self.type.name}"\n<Invalid Relationship>\n{self}',
                )

    def _validate_property_values(self) -> None:
        """Validate property value invariants.

        Raises:
            ValueError: If a stored value is null or not among the field's defined options.
            TypeError: If a stored value is not a string.
        """
        fields_by_name = {f_name.value: field for f_name, field in self.type.fields.items()}
        for property_name, value in self.properties.items():
            field = fields_by_name[property_name]

            # Stored values in properties must not be null
            if value is None:
                raise ValueError(
                    f'Invalid Relationship: property "{property_name}" has a null value stored (should be omitted instead)\n<Invalid Relationship>\n{self}',
                )

            # Property values must be strings (currently)
            if not isinstance(value, str):
                raise TypeError(
                    f'Invalid Relationship: property "{property_name}" must be of type string, '
                    f'got {type(value).__name__} instead\n<Invalid Relationship>\n{self}',
                )

            # Value must be contained in allowed values (options) if defined for the field
            if field.options and value not in field.options:
                raise ValueError(
                    f'Invalid Relationship: property "{property_name}" value "{value}" '
                    f"is not present in the field's defined options for allowed values: {field.options}\n<Invalid Relationship>\n{self}",
                )

    def __str__(self) -> str:
        """User-friendly string representation of the relationship."""
        lines = []
        lines.append(f'Relationship ID: {self.id}')
        lines.append(f'Type: {self.type.name}')
        lines.append(f'Source Entity ID: {self.source}')
        lines.append(f'Target Entity ID: {self.target}')
        lines.append('Properties:')
        for field, value in self.full_properties.items():
            lines.append(f'  * {field.name}: {value}')
        return '\n'.join(lines)

    @classmethod
    def from_extraction(
        cls,
        relationship_type: RelationshipType,
        source: EntityId,
        target: EntityId,
        properties: dict[str, Any],
        normalized_pk: NormalizedPK | None = None,
    ) -> Relationship:
        """Create a relationship instance from extraction results.

        Properties that are not fields of the relationship type, or whose value is None, are dropped.

        Args:
            relationship_type: Relationship type of the extracted relationship.
            source: Identifier of the source entity.
            target: Identifier of the target entity.
            properties: Extracted properties, keyed by field name.
            normalized_pk: Normalized primary key value. Required only when the type's identity policy is
                ``PRIMARY_KEY``; ignored otherwise.

        Returns:
            The relationship with a freshly generated instance ID and a content ID derived according to the type's
            identity policy.

        Raises:
            ValueError: If the identity policy requires a primary key and ``normalized_pk`` is None, or the remaining
                properties miss a required field or hold a value outside a field's options.
            TypeError: If a remaining property value is not a string.
        """
        relationship_id = RelationshipId.from_identity(
            relationship_type=relationship_type.name,
            identity_policy=relationship_type.identity_policy,
            source=source,
            target=target,
            normalized_pk=normalized_pk,
        )
        valid_properties = {}
        for field in relationship_type.fields.values():
            value = properties.get(field.name.value)
            if value is not None:
                valid_properties[field.name.value] = value
        return cls(
            id=relationship_id,
            type=relationship_type,
            source=source,
            target=target,
            properties=valid_properties,
        )

    @property
    def primary_key_property(self) -> tuple[RelationshipField, Any] | None:
        """The primary key property."""
        if self.type.primary_key is None:
            return None
        primary_key_field = self.type.fields[self.type.primary_key]
        primary_key_value = self.full_properties[primary_key_field]
        return primary_key_field, primary_key_value

    @property
    def required_properties(self) -> dict[RelationshipField, Any]:
        """Required properties."""
        required_props: dict[RelationshipField, Any] = {}
        for field in self.type.fields.values():
            if field.required:
                required_props[field] = self.properties[field.name.value]
        return dict(sorted(required_props.items(), key=lambda item: item[0].name.value))

    @property
    def optional_properties(self) -> dict[RelationshipField, Any]:
        """Optional properties, ignoring those with null values."""
        optional_props: dict[RelationshipField, Any] = {}
        for field in self.type.fields.values():
            if not field.required:
                field_value = self.properties.get(field.name.value)
                if field_value is not None:
                    optional_props[field] = field_value
        return dict(sorted(optional_props.items(), key=lambda item: item[0].name.value))

    @property
    def full_properties(self) -> dict[RelationshipField, Any]:
        """Full set of properties, including those with null values."""
        full_props: dict[RelationshipField, Any] = {}
        for field in self.type.fields.values():
            full_props[field] = self.properties.get(field.name.value)
        return dict(sorted(full_props.items(), key=lambda item: item[0].name.value))
