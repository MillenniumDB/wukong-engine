from pydantic import BaseModel, Field, StrictStr

from .field import FieldSchema


# TODO: Better class docstring that explains attributes
class EntityTypeSchema(BaseModel):
    """Schema-level representation of an entity type definition."""

    # parameters: dict[str, Any]  # TODO: Validate, decide if flatten or dict
    # input_document_groups: dict[str, list[str] | str] = Field(
    #     default_factory=dict,
    # )  # TODO: Change name, str -> list
    fields: dict[StrictStr, FieldSchema] = Field(default_factory=dict)  # TODO: Validate naming here or in domain?

    # @field_validator('input_document_groups', mode='before')
    # @classmethod
    # def parse_input_document_groups(cls, v: Any) -> Any:
    #     """Parse context level -> document groups mappings."""
    #     # Canonical context level mappings
    #     if isinstance(v, dict):
    #         input_doc_groups = {}
    #         for k, val in v.items():
    #             if isinstance(val, str):  # Single document set
    #                 input_doc_groups[k] = [val]
    #             else:  # Multiple document sets or invalid input
    #                 input_doc_groups[k] = val

    #     # Return raw value
    #     return v
