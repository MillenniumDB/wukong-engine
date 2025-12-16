import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from wukong_engine.core.enums import DataType, FieldMode, Source
from wukong_engine.schema.data_model import FieldSchema

# Logging
logger = logging.getLogger(__name__)

# Paths
DATA_MODEL_PATH = Path('./data_model.json')


# TODO: Complete
@dataclass(frozen=True)
class Field:
    """Represents a field in the internal data model.

    All inputs are assumed to be validated by the schema layer.
    """

    name: str
    data_type: DataType
    description: str | None = None
    instructions: str | None = None
    examples: list[str] | None = None
    _default_value: dict[Source, Any] | None = None
    _mode: dict[Source, FieldMode] | None = None

    @classmethod
    def from_schema(cls, schema: FieldSchema) -> Self:
        """Instantiate from a validated Pydantic FieldSchema."""
        return cls(
            name=schema.name,
            data_type=schema.data_type,
            mode=schema.mode,
            description=schema.description,
            examples=schema.examples,
            instructions=schema.instructions,
        )

    def default_value(self, source: Source) -> Any:
        """Get the default value for a specific source.

        Args:
            source: The source to get the default value for.

        Returns:
            The default value for the specified source.
        """
        return self._default_value[source]

    def mode(self, source: Source) -> FieldMode:
        """Get the field mode for a specific source.

        Args:
            source: The source to get the field mode for.

        Returns:
            The field mode for the specified source.
        """
        return self._mode[source]
