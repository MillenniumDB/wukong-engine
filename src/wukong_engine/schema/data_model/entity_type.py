from pydantic import BaseModel

from .field import FieldSchema


class EntityTypeSchema(BaseModel):
    name: str
    fields: list[FieldSchema]
