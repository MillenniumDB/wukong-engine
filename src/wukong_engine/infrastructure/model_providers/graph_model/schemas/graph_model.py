from pydantic import BaseModel, model_validator

from .entity_type import EntityTypeSchema


class GraphModelSchema(BaseModel):
    """Schema-level representation of a graph model definition."""

    parameters: dict = {}
    entities: dict[str, EntityTypeSchema]

    @model_validator(mode='before')
    @classmethod
    def inject_entity_names(cls, data):
        raw_entities = data.get('entities', {})
        normalized_entities = {}

        for entity_name, entity_data in raw_entities.items():
            if not isinstance(entity_data, dict):
                raise TypeError(
                    f'Entity "{entity_name}" must be an object',
                )

            normalized_entities[entity_name] = {
                'name': entity_name,
                **entity_data,
            }

        data['entities'] = normalized_entities
        return data
