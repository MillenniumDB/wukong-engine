from wukong_engine.core.data_model import DataModel, EntityType, Field
from wukong_engine.core.data_model.values import ContentLevel, FieldMode, FieldType

from .schemas import DataModelSchema, EntityTypeSchema, FieldSchema


# TODO:
def to_data_model(schema: DataModelSchema) -> DataModel:
    """Convert a DataModelSchema to a DataModel domain model."""
    return DataModel(
        entities=tuple(_to_entity_type(entity_type) for entity_type in schema.entities),
    )


# TODO:
def _to_entity_type(schema: EntityTypeSchema) -> EntityType:
    """Convert an EntityTypeSchema to an EntityType domain model."""
    fields = [_to_field(field_schema) for field_schema in schema.fields]

    return EntityType(
        name=schema.name,
        parameters=schema.parameters,
        input_document_groups=schema.input_document_groups,
        fields=fields,
    )


def _to_field(schema: FieldSchema) -> Field:
    """Convert a FieldSchema to a Field domain model."""
    return Field(
        name=schema.name,
        data_type=FieldType(schema.data_type),
        description=schema.description,
        instructions={ContentLevel(k): v for k, v in schema.instructions.items()},
        options=schema.options,
        examples=schema.examples,
        regex={ContentLevel(k): v for k, v in schema.regex.items()},
        default_value={ContentLevel(k): v for k, v in schema.default_value.items()},
        mode={ContentLevel(k): FieldMode(v) for k, v in schema.mode.items()},
        required=schema.required,
    )
