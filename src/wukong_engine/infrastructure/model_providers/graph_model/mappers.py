from wukong_engine.core.graph import ContextLevel, DataType, EntityType, Field, GraphModel, RetrievalMode

from .schemas import EntityTypeSchema, FieldSchema, GraphModelSchema


# TODO:
def schema_to_graph_model(schema: GraphModelSchema) -> GraphModel:
    """Convert a DataModelSchema to a DataModel domain model."""
    return GraphModel(
        entities=tuple(_schema_to_entity_type(entity_type) for entity_type in schema.entity_types),
    )


# TODO:
def _schema_to_entity_type(schema: EntityTypeSchema) -> EntityType:
    """Convert an EntityTypeSchema to an EntityType domain model."""
    fields = [_schema_to_field(field_schema) for field_schema in schema.fields]

    return EntityType(
        name=schema.name,
        parameters=schema.parameters,
        input_document_groups=schema.input_document_groups,
        fields=fields,
    )


def _schema_to_field(schema: FieldSchema) -> Field:
    """Convert a FieldSchema to a Field domain model."""
    return Field(
        name=schema.name,
        data_type=DataType(schema.data_type),
        description=schema.description,
        instructions={ContextLevel(k): v for k, v in schema.instructions.items()},
        options=schema.options,
        examples=schema.examples,
        regex={ContextLevel(k): v for k, v in schema.regex.items()},
        default_value={ContextLevel(k): v for k, v in schema.default_value.items()},
        mode={ContextLevel(k): RetrievalMode(v) for k, v in schema.mode.items()},
        required=schema.required,
    )
