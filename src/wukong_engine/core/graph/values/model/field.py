from dataclasses import dataclass
from typing import Any, Self

from wukong_engine.core.graph.values import ContextLevel, DataType, RetrievalMode


@dataclass(frozen=True)
class Field:
    """A field from an entity/relationship type."""

    name: str  # TODO: Value object for name str, validates naming conventions
    data_type: DataType  # TODO: Validate data type
    description: str
    instructions: dict[ContextLevel, str]  # TODO: Adapt str -> dict (DTO)  # TODO: Validate Context level keys
    options: set[str]  # TODO: Adapt str -> list (DTO)
    examples: list[str]  # TODO: Adapt str -> list (DTO)
    regex: dict[
        ContextLevel,
        str,
    ]  # TODO: Adapt str -> dict (DTO) # TODO: Validate Context level keys # TODO: Value object for regex str
    default_value: dict[ContextLevel, str]  # TODO: Adapt str -> dict (DTO) # TODO: Validate Context level keys
    retrieval_mode: dict[
        ContextLevel,
        RetrievalMode,
    ]  # TODO: Adapt str -> dict (DTO)  # TODO: Validate context level + retrieval mode compatibility
    required: bool

    # @classmethod
    # def from_schema(cls, schema: FieldSchema) -> Self:
    #     """Instantiate from a validated Pydantic FieldSchema."""
    #     return cls(
    #         name=schema.name,
    #         data_type=schema.data_type,
    #         mode=schema.mode,
    #         description=schema.description,
    #         examples=schema.examples,
    #         instructions=schema.instructions,
    #     )

    # TODO: Domain validation
    # @field_validator('name')
    # @classmethod
    # def validate_name(cls, v: str) -> str:
    #     """Validate field naming conventions."""
    #     # General convention
    #     if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', v):
    #         raise ValueError(
    #             f'Invalid field name "{v}". Field names must start with a letter and contain only alphanumeric characters and underscores.',
    #         )

    #     # Special field names
    #     if v.lower() == 'extracted_from':
    #         raise ValueError(f'Field name "{v}" is reserved for special fields and cannot be used')
    #     return v

    # @field_validator('data_type', mode='before')
    # @classmethod
    # def parse_data_type(cls, v: Any) -> DataType:
    #     """Parse data type string."""
    #     # String representation
    #     if isinstance(v, str):
    #         return DataType.from_string(v)
    #     raise TypeError('Expected a string representing a data type')

    # TODO: Callers for usefulness
    # def default_value(self, source: Source) -> Any:
    #     """Get the default value for a specific source.

    #     Args:
    #         source: The source to get the default value for.

    #     Returns:
    #         The default value for the specified source.
    #     """
    #     return self._default_value[source]

    # def mode(self, source: Source) -> FieldMode:
    #     """Get the field mode for a specific source.

    #     Args:
    #         source: The source to get the field mode for.

    #     Returns:
    #         The field mode for the specified source.
    #     """
    #     return self._mode[source]
