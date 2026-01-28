from pydantic import BaseModel, ConfigDict, Field


# TODO: Better class docstring that explains attributes
class FieldSchema(BaseModel):
    """Schema-level representation of a field definition."""

    name: str
    data_type: str
    description: str
    instructions: dict[str, str] | str = Field(default_factory=dict)
    options: list[str] | str = Field(default_factory=list)
    examples: list[str] | str = Field(default_factory=list)
    regex: dict[str, str] | str = Field(default_factory=dict)
    default_value: dict[str, str] | str = Field(default_factory=dict)
    retrieval_mode: dict[str, str] | str = Field(default_factory=dict)
    required: bool = False

    # Disable type coercion
    model_config = ConfigDict(strict=True)
