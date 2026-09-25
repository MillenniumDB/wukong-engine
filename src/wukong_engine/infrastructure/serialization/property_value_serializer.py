"""Provides the PropertyValueSerializer class."""

from typing import Any

from .string_serializer import StringSerializer


class PropertyValueSerializer:
    """Serializes property values for storage/transmission.

    Attributes:
        string_serializer: Serializer applied to the string form of every non-null value.
    """

    def __init__(self, string_serializer: StringSerializer) -> None:
        """Initialize the PropertyValueSerializer with a specific StringSerializer.

        Args:
            string_serializer: Serializer applied to the string form of every non-null value.
        """
        self.string_serializer = string_serializer

    def serialize(self, value: Any) -> str | None:
        """Serialize a property value.

        Strings are kept as-is and integers are converted with ``str`` before applying the string serializer.

        Args:
            value: Property value to serialize.

        Returns:
            The serialized string, or None if the value is None.

        Raises:
            ValueError: If the value is neither a string nor an integer.
        """
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
