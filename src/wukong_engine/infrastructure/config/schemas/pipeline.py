from pydantic import BaseModel, StrictBool


class PipelineConfigSchema(BaseModel):
    """Pipeline configuration schema."""

    extract_entities: StrictBool = True
    extract_relationships: StrictBool = True
    export_graph: StrictBool = True
