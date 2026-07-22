"""Provides the PropertyValueSerializer class."""

from typing import Any

from .string_serializer import StringSerializer


class PropertyValueSerializer:
    """Serializes and deserializes property values for storage/transmission and retrieval."""

    def __init__(self, string_serializer: StringSerializer) -> None:
        """Initialize the PropertyValueSerializer with a specific StringSerializer."""
        self.string_serializer = string_serializer

    def serialize(self, value: Any) -> str | None:
        """Serialize a property value."""
        # Null values can have different external representations, so return None to be explicit
        if value is None:
            return None

        # Handle different types of property values
        match value:
            case str():  # Keep the string value as-is
                pass
            case int():  # Convert integers to strings directly
                value = str(value)
            case _:  # All other types are unsupported for serialization
                raise ValueError(f'Unsupported property value type: {type(value)}')

        # Apply string serialization to the string value
        return self.string_serializer.serialize(value)
