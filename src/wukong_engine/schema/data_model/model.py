from pydantic import BaseModel

from .entity_type import EntityTypeSchema


class DataModelSchema(BaseModel):
    entities: list[EntityTypeSchema]
