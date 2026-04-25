from pydantic import BaseModel, StrictBool


class PipelineConfigSchema(BaseModel):
    """Pipeline configuration schema."""

    ingest_documents: StrictBool = True
    extract_entities: StrictBool = True
    extract_relationships: StrictBool = True
    export_graph: StrictBool = True
