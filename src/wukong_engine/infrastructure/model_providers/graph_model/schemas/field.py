from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
)

from wukong_engine.core.graph.model.values import ContextLevel, DataType, RegexPattern, RetrievalMode


# TODO: Complete regex
# TODO: retrieval_mode logic here or only domain?
# TODO: Better class docstring that explains attributes
# TODO: Error handling and UX displaying
class FieldSchema(BaseModel):
    """Schema-level representation of a field definition."""

    data_type: DataType
    description: StrictStr
    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    options: list[StrictStr] | StrictStr = Field(default_factory=list)
    examples: list[StrictStr] | StrictStr = Field(default_factory=list)
    regex: dict[ContextLevel, StrictStr] | StrictStr = Field(
        default_factory=dict,
        description='Each value must be a valid regular expression',
        examples=['^[a-z]+$'],
    )
    default_value: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    retrieval_mode: dict[ContextLevel, RetrievalMode] | RetrievalMode = Field(default_factory=dict)
    required: StrictBool = False

    # Mapping of various string representations to DataType members
    _DATA_TYPE_ALIASES: ClassVar[dict[str, DataType]] = {
        'str': DataType.STRING,
        'string': DataType.STRING,
        'text': DataType.STRING,
        # 'int': DataType.INTEGER,
        # 'integer': DataType.INTEGER,
        # 'number': DataType.INTEGER,
        # 'float': DataType.FLOAT,
        # 'double': DataType.FLOAT,
        # 'bool': DataType.BOOLEAN,
        # 'boolean': DataType.BOOLEAN,
    }

    @field_validator('data_type', mode='before')
    @classmethod
    def normalize_data_type(cls, value: Any) -> Any:
        """Normalize data type strings to DataType members."""
        if isinstance(value, str):
            return cls._DATA_TYPE_ALIASES.get(value, value)
        return value

    @field_validator('instructions', 'regex', 'default_value', 'retrieval_mode', mode='before')
    @classmethod
    def parse_context_level_mappings(cls, value: Any) -> Any:
        """Parse context level -> string mappings."""
        if isinstance(value, str):  # Apply same value to all context levels
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('options', 'examples', mode='before')
    @classmethod
    def parse_value_lists(cls, value: Any) -> Any:
        """Parse lists containing string values."""
        if isinstance(value, str):  # Single string value gets converted to single-item list
            return [value]
        return value

    # TODO: finish
    @field_validator('pattern')
    @classmethod
    def validate_regex(cls, value: str) -> str:
        """Validate that the regex pattern is valid."""
        RegexPattern(value)
        return value
